"""One example-conditioned network predicts dense centers, offsets and radii."""
from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import mobilenet_v3_small

from detector import Circle, preprocess_image, same_object, validate_examples
from neural_model import FineTunedEncoder


VERSION = 1
ARCHITECTURE = 'mobilenet-v3-small-example-conditioned-center-offset-radius-v1'
STRIDE = 4
NORMALIZED_RADIUS = 16.
TILE = 384
HALO = 64
CORE = TILE-2*HALO
PADDING_RGB = (.485, .456, .406)  # Zero after ImageNet channel normalization.


def input_tensor(rgb):
    values = torch.from_numpy(np.asarray(rgb, dtype=np.float32).transpose(0, 3, 1, 2).copy())
    return (values-torch.tensor([.485, .456, .406])[None, :, None, None])/torch.tensor([.229, .224, .225])[None, :, None, None]


def scaled_image(image, scale):
    """One exact isotropic transform, including the pixel-center convention."""
    height, width = image.shape[:2]
    matrix = np.asarray([[scale, 0, (scale-1)/2], [0, scale, (scale-1)/2]], dtype=np.float32)
    return cv2.warpAffine(image, matrix, (math.ceil(width*scale), math.ceil(height*scale)),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=PADDING_RGB)


class Smooth(nn.Sequential):
    def __init__(self):
        super().__init__(nn.Conv2d(32, 32, 3, padding=1, groups=32), nn.Conv2d(32, 32, 1), nn.SiLU())


class JointNetwork(nn.Module):
    def __init__(self, parent_checkpoint=None):
        super().__init__()
        self.backbone = (FineTunedEncoder(parent_checkpoint).model.features if parent_checkpoint is not None
                         else mobilenet_v3_small(weights=None).features)
        for name, parameter in self.backbone.named_parameters():
            parameter.requires_grad_(int(name.split('.')[0]) >= 10)
        self.lateral = nn.ModuleList([nn.Conv2d(c, 32, 1) for c in (16, 24, 48, 576)])
        self.smooth = nn.ModuleList([Smooth() for _ in range(3)])
        self.condition = nn.Sequential(nn.Conv2d(65, 32, 1), nn.SiLU(), Smooth())
        self.confidence = nn.Conv2d(32, 1, 1)
        self.offset = nn.Conv2d(32, 2, 1)
        self.radius = nn.Conv2d(32, 1, 1)
        nn.init.normal_(self.confidence.weight, std=.01)
        nn.init.constant_(self.confidence.bias, math.log(.1/.9))
        nn.init.zeros_(self.offset.weight); nn.init.zeros_(self.offset.bias)
        nn.init.zeros_(self.radius.weight); nn.init.zeros_(self.radius.bias)
        self.train(False)

    def train(self, mode=True):
        super().train(mode)
        for module in self.backbone.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        return self

    def prefix_maps(self, image):
        maps = []
        with torch.no_grad():
            for index in range(10):
                image = self.backbone[index](image)
                if index in (1, 3, 8, 9):
                    maps.append(image)
        return maps

    def decode(self, maps):
        deep = self.backbone[10:](maps[3])
        value = self.lateral[3](deep)
        for index in (2, 1, 0):
            value = F.interpolate(value, size=maps[index].shape[-2:], mode='bilinear', align_corners=False)
            value = self.smooth[index](value+self.lateral[index](maps[index]))
        return value

    def queries(self, features, examples):
        """Pool actual shared-image features at supplied x/y/r coordinates.

        Coordinates are already divided by output stride. No examples from
        another frame enter this operation. Nine inner points reduce aliasing.
        """
        height, width = features.shape[-2:]
        dx, dy = torch.meshgrid(torch.tensor([-.25, 0., .25], device=features.device),
                                torch.tensor([-.25, 0., .25], device=features.device), indexing='xy')
        offsets = torch.stack([dx.flatten(), dy.flatten()], -1)
        positions = examples[..., :2, None].transpose(-1, -2)+examples[..., 2, None, None]*offsets
        grid = positions.clone()
        grid[..., 0] = 2*grid[..., 0]/max(1, width-1)-1
        grid[..., 1] = 2*grid[..., 1]/max(1, height-1)-1
        sampled = F.grid_sample(features, grid, align_corners=True, padding_mode='border')
        return F.normalize(sampled.mean(-1).transpose(1, 2), dim=-1)

    def predictions(self, features, examples):
        queries = self.queries(features, examples)
        normalized = F.normalize(features, dim=1)
        similarities = torch.einsum('bchw,bec->behw', normalized, queries)
        maximum, which = similarities.max(dim=1, keepdim=True)
        query_field = queries.gather(1, which.flatten(2).transpose(1, 2).expand(-1, -1, 32))
        query_field = query_field.transpose(1, 2).reshape_as(features)
        conditioned = self.condition(torch.cat([features, features*query_field, maximum], 1))
        return {'logits': self.confidence(conditioned), 'offset': self.offset(conditioned).sigmoid(),
                'log_radius': self.radius(conditioned).tanh()*.7}

    def forward(self, images, examples):
        return self.predictions(self.decode(self.prefix_maps(images)), examples)


