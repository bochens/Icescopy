"""Official pretrained FamNet inference, without fitting or test-time adaptation.

FamNet predicts a density map and its sum. Converting that map into circles is
a separate fixed heuristic; it is not a learned cell-localization output.
"""
from __future__ import annotations

import ast
from dataclasses import asdict
import importlib.util
import math
from pathlib import Path
import types
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, maximum_filter
import torch
import torch.nn.functional as F
import torchvision
from torchvision import transforms

from detector import Circle, preprocess_image, same_object, validate_examples
from hybrid_data import sha256


PEAK_RULE = {'smoothing_sigma_example_radii': .1, 'minimum_smoothing_sigma_pixels': .75,
             'local_maximum_window_example_radii': .6, 'exemplar_peak_region_radii': .5,
             'relative_exemplar_peak_cutoff': .25,
             'duplicate_rule': 'Existing same_object distance <0.9*(r1+r2).',
             'choice': 'Fixed before viewing density predictions; no ground-truth count or labels choose peaks.'}
BACKBONE_SHA256 = '0676ba61b6795bbe1773cffd859882e5e297624d384b6993f7c9e683e722fb8a'
REGRESSOR_SHA256 = '9fd1b35d7f9f4c1af736e4562389dd16ec2ce70a4b9c68dc61454aa631cc17c1'


def official_modules(folder):
    """Run the authors' inference definitions unchanged, omitting plotting imports.

    The private runtime has no matplotlib. Selecting exact AST definitions
    avoids adding a plotting dependency; resize/correlation expressions are
    neither rewritten nor approximated. The full original files are retained.
    """
    folder = Path(folder)
    spec = importlib.util.spec_from_file_location('famnet_official_model', folder/'model.py')
    model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
    wanted = {'MAPS', 'Scales', 'MIN_HW', 'MAX_HW', 'IM_NORM_MEAN', 'IM_NORM_STD',
              'Normalize', 'Transform', 'resizeImage', 'extract_features'}
    selected = []
    for node in ast.parse((folder/'utils.py').read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets):
            selected.append(node)
    utility = types.ModuleType('famnet_official_inference_utils')
    utility.__dict__.update(torch=torch, F=F, math=math, transforms=transforms, np=np, cv2=cv2)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(folder/'utils.py'), 'exec'), utility.__dict__)
    if utility.MAX_HW != 1584 or utility.MAPS != ['map3', 'map4'] or utility.Scales != [.9, 1.1]:
        raise ValueError('Official FamNet inference defaults differ from the reviewed version.')
    return model, utility


def input_sample(image, examples, utility):
    image = np.asarray(image)
    if image.dtype != np.float32 or image.ndim != 3 or image.shape[2] != 3:
        image = preprocess_image(image, 'RGB')
    if not image.size or not np.isfinite(image).all() or image.min() < 0 or image.max() > 1:
        raise ValueError('Expected finite normalized RGB current-frame pixels.')
    if not 1 <= len(examples) <= 2:
        raise ValueError('Supply one or two current-frame examples.')
    validate_examples(image, examples)
    height, width = image.shape[:2]
    boxes = [[max(0, round(c.y-c.radius)), max(0, round(c.x-c.radius)),
              min(height-1, round(c.y+c.radius)), min(width-1, round(c.x+c.radius))] for c in examples]
    pixels = Image.fromarray(np.rint(image*255).astype(np.uint8))
    sample = utility.Transform({'image': pixels, 'lines_boxes': boxes})
    return sample, {'original_shape': [height, width], 'processed_shape': list(sample['image'].shape[-2:]),
                    'original_boxes_yxyx': boxes, 'processed_boxes': sample['boxes'].tolist()}


