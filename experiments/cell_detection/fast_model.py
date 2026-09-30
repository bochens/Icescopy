"""Separate CPU tree experiment using direct 32-pixel image measurements.

The original template and neural methods remain available. This module never
imports Torch. Tree scores are experimental rankings, not occupancy guarantees.
"""
from __future__ import annotations

from dataclasses import asdict
import math

import cv2
import numpy as np
from threadpoolctl import threadpool_limits

from detector import exclude_existing, patches, propose, same_object, unit_rows, validate_examples


DESCRIPTOR_VERSION = 1
MODEL_VERSION = 1
THREADS = 4
PROFILE_NAMES = [f'radial_{i}_{stat}' for i in range(13) for stat in ('mean', 'std')]
TEXTURE_NAMES = [f'{zone}_{stat}' for zone in ('inner', 'rim', 'outer')
                 for stat in ('gray_std', 'edge_mean', 'gray_p90_p10')]
TEXTURE_NAMES += [f'inner_outer_{channel}' for channel in ('red', 'green', 'blue')]
LOCAL_NAMES = PROFILE_NAMES + TEXTURE_NAMES
FEATURE_NAMES = ['gray_correlation', 'edge_correlation', 'quarter_turn_gray_correlation',
                 'quarter_turn_edge_correlation', 'edge_at_best_gray_rotation']
FEATURE_NAMES += [f'{kind}_{name}' for kind in ('candidate', 'example', 'difference') for name in LOCAL_NAMES]

_yy, _xx = np.mgrid[-1:1:32j, -1:1:32j]
_distance = np.hypot(_xx, _yy)
_rings = [(_distance >= low) & (_distance < high)
          for low, high in zip(np.linspace(0, 1.3, 14)[:-1], np.linspace(0, 1.3, 14)[1:])]
_zones = [_distance < .32, (_distance >= .32) & (_distance < .6),
          (_distance >= .6) & (_distance < 1.)]


def feature_bank(image, circles):
    """Measure image patches directly at 32 pixels; retain absolute intensities.

    Radii use the same 2.25-radius extent as the baseline. The radial profile
    captures the central liquid and surrounding holder separately. Zone texture
    measures help distinguish a smooth empty recess from a structured surface.
    No patch-wise brightness inversion or absolute gray correlation is used.
    """
    batch = patches(image, circles, size=32)
    appearance, edges, local = [], [], []
    for patch in batch:
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
        smooth = cv2.GaussianBlur(gray, (0, 0), .7)
        dx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
        dy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
        edge = np.hypot(dx, dy)
        appearance.append((smooth-smooth.mean()).ravel())
        edges.append((edge-edge.mean()).ravel())
        measurements = []
        for mask in _rings:
            values = smooth[mask]
            measurements.extend([float(values.mean()), float(values.std())])
        for mask in _zones:
            values = smooth[mask]
            measurements.extend([float(values.std()), float(edge[mask].mean()),
                                 float(np.percentile(values, 90)-np.percentile(values, 10))])
        measurements.extend((patch[_zones[0]].mean(axis=0)-patch[_zones[-1]].mean(axis=0)).tolist())
        local.append(measurements)
    return {'gray': unit_rows(np.asarray(appearance, np.float32).reshape(-1, 1024)),
            'edges': unit_rows(np.asarray(edges, np.float32).reshape(-1, 1024)),
            'local': np.asarray(local, np.float32).reshape(-1, len(LOCAL_NAMES))}


def pair_features(candidates, examples):
    """Quarter-turn tolerance plus signed and absolute local structure."""
    gray, edges = [], []
    with threadpool_limits(limits=THREADS):
        for turn in range(4):
            for key, destination in [('gray', gray), ('edges', edges)]:
                rotated = np.rot90(examples[key].reshape(-1, 32, 32), turn, axes=(1, 2))
                destination.append(candidates[key] @ rotated.reshape(-1, 1024).T)
    gray = np.stack(gray, axis=-1)
    edges = np.stack(edges, axis=-1)
    best = np.argmax(gray, axis=-1)
    correlation = np.stack([gray[:, :, 0], edges[:, :, 0], gray.max(axis=-1),
                            edges.max(axis=-1), np.take_along_axis(edges, best[..., None], axis=-1)[:, :, 0]], axis=-1)
    a, b = candidates['local'], examples['local']
    shape = (len(a), len(b), a.shape[1])
    return np.concatenate([correlation, np.broadcast_to(a[:, None, :], shape),
                           np.broadcast_to(b[None, :, :], shape),
                           np.abs(a[:, None, :]-b[None, :, :])], axis=-1).astype(np.float32)


def validate_model(bundle):
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    required = {'model_version', 'descriptor_version', 'feature_names', 'sklearn_version',
                'classifier', 'threshold', 'metadata'}
    if not isinstance(bundle, dict) or set(bundle) != required:
        raise ValueError('Malformed fast model bundle.')
    if bundle['model_version'] != MODEL_VERSION or bundle['descriptor_version'] != DESCRIPTOR_VERSION:
        raise ValueError('Incompatible fast model or image descriptor version.')
    if bundle['feature_names'] != FEATURE_NAMES or bundle['sklearn_version'] != sklearn.__version__:
        raise ValueError('Fast model requires its recorded features and scikit-learn version.')
    model = bundle['classifier']
    if (not isinstance(model, HistGradientBoostingClassifier) or
            getattr(model, 'n_features_in_', None) != len(FEATURE_NAMES) or
            not np.array_equal(getattr(model, 'classes_', None), [0, 1])):
        raise ValueError('Fast model must be a fitted two-class image classifier.')
    threshold = bundle['threshold']
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Invalid fast model threshold.')
    return bundle


def load_model(path):
    """Load a trusted locally generated joblib bundle; never load unknown files."""
    import joblib
    return validate_model(joblib.load(path))


def scores(candidates, examples, bundle):
    validate_model(bundle)
    pair = pair_features(candidates, examples)
    if not len(pair):
        return np.empty(0, np.float32)
    with threadpool_limits(limits=THREADS):
        values = bundle['classifier'].predict_proba(pair.reshape(-1, len(FEATURE_NAMES)))[:, 1]
    return values.reshape(pair.shape[:2]).max(axis=1)


def detect(image, examples, existing=(), method='fast', threshold=.75, encoder=None, head=None):
    """Signature matches the original detector for the single-frame boundary."""
    if method != 'fast' or encoder is not None:
        raise ValueError('Fast detection requires method=fast and no neural encoder.')
    validate_model(head)
    validate_examples(image, examples)
    protected = list(existing)+list(examples)
    radius = float(np.median([c.radius for c in examples]))
    candidates = exclude_existing(propose(image, radius), protected)
    if not candidates:
        return []
    values = scores(feature_bank(image, candidates), feature_bank(image, examples), head)
    accepted = []
    for i in np.argsort(-values):
        if values[i] >= threshold and not any(same_object(candidates[i], old) for old, _ in accepted):
            accepted.append((candidates[i], float(values[i])))
    return [{'circle': asdict(circle), 'score': value} for circle, value in accepted]