def save_joint(path, network, metadata):
    path = Path(path)
    if path.exists():
        raise ValueError('Joint checkpoint exists; use a fresh output path.')
    torch.save({'version': VERSION, 'architecture': ARCHITECTURE,
                'state_dict': network.state_dict(), 'metadata': metadata}, path)


class JointDetector:
    def __init__(self, checkpoint, threads=4):
        torch.set_num_threads(threads)
        saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if saved.get('version') != VERSION or saved.get('architecture') != ARCHITECTURE:
            raise ValueError('Unsupported joint detector checkpoint.')
        self.network = JointNetwork()
        self.network.load_state_dict(saved['state_dict'], strict=True); self.network.eval()
        self.metadata = saved['metadata']

    @torch.inference_mode()
    def prepare_frame(self, image, radius):
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError('Example radius must be positive and finite.')
        image = np.asarray(image)
        if image.dtype != np.float32 or image.ndim != 3 or image.shape[2] != 3:
            image = preprocess_image(image, 'RGB')
        if not image.size or not np.isfinite(image).all() or image.min() < 0 or image.max() > 1:
            raise ValueError('Joint image input must contain normalized RGB pixels.')
        scale = NORMALIZED_RADIUS/radius; resized = scaled_image(image, scale)
        height, width = resized.shape[:2]
        nh, nw = math.ceil(height/CORE), math.ceil(width/CORE)
        padded = cv2.copyMakeBorder(resized, HALO, nh*CORE-height+HALO,
                                   HALO, nw*CORE-width+HALO, cv2.BORDER_CONSTANT, value=PADDING_RGB)
        canvas = torch.empty((1, 32, nh*CORE//STRIDE, nw*CORE//STRIDE))
        for y in range(nh):
            for x in range(nw):
                tile = padded[y*CORE:y*CORE+TILE, x*CORE:x*CORE+TILE]
                features = self.network.decode(self.network.prefix_maps(input_tensor(tile[None])))
                crop = features[:, :, HALO//STRIDE:(HALO+CORE)//STRIDE, HALO//STRIDE:(HALO+CORE)//STRIDE]
                canvas[:, :, y*CORE//STRIDE:(y+1)*CORE//STRIDE, x*CORE//STRIDE:(x+1)*CORE//STRIDE] = crop
        return {'features': canvas[:, :, :math.ceil(height/STRIDE), :math.ceil(width/STRIDE)],
                'scale': scale, 'radius': float(radius), 'image_shape': tuple(image.shape[:2])}

    @torch.inference_mode()
    def predict_prepared(self, prepared, examples, protected=(), threshold=.5):
        if not examples or len(examples) > 2:
            raise ValueError('The joint detector requires one or two supplied examples.')
        if not 0 <= threshold <= 1 or not math.isfinite(threshold):
            raise ValueError('Confidence threshold must be between zero and one.')
        if not math.isclose(float(np.median([c.radius for c in examples])), prepared['radius'], rel_tol=1e-8):
            raise ValueError('Prepared frame scale differs from the selected examples.')
        scale = prepared['scale']; height, width = prepared['image_shape']
        for circle in examples:
            if not (0 <= circle.x < width and 0 <= circle.y < height):
                raise ValueError('Examples must lie inside the current original frame.')
        coordinates = torch.tensor([[[(c.x+.5)*scale/STRIDE-.5/STRIDE,
                                       (c.y+.5)*scale/STRIDE-.5/STRIDE, c.radius*scale/STRIDE]
                                      for c in examples]], dtype=torch.float32)
        predicted = self.network.predictions(prepared['features'], coordinates)
        probabilities = predicted['logits'].sigmoid()
        peaks = (probabilities == F.max_pool2d(probabilities, 3, stride=1, padding=1)) & (probabilities >= threshold)
        yy, xx = torch.where(peaks[0, 0]); values = probabilities[0, 0, yy, xx]
        order = torch.argsort(values, descending=True, stable=True)
        accepted = []; known = list(protected)+list(examples)
        for rank in order:
            y, x = int(yy[rank]), int(xx[rank])
            ox, oy = predicted['offset'][0, :, y, x].tolist()
            circle = Circle((STRIDE*(x+ox)+.5)/scale-.5, (STRIDE*(y+oy)+.5)/scale-.5,
                            prepared['radius']*math.exp(float(predicted['log_radius'][0, 0, y, x])))
            if (0 <= circle.x < width and 0 <= circle.y < height and
                    not any(same_object(circle, old) for old in known) and
                    not any(same_object(circle, old) for old, _ in accepted)):
                accepted.append((circle, float(values[rank])))
        return [{'circle': asdict(circle), 'score': score} for circle, score in accepted]

    def predict(self, image, examples, protected=(), threshold=.5):
        if not examples or len(examples) > 2:
            raise ValueError('The joint detector requires one or two supplied examples.')
        validate_examples(image, examples)
        return self.predict_prepared(self.prepare_frame(image, float(np.median([c.radius for c in examples]))),
                                     examples, protected, threshold)

    def __call__(self, image, examples, existing=(), method=None, threshold=.5, encoder=None, head=None):
        return self.predict(image, examples, existing, threshold)
