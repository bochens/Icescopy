"""Train one portable OpenCV forest to score cell centers directly from RGB patches.

Only padding is unknown. Unmarked valid centers are negative. Inference uses
the original median marked radius, optionally overridden, and uncalibrated
positive-tree vote fractions. Circle proposals supply training negatives only;
inference never calls a circle finder or reads evaluation labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np

if __package__:
    from .data import _read_source
else:
    from data import _read_source

FORMAT = "icescopy-opencv-center-forest-v1"
FEATURE_VERSION = "gray-color-layout-gradient-rings-v1"
SAMPLER_VERSION = "original-image-circle-edge-negatives-v2"
DEFAULT_THRESHOLD = 0.55


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def _prepare(image, radius, valid=None):
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("Expected a nonempty RGB uint8 image or decoded video frame")
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("radius must be finite and positive")
    mask = np.ones(image.shape[:2], np.float32) if valid is None else valid.astype(np.float32)
    rgb = image.astype(np.float32) / 255
    sigma = max(0.6, 0.08 * radius)
    # Normalize the blur by valid-pixel weight so black padding cannot alter
    # known pixels. Missing patch samples later use the candidate's own value.
    weight = cv2.GaussianBlur(mask, (0, 0), sigma)
    color = cv2.GaussianBlur(rgb * mask[..., None], (0, 0), sigma) / np.maximum(weight[..., None], 1e-6)
    gray = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY)
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    return gray, color, cv2.magnitude(gx, gy), mask


def _features(prepared, points, radius):
    """Extract only requested coordinates: spatial layout, color, and texture."""
    gray, color, gradient, mask = prepared
    points = np.asarray(points, np.float32).reshape(-1, 2)
    axis = np.linspace(-1.25, 1.25, 5, dtype=np.float32)
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    grid = np.column_stack((xx.ravel(), yy.ravel()))

    def sample(values, offsets):
        coords = points[:, None, :] + radius * np.asarray(offsets, np.float32)[None, :, :]
        mx, my = np.ascontiguousarray(coords[..., 0]), np.ascontiguousarray(coords[..., 1])
        values_at = cv2.remap(values, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        known = cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101) >= 0.999
        center = cv2.remap(values, points[:, :1], points[:, 1:2], cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REFLECT_101)
        return np.where(known if values.ndim == 2 else known[..., None], values_at, center)

    layout = sample(gray, grid)
    mean = layout.mean(axis=1, keepdims=True)
    inner = sample(gray, grid * 0.5)
    ca = np.array([-1.25, 0, 1.25], np.float32)
    cy, cx = np.meshgrid(ca, ca, indexing="ij")
    angles = np.arange(8) * (math.pi / 4)
    ring_offsets = np.concatenate([r * np.column_stack((np.cos(angles), np.sin(angles)))
                                   for r in (0.5, 1.0, 1.5)])
    rings = sample(gray, ring_offsets).reshape(len(points), 3, 8)
    return np.ascontiguousarray(np.concatenate([
        layout, layout - mean, inner - mean,
        sample(color, np.column_stack((cx.ravel(), cy.ravel()))).reshape(len(points), -1),
        sample(gradient, grid), rings.reshape(len(points), -1) - mean,
        rings.mean(axis=2) - mean, rings.std(axis=2),
    ], axis=1), dtype=np.float32)


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


def fit(manifest, output, *, setup, max_samples=80000, trees=64, max_depth=16, seed=0, threads=4):
    """Train directly from one original labeled image selected in datasets.json.

    The trusted session reader verifies source identity, hashes, and marks.
    No transformed images, generated manifests, or evaluation data are read.
    """
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if min(max_samples, trees, max_depth, threads) < 1 or seed < 0:
        raise ValueError("Training settings must be positive and seed nonnegative")
    cv2.setNumThreads(threads)
    cv2.setRNGSeed(seed)
    start = time.perf_counter()
    image, circles, source = _read_source(manifest, setup)
    if not len(circles):
        raise ValueError("Original training image must contain marked circles")
    radius = float(np.median(np.asarray(circles)[:, 2]))
    valid = np.ones(image.shape[:2], bool)
    points, labels, counts = sample_points(circles, valid, budget=max_samples, seed=seed,
                                          image=image, radius=radius, return_details=True)
    negatives = points[labels == 0]
    coverage, _, _ = np.histogram2d(negatives[:, 1], negatives[:, 0],
                                    bins=(np.linspace(0, image.shape[0], 9), np.linspace(0, image.shape[1], 9)))
    prepared = _prepare(image, radius)
    # cv2.remap supports fewer than 32767 rows; also bound temporary memory.
    features = np.concatenate([_features(prepared, points[i:i + 4096], radius)
                               for i in range(0, len(points), 4096)])
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError("Training requires both positive and negative center examples")
    sampling_seconds = time.perf_counter() - start
    forest = cv2.ml.RTrees_create()
    forest.setMaxDepth(max_depth)
    forest.setMinSampleCount(3)
    forest.setActiveVarCount(max(1, int(math.sqrt(features.shape[1]))))
    forest.setCalculateVarImportance(False)
    forest.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, trees, 0))
    fitting_start = time.perf_counter()
    if not forest.train(features, cv2.ml.ROW_SAMPLE, labels):
        raise RuntimeError("OpenCV forest training failed")
    fitting_seconds = time.perf_counter() - fitting_start
    output.mkdir(parents=True, exist_ok=False)
    model_path = output / "model.xml.gz"
    forest.save(str(model_path))
    metadata = {"format": FORMAT, "feature_version": FEATURE_VERSION, "setup": setup,
                "recording_id": source["recording_id"], "source": source,
                "sampler_version": SAMPLER_VERSION, "training_image_count": 1, "augmentation": False,
                "opencv_version": cv2.__version__, "training_manifest_sha256": _hash(manifest),
                "model_sha256": _hash(model_path), "model_bytes": model_path.stat().st_size,
                "fixed_radius": radius, "radius_rule": "median original user-marked radius",
                "center_suppression": "Reject lower-vote centers separated by less than the smaller radius",
                "threshold": DEFAULT_THRESHOLD, "positive_support": "max(1.5 pixels, 0.15 * marked radius)",
                "feature_count": features.shape[1], "sample_count": len(labels), "negative_sampling_counts": counts,
                "negative_frame_coverage": {"rows": 8, "columns": 8, "occupied_tiles": int((coverage > 0).sum()),
                                            "sample_counts": coverage.astype(int).tolist()},
                "positive_count": int(labels.sum()), "negative_count": int(len(labels) - labels.sum()),
                "sampling_seconds": sampling_seconds, "fit_seconds": fitting_seconds,
                "total_seconds": time.perf_counter() - start,
                "sampling_note": "Unique positive support coordinates; sampled class counts are not image class prevalence. No balancing or calibration.",
                "proposal_rule": "Training only: Hough dp=1, minDist=0.7r, param1=80, param2=8, radius=0.7..1.3r; top-decile local gradient maxima; up to half negatives",
                "config": {"max_samples": max_samples, "trees": trees, "max_depth": max_depth,
                           "min_sample_count": 3, "active_var_count": forest.getActiveVarCount(),
                           "seed": seed, "threads": threads, "class_priors": "empirical sampled counts"}}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    return model_path, metadata


def load_model(model_path):
    model_path = Path(model_path)
    if model_path.is_dir():
        model_path = model_path / "model.xml.gz"
    metadata = json.loads((model_path.parent / "metadata.json").read_text())
    if metadata.get("format") != FORMAT or metadata.get("feature_version") != FEATURE_VERSION:
        raise ValueError("Unsupported forest or patch feature format")
    if _hash(model_path) != metadata["model_sha256"]:
        raise ValueError("Forest file does not match metadata SHA-256")
    forest = cv2.ml.RTrees_load(str(model_path))
    if not forest.isClassifier() or forest.getVarCount() != metadata["feature_count"]:
        raise ValueError("Forest must classify centers using the saved feature count")
    return forest, metadata


def _scores(forest, features):
    votes = forest.getVotes(features, 0)
    positive = np.flatnonzero(votes[0] == 1)
    if len(positive) != 1:
        raise ValueError("Forest must contain positive center class 1")
    return votes[1:, positive[0]].astype(np.float32) / np.maximum(1, votes[1:].sum(axis=1))


def suppress_centers(circles):
    """Keep the highest vote; distinct overlapping cells a radius apart survive."""
    found = []
    for circle in sorted(circles, key=lambda c: c["confidence"], reverse=True):
        if all(math.hypot(circle["x"] - c["x"], circle["y"] - c["y"])
               >= min(circle["radius"], c["radius"]) for c in found):
            found.append(circle)
    return sorted(found, key=lambda c: (c["y"], c["x"]))


def detect(forest, image, *, radius, threshold=DEFAULT_THRESHOLD, stride=2, batch_size=4096):
    """Score a dense <=2-pixel grid, retain local maxima, and merge close centers."""
    if not 0 < threshold < 1 or stride not in (1, 2) or batch_size < 1:
        raise ValueError("threshold must be between 0 and 1; stride 1 or 2; batch_size positive")
    prepared = _prepare(image, radius)
    h, w = image.shape[:2]
    ys, xs = np.arange(0, h, stride), np.arange(0, w, stride)
    scores = np.empty((len(ys), len(xs)), np.float32)
    for start in range(0, scores.size, batch_size):
        indices = np.arange(start, min(start + batch_size, scores.size))
        points = np.column_stack((xs[indices % len(xs)], ys[indices // len(xs)]))
        scores.flat[start:start + len(indices)] = _scores(forest, _features(prepared, points, radius))
    maxima = (scores >= threshold) & (scores == cv2.dilate(scores, np.ones((3, 3), np.uint8)))
    candidates = np.argwhere(maxima)
    return suppress_centers([{"x": int(xs[col]), "y": int(ys[row]), "radius": float(radius),
                              "confidence": float(scores[row, col])} for row, col in candidates])


def evaluate(model_path, image_path, output, *, radius=None, threshold=DEFAULT_THRESHOLD, stride=2, threads=4):
    """Save predictions and an overlay for an unlabeled separate image."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if threads < 1:
        raise ValueError("threads must be positive")
    cv2.setNumThreads(threads)
    forest, metadata = load_model(model_path)
    image = read_rgb(image_path)
    radius = metadata["fixed_radius"] if radius is None else radius
    start = time.perf_counter()
    circles = detect(forest, image, radius=radius, threshold=threshold, stride=stride)
    result = {"setup": metadata["setup"], "image_name": Path(image_path).name,
              "image_sha256": _hash(image_path), "width": image.shape[1], "height": image.shape[0],
              "model_sha256": metadata["model_sha256"], "threshold": threshold, "stride": stride,
              "fixed_radius": radius, "inference_seconds": time.perf_counter() - start,
              "center_suppression": "Reject lower-vote centers separated by less than the smaller radius",
              "count": len(circles), "circles": circles, "evaluation_labels_used": False,
              "score_meaning": "fraction of trees voting for center; not calibrated accuracy"}
    output.mkdir(parents=True, exist_ok=False)
    (output / "predictions.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    preview = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    for c in circles:
        cv2.circle(preview, (c["x"], c["y"]), round(radius), (70, 255, 50), max(1, round(max(image.shape[:2]) / 850)))
    scale = min(1, 1600 / max(preview.shape[:2]))
    preview = cv2.resize(preview, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(output / "overlay.jpg"), preview, [cv2.IMWRITE_JPEG_QUALITY, 93]):
        raise OSError("Cannot save detection overlay")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("--manifest", type=Path, required=True)
    train.add_argument("--setup", required=True)
    train.add_argument("--output", type=Path, required=True)
    for name, default in (("max-samples", 80000), ("trees", 64), ("max-depth", 16), ("seed", 0), ("threads", 4)):
        train.add_argument("--" + name, type=int, default=default)
    infer = commands.add_parser("infer")
    infer.add_argument("--model", dest="model_path", type=Path, required=True)
    infer.add_argument("--image", dest="image_path", type=Path, required=True)
    infer.add_argument("--output", type=Path, required=True)
    infer.add_argument("--radius", type=float)
    infer.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    infer.add_argument("--stride", type=int, choices=(1, 2), default=2)
    infer.add_argument("--threads", type=int, default=4)
    args = vars(parser.parse_args())
    command = args.pop("command")
    try:
        result = fit(**args)[1] if command == "train" else evaluate(**args)
    except (ValueError, OSError, KeyError, cv2.error) as exc:
        parser.exit(2, f"{exc}\n")
    fields = ("sample_count", "positive_count", "negative_count", "fit_seconds", "model_bytes") if command == "train" else ("count", "fixed_radius", "inference_seconds")
    print(json.dumps({key: result[key] for key in fields}))


if __name__ == "__main__":
    main()
