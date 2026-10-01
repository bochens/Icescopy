"""Apply a trained setup model to one original image and save a circle overlay."""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import torch
from torch.nn import functional as F

from model import load_model


def read_rgb(path):
    with Image.open(path) as image:
        values = np.asarray(image)
        if values.dtype == np.uint16:
            image = Image.fromarray(np.rint(values.astype(np.float32) / 257).astype(np.uint8))
        return np.array(image.convert("RGB"))


def tile_intervals(length, size, overlap):
    """Each pixel belongs to one overlapping tile's central ownership interval."""
    if length < 1 or size < 1 or not 0 <= overlap < size:
        raise ValueError("Invalid tile dimensions")
    starts = list(range(0, max(length - size, 0) + 1, size - overlap))
    if starts[-1] != max(length - size, 0):
        starts.append(max(length - size, 0))
    boundaries = [0.0] + [(a + size + b) / 2 for a, b in zip(starts, starts[1:])] + [float(length)]
    return list(zip(starts, boundaries[:-1], boundaries[1:]))


@torch.inference_mode()
def detect(model, image, *, size=384, threshold=0.5, device="cpu", batch_size=4):
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("Expected an RGB uint8 image or decoded video frame")
    if size < 32 or size % 4 or not 0 < threshold < 1 or batch_size < 1:
        raise ValueError("Tile size must be at least 32 and a multiple of 4; threshold must be between 0 and 1")
    model.eval()
    height, width = image.shape[:2]
    tiles = [(x, y, left, right, top, bottom)
             for y, top, bottom in tile_intervals(height, size, size // 4)
             for x, left, right in tile_intervals(width, size, size // 4)]
    circles = []
    for start in range(0, len(tiles), batch_size):
        group = tiles[start:start + batch_size]
        arrays = []
        for x, y, *_ in group:
            patch = image[y:y + size, x:x + size]
            padded = np.zeros((size, size, 3), dtype=np.uint8)
            padded[:len(patch), :patch.shape[1]] = patch
            arrays.append(padded.transpose(2, 0, 1))
        pred = model(torch.from_numpy(np.stack(arrays)).to(device).float() / 255)
        confidence = pred["center"].sigmoid()
        maxima = (confidence >= threshold) & (confidence == F.max_pool2d(confidence, 3, 1, 1))
        offsets = pred["offsets"].cpu().numpy()
        log_radius = pred["log_radius"].cpu().numpy()
        scores = confidence.cpu().numpy()
        indexes = maxima.cpu().numpy()
        for b, (x, y, left, right, top, bottom) in enumerate(group):
            for row, col in np.argwhere(indexes[b, 0]):
                cx = x + model.stride * (col + float(offsets[b, 0, row, col]))
                cy = y + model.stride * (row + float(offsets[b, 1, row, col]))
                # Keep overlapping predictions until global suppression: slightly shifted
                # centers must not disappear on opposite sides of a tile ownership seam.
                if not (0 <= cx < width and 0 <= cy < height):
                    continue
                rlog = float(log_radius[b, 0, row, col])
                if not math.isfinite(rlog) or not -10 < rlog < 10:
                    continue
                radius = 16 * math.exp(rlog)
                if 0 < radius <= max(width, height):
                    circles.append({"x": cx, "y": cy, "radius": radius,
                                    "confidence": float(scores[b, 0, row, col])})
    retained = []
    for circle in sorted(circles, key=lambda c: c["confidence"], reverse=True):
        if not any(math.hypot(circle["x"] - other["x"], circle["y"] - other["y"])
                   < 0.5 * min(circle["radius"], other["radius"]) for other in retained):
            retained.append(circle)
    return sorted(retained, key=lambda c: (c["y"], c["x"]))


def run(model_path, image_path, output, *, threshold=0.5, device="cpu", threads=4):
    prefix = Path(output)
    destinations = [prefix.with_suffix(suffix) for suffix in (".json", ".jpg")]
    if any(p.exists() for p in destinations):
        raise FileExistsError(f"Evaluation output already exists: {prefix}")
    torch.set_num_threads(threads)
    model, meta = load_model(model_path, device)
    image = read_rgb(image_path)
    start = time.perf_counter()
    circles = detect(model, image, size=meta["crop_size"], threshold=threshold, device=device)
    elapsed = time.perf_counter() - start
    result = {"setup": meta["setup"], "image_name": Path(image_path).name,
              "width": image.shape[1], "height": image.shape[0], "threshold": threshold,
              "inference_seconds": elapsed, "count": len(circles), "circles": circles,
              "evaluation_labels_used": False, "accuracy": None}
    prefix.parent.mkdir(parents=True, exist_ok=True)
    destinations[0].write_text(json.dumps(result, indent=2) + "\n")
    preview = Image.fromarray(image)
    draw = ImageDraw.Draw(preview)
    line_width = max(1, round(max(image.shape[:2]) / 850))
    for c in circles:
        x, y, r = c["x"], c["y"], c["radius"]
        draw.ellipse((x - r, y - r, x + r, y + r), outline="#39ff76", width=line_width)
    preview.thumbnail((1600, 1600))
    preview.save(destinations[1], quality=93)
    print(f"{len(circles)} detections in {elapsed:.2f}s; {destinations[1]}", flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", dest="model_path", type=Path, required=True)
    p.add_argument("--image", dest="image_path", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="Output filename prefix")
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    p.add_argument("--threads", type=int, default=4)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
