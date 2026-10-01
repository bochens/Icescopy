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
    from .image_samples import read_rgb, sample_points, suppress_centers, SAMPLER_VERSION, _usable, _negative_proposals
else:
    from data import _read_source
    from image_samples import read_rgb, sample_points, suppress_centers, SAMPLER_VERSION, _usable, _negative_proposals

FORMAT = "icescopy-opencv-center-forest-v1"
FEATURE_VERSION = "gray-color-layout-gradient-rings-v1"
DEFAULT_THRESHOLD = 0.55


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
