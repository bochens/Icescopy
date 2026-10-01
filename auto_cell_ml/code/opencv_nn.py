"""Train one small OpenCV neural network on raw RGB patches from an original image.

The signed output is a center score, not a probability. No augmented training
images are generated, and circle proposals never restrict dense inference.
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
    from .image_samples import read_rgb, sample_points, suppress_centers, SAMPLER_VERSION
else:
    from data import _read_source
    from image_samples import read_rgb, sample_points, suppress_centers, SAMPLER_VERSION

FORMAT = "icescopy-opencv-ann-center-v1"
INPUT_VERSION = "rgb15x15-span3r-minus1to1-v1"
LAYERS = np.array([15 * 15 * 3, 32, 16, 1], np.int32)
TRAIN_FLAGS = cv2.ml.ANN_MLP_NO_INPUT_SCALE | cv2.ml.ANN_MLP_NO_OUTPUT_SCALE
DEFAULT_THRESHOLD = 0.0
SUPPRESSION_RULE = "Reject lower-score centers separated by less than the smaller radius"


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pixels(image):
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or not image.size:
        raise ValueError("Expected a nonempty RGB uint8 image or decoded video frame")
    return image.astype(np.float32) / 127.5 - 1


def _patches(pixels, points, radius):
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("radius must be finite and positive")
    points = np.asarray(points, np.float32).reshape(-1, 2)
    if len(points) >= 32767 or not np.isfinite(points).all():
        raise ValueError("Patch batches must have fewer than 32767 finite coordinates")
    if len(points) == 0:
        return np.empty((0, int(LAYERS[0])), np.float32)
    axis = np.linspace(-1.5 * radius, 1.5 * radius, 15, dtype=np.float32)
    dy, dx = np.meshgrid(axis, axis, indexing="ij")
    mx = np.ascontiguousarray(points[:, :1] + dx.ravel())
    my = np.ascontiguousarray(points[:, 1:2] + dy.ravel())
    patches = cv2.remap(pixels, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return np.ascontiguousarray(patches.reshape(len(points), -1), dtype=np.float32)


def pixel_patches(image, points, radius):
    """Return row-major 15x15 RGB samples spanning +/-1.5 radii, in [-1,1]."""
    return _patches(_pixels(image), points, radius)


def fit(manifest, output, *, setup, max_samples=30000, max_iter=100, seed=0, threads=4):
    """Fit one 675-32-16-1 network from the trusted original saved frame only."""
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if min(max_samples, max_iter, threads) < 1 or not 0 <= seed < 2**31:
        raise ValueError("Training settings must be positive; seed must be a nonnegative int32")
    cv2.setNumThreads(threads)
    cv2.setRNGSeed(seed)
    start = time.perf_counter()
    image, circles, source = _read_source(manifest, setup)
    if not len(circles):
        raise ValueError("Original training image must contain marked circles")
    radius = float(np.median(np.asarray(circles)[:, 2]))
    points, labels, counts = sample_points(circles, np.ones(image.shape[:2], bool), budget=max_samples,
                                          seed=seed, image=image, radius=radius, return_details=True)
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError("Training requires positive and negative center examples")
    pixels = _pixels(image)
    features = np.concatenate([_patches(pixels, points[i:i + 4096], radius)
                               for i in range(0, len(points), 4096)])
    targets = (2 * labels.astype(np.float32) - 1).reshape(-1, 1)
    negatives = points[labels == 0]
    coverage, _, _ = np.histogram2d(negatives[:, 1], negatives[:, 0],
                                    bins=(np.linspace(0, image.shape[0], 9), np.linspace(0, image.shape[1], 9)))
    preparation_seconds = time.perf_counter() - start
    model = cv2.ml.ANN_MLP_create()
    model.setLayerSizes(LAYERS)
    model.setActivationFunction(cv2.ml.ANN_MLP_SIGMOID_SYM, 1, 1)
    model.setTrainMethod(cv2.ml.ANN_MLP_RPROP)
    # With 675 correlated raw pixels, default steps saturated every hidden unit
    # in a controlled target/distractor check. Bound each weight-vector update
    # by scaling the initial and maximum per-weight steps with input width.
    model.setRpropDW0(0.1 / math.sqrt(int(LAYERS[0])))
    model.setRpropDWMax(1 / math.sqrt(int(LAYERS[0])))
    model.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, max_iter, 0))
    train_data = cv2.ml.TrainData_create(features, cv2.ml.ROW_SAMPLE, targets)
    fitting_start = time.perf_counter()
    if not model.train(train_data, TRAIN_FLAGS):
        raise RuntimeError("OpenCV neural-network training failed")
    fitting_seconds = time.perf_counter() - fitting_start
    check_start = time.perf_counter()
    fitted_scores = np.concatenate([_scores(model, features[i:i + 4096])
                                    for i in range(0, len(features), 4096)])
    training_check = {"mean_squared_error": float(np.mean((fitted_scores - targets[:, 0]) ** 2)),
                      "threshold": DEFAULT_THRESHOLD, "positive_total": int(labels.sum()),
                      "positive_accepted": int(((labels == 1) & (fitted_scores >= DEFAULT_THRESHOLD)).sum()),
                      "negative_total": int((labels == 0).sum()),
                      "negative_accepted": int(((labels == 0) & (fitted_scores >= DEFAULT_THRESHOLD)).sum()),
                      "note": "These are fitted training samples, not independent evaluation labels"}
    training_check_seconds = time.perf_counter() - check_start
    output.mkdir(parents=True, exist_ok=False)
    path = output / "model.xml.gz"
    model.save(str(path))
    metadata = {"format": FORMAT, "input_version": INPUT_VERSION, "setup": setup,
                "recording_id": source["recording_id"], "source": source,
                "training_manifest_sha256": _hash(manifest), "opencv_version": cv2.__version__,
                "model_sha256": _hash(path), "model_bytes": path.stat().st_size,
                "sampler_version": SAMPLER_VERSION, "training_image_count": 1, "augmentation": False,
                "fixed_radius": radius, "radius_rule": "median original user-marked radius",
                "input_transform": "15x15 uniformly spaced raw RGB pixels over +/-1.5r; pixel/127.5-1; bilinear sampling; reflected borders",
                "threshold": DEFAULT_THRESHOLD, "score_meaning": "signed center score, not a probability",
                "center_suppression": SUPPRESSION_RULE, "sample_count": len(labels),
                "positive_count": int(labels.sum()), "negative_count": int(len(labels) - labels.sum()),
                "positive_support": "max(1.5 pixels, 0.15 * marked radius)",
                "negative_sampling_counts": counts,
                "negative_frame_coverage": {"rows": 8, "columns": 8, "occupied_tiles": int((coverage > 0).sum()),
                                            "sample_counts": coverage.astype(int).tolist()},
                "sampling_note": "Unique positive support coordinates; sampled counts are not image class prevalence. No class balancing or score calibration.",
                "preparation_seconds": preparation_seconds, "fit_seconds": fitting_seconds,
                "training_sample_check": training_check, "training_check_seconds": training_check_seconds,
                "total_seconds": time.perf_counter() - start,
                "config": {"max_samples": max_samples, "max_iter": max_iter, "epsilon_early_stop": False,
                           "seed": seed, "threads": threads, "layers": LAYERS.tolist(),
                           "activation": "SIGMOID_SYM", "activation_alpha": 1, "activation_beta": 1,
                           "training_method": "RPROP", "train_flags": int(TRAIN_FLAGS),
                           "rprop_initial_step": model.getRpropDW0(), "rprop_max_step": model.getRpropDWMax(),
                           "rprop_step_rule": "initial=0.1/sqrt(input_count), max=1/sqrt(input_count), to limit raw-pixel hidden saturation",
                           "input_scaling": False, "output_scaling": False}}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    return path, metadata


def load_model(model_path):
    path = Path(model_path)
    if path.is_dir():
        path = path / "model.xml.gz"
    metadata = json.loads((path.parent / "metadata.json").read_text())
    if metadata.get("format") != FORMAT or metadata.get("input_version") != INPUT_VERSION:
        raise ValueError("Unsupported OpenCV network or RGB patch format")
    if _hash(path) != metadata["model_sha256"]:
        raise ValueError("Network file does not match metadata SHA-256")
    model = cv2.ml.ANN_MLP_load(str(path))
    if not model.isTrained() or not np.array_equal(model.getLayerSizes().ravel(), LAYERS):
        raise ValueError("Network must have the saved 675-32-16-1 layers")
    return model, metadata


def _scores(model, features):
    scores = model.predict(features)[1].reshape(-1)
    if not np.isfinite(scores).all():
        raise ValueError("Network returned nonfinite center scores")
    return scores


def detect(model, image, *, radius, threshold=DEFAULT_THRESHOLD, stride=2, batch_size=4096):
    """Score every one- or two-pixel grid location without a candidate gate."""
    if not math.isfinite(threshold) or stride not in (1, 2) or not 1 <= batch_size < 32767:
        raise ValueError("threshold must be finite; stride 1 or 2; batch_size 1..32766")
    pixels = _pixels(image)
    ys, xs = np.arange(0, image.shape[0], stride), np.arange(0, image.shape[1], stride)
    scores = np.empty((len(ys), len(xs)), np.float32)
    for start in range(0, scores.size, batch_size):
        index = np.arange(start, min(start + batch_size, scores.size))
        points = np.column_stack((xs[index % len(xs)], ys[index // len(xs)]))
        scores.flat[start:start + len(index)] = _scores(model, _patches(pixels, points, radius))
    maxima = (scores >= threshold) & (scores == cv2.dilate(scores, np.ones((3, 3), np.uint8)))
    return suppress_centers([{"x": int(xs[col]), "y": int(ys[row]), "radius": float(radius),
                              "score": float(scores[row, col])} for row, col in np.argwhere(maxima)], score_key="score")


def evaluate(model_path, image_path, output, *, radius=None, threshold=DEFAULT_THRESHOLD, stride=2, threads=4):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if threads < 1:
        raise ValueError("threads must be positive")
    cv2.setNumThreads(threads)
    model, metadata = load_model(model_path)
    image = read_rgb(image_path)
    radius = metadata["fixed_radius"] if radius is None else radius
    start = time.perf_counter()
    circles = detect(model, image, radius=radius, threshold=threshold, stride=stride)
    result = {"setup": metadata["setup"], "image_name": Path(image_path).name,
              "image_sha256": _hash(image_path), "model_sha256": metadata["model_sha256"],
              "width": image.shape[1], "height": image.shape[0], "threshold": threshold,
              "stride": stride, "fixed_radius": radius, "count": len(circles), "circles": circles,
              "inference_seconds": time.perf_counter() - start, "evaluation_labels_used": False,
              "score_meaning": "signed center score, not a probability", "center_suppression": SUPPRESSION_RULE}
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
    for name, default in (("max-samples", 30000), ("max-iter", 100), ("seed", 0), ("threads", 4)):
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
