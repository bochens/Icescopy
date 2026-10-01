"""Create transformed training crops from one explicitly selected recording.

Every saved circle is transformed, including partially cropped disks. Unmarked
source pixels are negatives; only pixels outside the source are padding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "auto_cell_ml/data/datasets.json"


def _circles_array(circles):
    circles = np.asarray(circles, dtype=np.float64)
    if circles.size == 0:
        circles = circles.reshape(0, 3)
    if circles.ndim != 2 or circles.shape[1] != 3:
        raise ValueError("circles must have shape (N, 3): x, y, radius")
    if not np.isfinite(circles).all() or np.any(circles[:, 2] <= 0):
        raise ValueError("circle coordinates must be finite and radii positive")
    return circles


def transform_circles(circles, matrix):
    """Apply a 2x3 rotation/reflection/uniform-scale transform to all circles."""
    circles = _circles_array(circles)
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (2, 3) or not np.isfinite(matrix).all():
        raise ValueError("matrix must be a finite 2x3 affine matrix")
    linear = matrix[:, :2]
    gram = linear.T @ linear
    scale_squared = float(np.trace(gram) / 2)
    if scale_squared <= 0 or not np.allclose(
        gram, np.eye(2) * scale_squared, rtol=1e-7, atol=1e-12
    ):
        raise ValueError("circles require a uniform scale, without shear")
    result = np.empty_like(circles)
    result[:, :2] = circles[:, :2] @ linear.T + matrix[:, 2]
    result[:, 2] = circles[:, 2] * math.sqrt(scale_squared)
    return result


def targets(circles, valid, stride=4):
    """Build binary centers, fractional x/y offsets, and log(radius/16).

    A grid cell is usable only when its entire stride-by-stride pixel block is
    valid. Two centers in the same usable cell are an error. Off-crop circles
    remain in the JSON labels but do not produce center targets.
    """
    circles = _circles_array(circles)
    valid = np.asarray(valid)
    if valid.ndim != 2 or valid.dtype != np.bool_:
        raise ValueError("valid must be a two-dimensional Boolean mask")
    if isinstance(stride, bool) or not isinstance(stride, (int, np.integer)) or stride <= 0:
        raise ValueError("stride must be a positive integer")
    height, width = valid.shape
    if height == 0 or width == 0 or height % stride or width % stride:
        raise ValueError("mask dimensions must be positive multiples of stride")
    rows, columns = height // stride, width // stride
    usable = valid.reshape(rows, stride, columns, stride).all(axis=(1, 3))
    result = {
        "center": np.zeros((1, rows, columns), np.float32),
        "offsets": np.zeros((2, rows, columns), np.float32),
        "log_radius": np.zeros((1, rows, columns), np.float32),
        "valid": usable[None].astype(np.float32),
    }
    for x, y, radius in circles:
        if not (0 <= x < width and 0 <= y < height):
            continue
        column, row = int(x // stride), int(y // stride)
        if not usable[row, column]:
            continue
        if result["center"][0, row, column]:
            raise ValueError(f"Two circle centers share target cell ({column}, {row})")
        result["center"][0, row, column] = 1
        result["offsets"][:, row, column] = [x / stride - column, y / stride - row]
        result["log_radius"][0, row, column] = math.log(radius / 16)
    return result


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_source(manifest, setup):
    # Anchor the app reader to this checkout. No search for substitute media or
    # alternate manifest names is performed.
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from icescopy_droplet_training_io import (
        load_training_scenes, load_training_session, resolved_source_payload,
    )

    payload = json.loads(manifest.read_text())
    matches = [row for row in payload["setups"] if row["setup"] == setup]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one setup named {setup!r}")
    # Deliberately access only train. Evaluation images and labels are unopened.
    train = matches[0]["train"]
    if train["label_status"] != "user_marked" or not train["recording_id"]:
        raise ValueError("Training requires user-marked circles and a recording ID")
    image_path = (manifest.parent / train["image"]).resolve()
    session_path = (manifest.parent / train["session"]).resolve()
    image_hash = _hash(image_path)
    if image_hash != train["sha256"]:
        raise ValueError("Training image SHA-256 does not match the manifest")
    session = load_training_session(session_path)
    source = resolved_source_payload(session)
    if source["kind"] != "image_sequence" or (
        Path(source["image_paths"][session.saved_frame_index]).resolve() != image_path
    ):
        raise ValueError("Manifest image must be the session's saved original image frame")
    scene = load_training_scenes(session, [session.saved_frame_index])[0]
    circles = np.asarray([[c.x, c.y, c.radius] for c in scene["circles"]], np.float64)
    if len(circles) != train["circle_count"]:
        raise ValueError("Saved circle count does not match the manifest")
    provenance = {
        "recording_id": train["recording_id"],
        "image": train["image"], "session": train["session"],
        "image_sha256": image_hash, "session_sha256": _hash(session_path),
        "manifest_sha256": _hash(manifest),
        "saved_frame_index": session.saved_frame_index,
        "circle_count": len(circles),
        "decoder": "Icescopy original-frame QImage converted to RGB888",
    }
    return scene["image"], circles, provenance


def _valid_mask(matrix, source_shape, size):
    inverse = cv2.invertAffineTransform(matrix)
    yy, xx = np.mgrid[:size, :size]
    sx = inverse[0, 0] * xx + inverse[0, 1] * yy + inverse[0, 2]
    sy = inverse[1, 0] * xx + inverse[1, 1] * yy + inverse[1, 2]
    height, width = source_shape[:2]
    return (sx >= 0) & (sx <= width - 1) & (sy >= 0) & (sy <= height - 1)


def _warp(image, matrix, size):
    """One interpolation from the original frame, without chained resampling."""
    valid = _valid_mask(matrix, image.shape, size)
    pixels = cv2.warpAffine(image, matrix, (size, size), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return pixels, valid


def _lighting(image, params, valid):
    pixels = image.astype(np.float32) / 255
    pixels = (pixels - 0.5) * params["contrast"] + 0.5
    pixels = np.clip(pixels * params["brightness"], 0, 1) ** params["gamma"]
    pixels *= np.asarray(params["channel_gain"], np.float32)
    result = np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8)
    result[~valid] = 0
    return result


def _plan(image, circles, size, count, seed):
    height, width = image.shape[:2]
    x, y, radius = circles.T
    if np.any((x - radius < 0) | (y - radius < 0) |
              (x + radius > width - 1) | (y + radius > height - 1)):
        raise ValueError("A source disk crosses the source boundary; complete-circle coverage is impossible")
    rng = np.random.default_rng(seed)
    plans = []
    for index in range(count):
        sample_seed = int(rng.integers(0, 2**63 - 1))
        sample_rng = np.random.default_rng(sample_seed)
        focus = index if index < len(circles) else (
            int(sample_rng.integers(len(circles))) if sample_rng.random() < 0.8 else None
        )
        for _ in range(100):
            angle = float(sample_rng.uniform(0, 360))
            flips = sample_rng.choice([-1, 1], size=2)
            scale = float(sample_rng.uniform(0.65, 1.5))
            if focus is not None:
                scale = min(scale, 0.35 * size / circles[focus, 2])
                anchor = circles[focus, :2]
                margin = circles[focus, 2] * scale + 4
                destination = sample_rng.uniform(margin, size - 1 - margin, size=2)
            else:
                anchor = sample_rng.uniform([0, 0], [width - 1, height - 1])
                destination = sample_rng.uniform(0.2 * size, 0.8 * size, size=2)
            theta = math.radians(angle)
            linear = scale * np.array([[math.cos(theta), -math.sin(theta)],
                                       [math.sin(theta), math.cos(theta)]]) @ np.diag(flips)
            matrix = np.column_stack((linear, destination - linear @ anchor))
            transformed = transform_circles(circles, matrix)
            valid = _valid_mask(matrix, image.shape, size)
            try:
                target = targets(transformed, valid)
            except ValueError as exc:
                if "share target cell" in str(exc):
                    continue
                raise
            if focus is not None:
                cx, cy, _ = transformed[focus]
                if not target["valid"][0, int(cy // 4), int(cx // 4)]:
                    continue
            lighting = {
                "brightness": float(sample_rng.uniform(0.8, 1.2)),
                "contrast": float(sample_rng.uniform(0.8, 1.2)),
                "gamma": float(sample_rng.uniform(0.8, 1.2)),
                "channel_gain": (sample_rng.uniform(0.94, 1.06, size=3).tolist()
                                 if sample_rng.random() < 0.5 else [1.0, 1.0, 1.0]),
            }
            plans.append({"matrix": matrix, "circles": transformed, "lighting": lighting,
                          "sample_seed": sample_seed, "angle_degrees": angle,
                          "reflect_x": bool(flips[0] < 0), "reflect_y": bool(flips[1] < 0),
                          "scale": scale, "coverage_circle_index": focus if index < len(circles) else None})
            break
        else:
            raise ValueError("Could not make a valid crop without center collisions after 100 attempts")
    return plans


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


def generate(manifest, setup, output, *, count=240, size=384, seed=0):
    """Write crops, circles, padding masks, one manifest, and one contact sheet.

    At least one crop per original circle is required. These coverage crops
    place that entire circle at a randomly drawn interior location, not at a
    fixed center. All planning and collision checks finish before writing.
    """
    for name, value in (("count", count), ("size", size), ("seed", seed)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"{name} must be an integer")
    if count <= 0 or size < 32 or size % 4 or seed < 0:
        raise ValueError("count must be positive; size >=32 and divisible by 4; seed nonnegative")
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    image, circles, source = _read_source(manifest, setup)
    if count < len(circles):
        raise ValueError(f"count must be at least {len(circles)} for complete-circle coverage")
    plans = _plan(image, circles, size, count, seed)
    output.mkdir(parents=True, exist_ok=False)
    samples = []
    preview_indices = set(np.linspace(0, count - 1, min(count, 16), dtype=int).tolist())
    previews = []
    for index, plan in enumerate(plans):
        stem = f"{index:05d}"
        paths = {"image": stem + ".png", "labels": stem + ".json",
                 "valid_mask": stem + ".valid.png"}
        pixels, valid = _warp(image, plan["matrix"], size)
        pixels = _lighting(pixels, plan["lighting"], valid)
        Image.fromarray(pixels).save(output / paths["image"])
        Image.fromarray(valid.astype(np.uint8) * 255).save(output / paths["valid_mask"])
        label = {
            "schema_version": 1, "setup": setup, "split": "train", "seed": int(seed),
            "sample_seed": plan["sample_seed"], "sample_index": index, **paths,
            "source": source, "recording_id": source["recording_id"],
            "affine_matrix": plan["matrix"].tolist(), "lighting": plan["lighting"],
            "angle_degrees": plan["angle_degrees"], "reflect_x": plan["reflect_x"],
            "reflect_y": plan["reflect_y"], "scale": plan["scale"],
            "circles": plan["circles"].tolist(),
            "source_circle_indices": list(range(len(circles))),
            "coverage_circle_index": plan["coverage_circle_index"],
        }
        _write_json(output / paths["labels"], label)
        samples.append({**paths, "sample_index": index, "recording_id": source["recording_id"]})
        if index in preview_indices:
            thumbnail = Image.fromarray(pixels)
            draw = ImageDraw.Draw(thumbnail)
            for cx, cy, radius in plan["circles"]:
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                             outline=(50, 255, 50), width=2)
            thumbnail = thumbnail.resize((160, 160))
            tile = Image.new("RGB", (160, 180), "white")
            tile.paste(thumbnail, (0, 20))
            ImageDraw.Draw(tile).text((3, 3), f"{stem}: {plan['angle_degrees']:.0f} deg", fill="black")
            previews.append(tile)
    columns = min(4, len(previews))
    sheet = Image.new("RGB", (columns * 160, math.ceil(len(previews) / columns) * 180), "white")
    for index, tile in enumerate(previews):
        sheet.paste(tile, ((index % columns) * 160, (index // columns) * 180))
    sheet.save(output / "contact-sheet.jpg", quality=90)
    result = {
        "schema_version": 1, "setup": setup, "split": "train", "seed": int(seed),
        "count": int(count), "size": int(size), "stride": 4, "source": source,
        "contact_sheet": "contact-sheet.jpg", "samples": samples,
        "circle_coordinates": "Original pixel centers transformed by affine_matrix; radius uniformly scaled",
        "padding": "Only out-of-source pixels; every full valid stride block is a training cell",
        "lighting_formula": "clip(clip(((RGB/255-0.5)*contrast+0.5)*brightness,0,1)**gamma*channel_gain,0,1)",
    }
    _write_json(output / "manifest.json", result)
    return output / "manifest.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--setup", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=240)
    parser.add_argument("--size", type=int, default=384)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        result = generate(args.manifest, args.setup, args.output,
                          count=args.count, size=args.size, seed=args.seed)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"{exc}\n")
    print(result)


if __name__ == "__main__":
    main()
