"""One pretrained network matches selected cells and predicts their circle geometry."""
from __future__ import annotations

import math
import copy
import importlib.util
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import mobilenet_v3_small

FORMAT = "icescopy-droplet-mobilenet-examples-v4"


class DropletNet(nn.Module):
    stride = 4

    def __init__(self, pretrained: str | Path | None = None):
        super().__init__()
        backbone = mobilenet_v3_small(weights=None)
        if pretrained is not None:
            backbone.load_state_dict(torch.load(pretrained, map_location="cpu", weights_only=True), strict=True)
        # Original pretrained feature blocks; retain spatial detail at strides 4, 8, 16.
        self.encoder = nn.Sequential(*list(backbone.features.children())[:9])
        self.lateral = nn.ModuleList(nn.Conv2d(c, 32, 1) for c in (16, 24, 48))
        # Every head sees query/reference interactions, with no query-only bypass.
        self.fusion = nn.Sequential(nn.Conv2d(66, 32, 1), nn.SiLU())
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

    def encode(self, image):
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
        return p

    def forward(self, image, examples, example_mask, example_radii):
        """RGB inputs are in [0,1]; active reference radii use query-image pixels."""
        batch = image.shape[0]
        if examples.shape != (batch, 2, 3, 64, 64) or example_mask.shape != (batch, 2) or example_radii.shape != (batch, 2):
            raise ValueError("Require two 64px example slots, a mask and radii for each image")
        active = example_mask.bool()
        if not active.any(dim=1).all():
            raise ValueError("Each image requires one or two selected positive examples")
        if not torch.isfinite(example_radii[active]).all() or not (example_radii[active] > 0).all():
            raise ValueError("Active example radii must be finite and positive")
        query = self.encode(image)
        encoded = self.encode(examples.reshape(batch * 2, 3, 64, 64)).mean(dim=(-2, -1)).reshape(batch, 2, 32)
        weights = active.to(query.dtype)
        denominator = weights.sum(dim=1, keepdim=True)
        reference = (encoded * weights[..., None]).sum(dim=1) / denominator
        reference = reference[:, :, None, None]
        radius = (torch.where(active, example_radii, 0).sum(dim=1, keepdim=True) / denominator)
        radius = (radius / 16).log()[:, :, None, None].expand(-1, -1, *query.shape[-2:])
        cosine = F.cosine_similarity(query, reference, dim=1, eps=1e-6)[:, None]
        interaction = torch.cat((query * reference, (query - reference).abs(), cosine, radius), dim=1)
        raw = self.head(self.decoder(self.fusion(interaction)))
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

    RGB inputs are float32 in [0,1], with two masked 64px examples and pixel radii.
    Outputs are center logit, two sigmoid offsets,
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
        def forward(self, image, examples, example_mask, example_radii):
            prediction = self.network(image, examples, example_mask, example_radii)
            return torch.cat([prediction[name] for name in ("center", "offsets", "log_radius")], dim=1)
    wrapper = Heads(copy.deepcopy(model).cpu().eval())
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = (torch.zeros(1, 3, size, size), torch.zeros(1, 2, 3, 64, 64),
              torch.tensor([[True, False]]), torch.tensor([[16., 0.]]))
    torch.onnx.export(wrapper, inputs, str(output), dynamo=False, opset_version=12,
                      input_names=["rgb", "examples", "example_mask", "example_radii"], output_names=["prediction"])
    return output
