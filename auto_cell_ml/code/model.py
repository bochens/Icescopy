"""One small network predicts droplet centers and circle geometry together."""
from __future__ import annotations

import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import mobilenet_v3_small


class DropletNet(nn.Module):
    stride = 4

    def __init__(self, pretrained: str | Path | None = None):
        super().__init__()
        backbone = mobilenet_v3_small(weights=None)
        if pretrained is not None:
            backbone.load_state_dict(torch.load(pretrained, map_location="cpu", weights_only=True))
        # Original pretrained feature blocks; retain spatial detail at strides 4, 8, 16.
        self.encoder = nn.Sequential(*list(backbone.features.children())[:9])
        self.lateral = nn.ModuleList(nn.Conv2d(c, 32, 1) for c in (16, 24, 48))
        self.decoder = nn.Sequential(
            nn.Conv2d(32, 32, 3, padding=1), nn.GroupNorm(8, 32), nn.SiLU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.GroupNorm(8, 32), nn.SiLU(),
        )
        self.head = nn.Conv2d(32, 4, 1)
        nn.init.normal_(self.head.weight, std=0.01)
        nn.init.zeros_(self.head.bias)
        with torch.no_grad():
            self.head.bias[0] = math.log(0.01 / 0.99)
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def train(self, mode=True):
        super().train(mode)
        # A few related source pictures should not replace pretrained population statistics.
        for module in self.encoder.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        return self

    def forward(self, image):
        x = (image - self.mean) / self.std
        features = []
        for index, layer in enumerate(self.encoder):
            x = layer(x)
            if index in (1, 3, 8):
                features.append(x)
        p = self.lateral[2](features[2])
        for index in (1, 0):
            p = F.interpolate(p, size=features[index].shape[-2:], mode="bilinear", align_corners=False)
            p = p + self.lateral[index](features[index])
        raw = self.head(self.decoder(p))
        return {"center": raw[:, :1], "offsets": raw[:, 1:3].sigmoid(), "log_radius": raw[:, 3:4]}


def loss(prediction, target):
    """Every valid non-center cell is negative, including empty wells and tray edges."""
    center, valid = target["center"], target["valid"]
    positive = center * valid
    count = positive.sum().clamp_min(1)
    logits = prediction["center"]
    prob = logits.sigmoid()
    # Focal loss reduces easy-background influence; confident false positives keep full weight.
    wrong_probability = torch.where(center.bool(), 1 - prob, prob)
    classification = (F.binary_cross_entropy_with_logits(logits, center, reduction="none")
                      * wrong_probability.square() * valid).sum() / count
    offsets = (F.smooth_l1_loss(prediction["offsets"], target["offsets"], reduction="none")
               * positive).sum() / count
    radius = (F.smooth_l1_loss(prediction["log_radius"], target["log_radius"], reduction="none")
              * positive).sum() / count
    return {"total": classification + offsets + radius,
            "center": classification, "offsets": offsets, "radius": radius}


def load_model(path, device="cpu"):
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("format") != "icescopy-droplet-net-v1":
        raise ValueError("Unsupported droplet model format")
    model = DropletNet()
    model.load_state_dict(payload["state_dict"], strict=True)
    return model.to(device).eval(), payload
