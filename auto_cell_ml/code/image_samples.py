"""Shared original-image sampling and center suppression for CPU models."""
import math
from pathlib import Path

import cv2
import numpy as np

SAMPLER_VERSION = "original-image-circle-edge-negatives-v2"


def read_rgb(path):
    """Decode unchanged pixels; map the full uint16 range to uint8 RGB."""
    pixels = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if pixels is None:
        raise OSError(f"Cannot decode image: {path}")
    if pixels.dtype == np.uint16:
        pixels = np.rint(pixels.astype(np.float32) / 257).astype(np.uint8)
    if pixels.dtype != np.uint8:
        raise ValueError("Images must contain uint8 or uint16 pixels")
    if pixels.ndim == 2:
        return cv2.cvtColor(pixels, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(pixels, cv2.COLOR_BGRA2RGB if pixels.shape[2] == 4 else cv2.COLOR_BGR2RGB)


def _usable(points, valid):
    points = np.asarray(points).reshape(-1, 2)
    h, w = valid.shape
    inside = (points[:, 0] >= 0) & (points[:, 0] < w) & (points[:, 1] >= 0) & (points[:, 1] < h)
    ix = np.clip(np.rint(points[:, 0]).astype(int), 0, w - 1)
    iy = np.clip(np.rint(points[:, 1]).astype(int), 0, h - 1)
    return inside & valid[iy, ix]


def _negative_proposals(image, valid, radius):
    """Fixed training-only circle centers and strongest local edge locations."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (0, 0), max(0.6, 0.06 * radius))
    found = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=max(2, 0.7 * radius),
                             param1=80, param2=8, minRadius=max(2, math.floor(0.7 * radius)),
                             maxRadius=max(3, math.ceil(1.3 * radius)))
    centers = np.empty((0, 2), np.float32) if found is None else found[0, :, :2]
    jitter = radius * 0.1 * np.array([[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]])
    proposals = (centers[:, None, :] + jitter).reshape(-1, 2)
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    gradient = cv2.magnitude(gx, gy)
    known = cv2.erode(valid.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    values = gradient[known & (gradient > 0)]
    cutoff = max(16, float(np.quantile(values, 0.9))) if len(values) else math.inf
    edge = np.argwhere(known & (gradient >= cutoff) &
                       (gradient == cv2.dilate(gradient, np.ones((3, 3), np.uint8))))
    return proposals, edge[:, ::-1].astype(np.float32)


def sample_points(circles, valid, *, budget, seed=0, image=None, radius=None, return_details=False):
    """Exact centers, small jitter, and automatic/spatial/near-center negatives.

    The positive support is max(1.5 pixels, 15% of each marked radius), covering
    the worst 1.414-pixel quantization error of the two-pixel inference grid.
    Empty regions contribute only negatives. At most half the negative budget
    uses automatic proposals; remaining points retain broad spatial coverage.
    Positive coordinates are unique, not repeated to fill a class quota.
    """
    circles = np.asarray(circles, np.float32).reshape(-1, 3)
    if valid.ndim != 2 or valid.dtype != np.bool_ or not valid.size or not valid.any():
        raise ValueError("valid must be a nonempty Boolean mask with known pixels")
    if not np.isfinite(circles).all() or np.any(circles[:, 2] <= 0) or budget < 2:
        raise ValueError("Finite circles with positive radii and budget >=2 are required")
    centers = circles[_usable(circles[:, :2], valid)]
    if len(centers) >= budget:
        raise ValueError("Sampling budget must retain every exact center and negative examples")
    rng = np.random.default_rng(seed)
    tolerance = np.maximum(1.5, 0.15 * centers[:, 2])
    angles = np.arange(8) * math.pi / 4
    direction = np.column_stack((np.cos(angles), np.sin(angles)))
    jitter = np.concatenate([(centers[:, None, :2] + tolerance[:, None, None] * factor * direction).reshape(-1, 2)
                             for factor in (0.5, 0.85)])
    # Include neighboring two-pixel grid locations when within positive support.
    offsets = np.array([[0, 0], [0, 2], [2, 0], [2, 2]])
    quantized = (2 * np.floor(centers[:, None, :2] / 2) + offsets).reshape(-1, 2)
    distance = np.linalg.norm(quantized.reshape(-1, 4, 2) - centers[:, None, :2], axis=2)
    extras = np.concatenate((quantized[(distance <= tolerance[:, None]).ravel()], jitter))
    extras = extras[_usable(extras, valid)]
    # Keep exact labeled centers first and remove coincident support coordinates.
    positive_set = set(map(tuple, centers[:, :2]))
    extras = np.asarray([point for point in np.unique(extras.astype(np.float32), axis=0)
                         if tuple(point) not in positive_set], np.float32).reshape(-1, 2)
    rng.shuffle(extras)
    positive = np.concatenate((centers[:, :2], extras[:max(0, max(len(centers), budget // 3) - len(centers))]))
    remaining = budget - len(positive)
    h, w = valid.shape
    side = max(2, math.ceil(math.sqrt(2 * remaining)))
    yy, xx = np.meshgrid(np.linspace(0, h - 1, side), np.linspace(0, w - 1, side), indexing="ij")
    uniform = np.column_stack((xx.ravel(), yy.ravel()))
    near = np.concatenate([(centers[:, None, :2] + centers[:, None, 2:] * r * direction).reshape(-1, 2)
                           for r in (0.25, 0.5, 0.9, 1.3)])

    def negative(points):
        points = points[_usable(points, valid)]
        for center, tol in zip(centers[:, :2], tolerance):
            points = points[np.sum((points - center) ** 2, axis=1) > tol ** 2]
        rng.shuffle(points)
        return points

    proposal_budget = remaining // 2 if image is not None else 0
    circle_points, edge_points = np.empty((0, 2)), np.empty((0, 2))
    proposal_counts = {"circle_candidate_count": 0, "circle_proposal_pool": 0, "edge_proposal_pool": 0,
                       "eligible_circle_proposals": 0, "eligible_edge_proposals": 0}
    if image is not None:
        if image.shape[:2] != valid.shape or image.dtype != np.uint8 or image.shape[2:] != (3,):
            raise ValueError("Proposal image must be RGB uint8 and match the valid mask")
        radius = float(np.median(circles[:, 2])) if radius is None and len(circles) else radius
        if radius is None or not math.isfinite(radius) or radius <= 0:
            raise ValueError("Automatic proposals require a positive finite radius")
        cp, ep = _negative_proposals(image, valid, radius)
        eligible_cp, eligible_ep = negative(cp), negative(ep)
        proposal_counts = {"circle_candidate_count": len(cp) // 5, "circle_proposal_pool": len(cp),
                           "edge_proposal_pool": len(ep), "eligible_circle_proposals": len(eligible_cp),
                           "eligible_edge_proposals": len(eligible_ep)}
        circle_points = eligible_cp[:3 * proposal_budget // 4]
        edge_points = eligible_ep[:proposal_budget - len(circle_points)]
    baseline = negative(uniform)[:(remaining - proposal_budget) // 2]
    nearby = negative(near)[:remaining - proposal_budget - len(baseline)]
    negatives = np.concatenate((circle_points, edge_points, baseline, nearby))
    details = {"negative_circle_proposals": len(circle_points), "negative_edge_proposals": len(edge_points),
               "negative_spatial": len(baseline), "negative_near_marked": len(nearby), **proposal_counts}
    initial_negative_count = len(negatives)
    known_y, known_x = np.nonzero(valid)
    for _ in range(10):
        missing = remaining - len(negatives)
        if missing <= 0:
            break
        index = rng.integers(len(known_x), size=2 * missing)
        extra = negative(np.column_stack((known_x[index], known_y[index])))[:missing]
        negatives = np.concatenate((negatives, extra))
    if len(negatives) == 0:
        raise ValueError("Image has no sampled negative center outside positive support")
    details["negative_random"] = len(negatives) - initial_negative_count
    points = np.asarray(np.concatenate((positive, negatives)), np.float32)
    labels = np.concatenate((np.ones(len(positive), np.int32), np.zeros(len(negatives), np.int32)))
    return (points, labels, details) if return_details else (points, labels)


def suppress_centers(circles, *, score_key="confidence"):
    """Keep the highest score; distinct overlapping cells a radius apart survive."""
    found = []
    for circle in sorted(circles, key=lambda c: c[score_key], reverse=True):
        if all(math.hypot(circle["x"] - c["x"], circle["y"] - c["y"])
               >= min(circle["radius"], c["radius"]) for c in found):
            found.append(circle)
    return sorted(found, key=lambda c: (c["y"], c["x"]))