def density_circles(density, original_shape, processed_shape, examples, protected=(), rule=PEAK_RULE):
    """Extract peaks using supplied example sizes/density, never true object count."""
    density = np.asarray(density, np.float32)
    if density.ndim != 2 or not np.isfinite(density).all() or (density < 0).any():
        raise ValueError('A finite nonnegative2Ddensity map is required.')
    h, w = processed_shape; original_h, original_w = original_shape
    if not examples or min(h, w, original_h, original_w) <= 0 or density.shape[0] < h or density.shape[1] < w:
        raise ValueError('Density/image geometry is incompatible.')
    density = density[:h, :w]  # The official sum still includes any final padded cells.
    sx, sy = w/original_w, h/original_h
    radius = float(np.median([c.radius for c in examples])); mapped_radius = radius*math.sqrt(sx*sy)
    smooth = gaussian_filter(density, max(rule['minimum_smoothing_sigma_pixels'], rule['smoothing_sigma_example_radii']*mapped_radius))
    yy, xx = np.mgrid[:h, :w]
    exemplar_peaks = []
    for c in examples:
        cx, cy = (c.x+.5)*sx-.5, (c.y+.5)*sy-.5
        mask = ((xx-cx)/sx)**2+((yy-cy)/sy)**2 <= (rule['exemplar_peak_region_radii']*c.radius)**2
        exemplar_peaks.append(float(smooth[mask].max()) if mask.any() else 0.)
    reference = float(np.median(exemplar_peaks))
    if reference <= 0:
        return [], {'reference_peak': reference, 'exemplar_peaks': exemplar_peaks, 'cutoff': None,
                    'reason': 'No positive density in supplied exemplar regions.'}
    cutoff = reference*rule['relative_exemplar_peak_cutoff']
    half_window = max(1, int(math.floor(mapped_radius*rule['local_maximum_window_example_radii'])))
    peaks = (smooth == maximum_filter(smooth, size=2*half_window+1)) & (smooth >= cutoff) & (smooth > 0)
    y, x = np.where(peaks); order = np.argsort(-smooth[y, x], kind='stable')
    known = list(protected)+list(examples); accepted = []
    for index in order:
        candidate = Circle((float(x[index])+.5)/sx-.5, (float(y[index])+.5)/sy-.5, radius)
        if any(same_object(candidate, c) for c in known) or any(same_object(candidate, c) for c, _ in accepted):
            continue
        accepted.append((candidate, float(smooth[y[index], x[index]])))
    return [{'circle': asdict(c), 'score': score} for c, score in accepted], {
        'reference_peak': reference, 'exemplar_peaks': exemplar_peaks, 'cutoff': cutoff,
        'raw_peak_candidates': len(order), 'scores_are_probabilities': False}


class FamNetDetector:
    def __init__(self, official_root, backbone_weights, threads=4):
        torch.set_num_threads(threads); cv2.setNumThreads(threads)
        self.official_root = Path(official_root); self.backbone_weights = Path(backbone_weights)
        if sha256(self.backbone_weights) != BACKBONE_SHA256:
            raise ValueError('Expected the pinned ImageNetV1 ResNet50 weights.')
        model, self.utility = official_modules(self.official_root)
        state = torch.load(self.backbone_weights, map_location='cpu', weights_only=True)
        resnet = torchvision.models.resnet50(weights=None); resnet.load_state_dict(state, strict=True)
        # Replace only the legacy implicit download with the verified localV1
        # state. The instantiated authors' forward/correlation/regressor code
        # is otherwise unchanged.
        with patch.object(torchvision.models, 'resnet50', return_value=resnet):
            self.backbone = model.Resnet50FPN().eval()
        self.regressor = model.CountRegressor(6, pool='mean').eval()
        self.regressor_path = self.official_root/'data/pretrainedModels/FamNet_Save1.pth'
        if sha256(self.regressor_path) != REGRESSOR_SHA256:
            raise ValueError('Expected the pinned official FamNet_Save1 weights.')
        self.regressor.load_state_dict(torch.load(self.regressor_path, map_location='cpu', weights_only=True), strict=True)
        self.backbone.requires_grad_(False); self.regressor.requires_grad_(False)
        used = {id(p): p for module in (self.backbone.conv1, self.backbone.conv2, self.backbone.conv3, self.backbone.conv4)
                for p in module.parameters()}
        self.provenance = {'adaptation': False, 'training_steps': 0, 'cpu_threads': threads,
                           'backbone_weights': {'path': str(self.backbone_weights.resolve()), 'sha256': sha256(self.backbone_weights),
                                                'bytes': self.backbone_weights.stat().st_size, 'variant': 'ResNet50 ImageNetV1'},
                           'regressor_weights': {'path': str(self.regressor_path.resolve()), 'sha256': sha256(self.regressor_path),
                                                 'bytes': self.regressor_path.stat().st_size},
                           'parameters': {'full_registered_backbone': sum(p.numel() for p in self.backbone.parameters()),
                                          'used_backbone_forward': sum(p.numel() for p in used.values()),
                                          'density_regressor': sum(p.numel() for p in self.regressor.parameters())},
                           'upstream_file_sha256': {name: sha256(self.official_root/name) for name in ('model.py', 'utils.py', 'demo.py', 'LICENSE')},
                           'peak_rule': PEAK_RULE}

    @torch.inference_mode()
    def predict_density(self, image, examples):
        sample, geometry = input_sample(image, examples, self.utility)
        features = self.utility.extract_features(self.backbone, sample['image'].unsqueeze(0),
                                                sample['boxes'].unsqueeze(0), self.utility.MAPS, self.utility.Scales)
        output = self.regressor(features)
        density = output[0, 0].cpu().numpy()
        return density, float(output.sum()), geometry

    def predict(self, image, examples, protected=()):
        density, count, geometry = self.predict_density(image, examples)
        predictions, localization = density_circles(density, geometry['original_shape'], geometry['processed_shape'], examples, protected)
        return {'predictions': predictions, 'density': density, 'density_count_including_examples': count,
                'geometry': geometry, 'localization': localization}
