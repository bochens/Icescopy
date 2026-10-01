"""One small network predicts droplet centers and circle geometry together."""
from __future__ import annotations

import math
import copy
import importlib.util
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

FORMAT = "icescopy-droplet-cnn-v2"


def _stage(input_channels, output_channels):
    return nn.Sequential(nn.Conv2d(input_channels, output_channels, 3, stride=2, padding=1), nn.ReLU(),
                         nn.Conv2d(output_channels, output_channels, 3, padding=1), nn.ReLU())


class DropletNet(nn.Module):
    stride = 4

    def __init__(self):
        super().__init__()
        self.encoder = nn.ModuleList([_stage(3, 16), _stage(16, 32), _stage(32, 64)])
        self.lateral = nn.Conv2d(64, 32, 1)
        self.decoder = nn.Sequential(
            nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
        )
        self.head = nn.Conv2d(32, 4, 1)
        nn.init.normal_(self.head.weight, std=0.01)
        nn.init.zeros_(self.head.bias)
        with torch.no_grad():
            self.head.bias[0] = math.log(0.01 / 0.99)

    def forward(self, image):
        x = self.encoder[0](image * 2 - 1)
        skip = self.encoder[1](x)
        p = F.interpolate(self.lateral(self.encoder[2](skip)), size=skip.shape[-2:], mode="nearest") + skip
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
    if payload.get("format") != FORMAT:
        raise ValueError("Unsupported droplet model format")
    model = DropletNet()
    model.load_state_dict(payload["state_dict"], strict=True)
    return model.to(device).eval(), payload


def export_onnx(model, output, *, size=256):
    """Export standard convolution operations; output channels match the heads.

    RGB input is float32 in [0,1]. Outputs are center logit, two sigmoid offsets,
    and log(radius/16). The optional onnx package must already be installed.
    """
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if size < 32 or size % 4:
        raise ValueError("size must be at least 32 and divisible by 4")
    if importlib.util.find_spec("onnx") is None:
        raise RuntimeError("Optional ONNX export requires the onnx package; it is not installed")
    class Heads(nn.Module):
        def __init__(self, network):
            super().__init__()
            self.network = network
        def forward(self, image):
            prediction = self.network(image)
            return torch.cat([prediction[name] for name in ("center", "offsets", "log_radius")], dim=1)
    wrapper = Heads(copy.deepcopy(model).cpu().eval())
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(wrapper, torch.zeros(1, 3, size, size), str(output), dynamo=False,
                      opset_version=12, input_names=["rgb"], output_names=["prediction"])
    return output
