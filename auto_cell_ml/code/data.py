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
DEFAULT_MANIFEST = PROJECT_ROOT / "auto_cell_ml/examples/real/datasets.json"


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


def _tile_starts(length, size):
    last = max(0, length - size)
    starts = list(range(0, last + 1, size))
    if starts[-1] != last:
        starts.append(last)
    return starts


def _example_views(image, circles, linear, lighting, example_size):
    if (isinstance(example_size, bool) or not isinstance(example_size, (int, np.integer))
            or example_size < 8):
        raise ValueError("example_size must be an integer of at least 8 pixels")
    refs = np.zeros((2, example_size, example_size, 3), np.uint8)
    mask = np.zeros(2, bool)
    radii = np.zeros(2, np.float32)
    scale = math.sqrt(float(np.sum(linear * linear) / 2))
    center = np.full(2, (example_size - 1) / 2)
    for slot, (x, y, radius) in enumerate(circles):
        # Normalize each example to a three-radius-wide field of view while
        # preserving the query's rotation/reflection. Report its query radius
        # separately so resizing the reference cannot erase the size example.
        ref_linear = example_size / (3 * radius * scale) * linear
        matrix = np.column_stack((ref_linear, center - ref_linear @ np.array([x, y])))
        pixels, valid = _warp(image, matrix, example_size)
        refs[slot] = _lighting(pixels, lighting, valid)
        mask[slot], radii[slot] = True, radius * scale
    return refs, mask, radii


def extract_examples(image, circles, *, example_size=64):
    """Crop one or two marked runtime examples and return refs, mask, radii.

    Input circles use original image pixels. Examples have an approximately
    three-radius-wide field of view, centered at 31.5 for the default 64 pixels.
    Their radii remain in original image pixels. No fitting or files are used.
    """
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or not image.size:
        raise ValueError("Example image must be nonempty RGB uint8")
    circles = _circles_array(circles)
    if not 1 <= len(circles) <= 2:
        raise ValueError("Provide one or two marked example circles")
    height, width = image.shape[:2]
    if np.any((circles[:, 0] < 0) | (circles[:, 0] >= width) |
              (circles[:, 1] < 0) | (circles[:, 1] >= height)):
        raise ValueError("Example circle centers must be inside the source image")
    lighting = {"brightness": 1.0, "contrast": 1.0, "gamma": 1.0,
                "channel_gain": [1.0, 1.0, 1.0]}
    return _example_views(image, circles, np.eye(2), lighting, example_size)


class TrainingViews:
    """Make training views in memory from one original marked recording.

    Every epoch includes unrotated, scale-one tiles covering every source pixel,
    followed by one randomly positioned whole-circle view per manual circle.
    The actual ``count`` is max(requested count, tile count + circle count).
    Remaining views sample marked circles or source background. No files are
    written and no evaluation files are read. Calling ``set_epoch`` changes
    random views and lighting deterministically without caching derived images.
    """

    def __init__(self, manifest, setup, *, size=256, count=240, seed=0):
        self._validate_settings(size, count, seed)
        image, circles, source = _read_source(Path(manifest).resolve(), setup)
        self._initialize(image, circles, source, setup=setup, size=size, count=count, seed=seed)

    @classmethod
    def from_scene(cls, image, circles, source, *, setup, size=256, count=64, seed=0):
        """Use an already verified synthetic fit scene with the same view rules."""
        if source.get("synthetic") is not True or source.get("split") != "fit" or source.get("complete_labels") is not True:
            raise ValueError("Scene views require a verified, completely labeled synthetic fit source")
        instance = cls.__new__(cls)
        instance._initialize(image, circles, source, setup=setup, size=size, count=count, seed=seed)
        return instance

    @staticmethod
    def _validate_settings(size, count, seed):
        for name, value in (("size", size), ("count", count), ("seed", seed)):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise ValueError(f"{name} must be an integer")
        if size < 32 or size % 4 or count < 1 or seed < 0:
            raise ValueError("size must be >=32 and divisible by 4; count positive; seed nonnegative")

    def _initialize(self, image, circles, source, *, setup, size, count, seed):
        self._validate_settings(size, count, seed)
        self.setup, self.size, self.seed = setup, int(size), int(seed)
        self.requested_count, self.epoch = int(count), 0
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or not image.size:
            raise ValueError("Training image must be nonempty RGB uint8")
        self._image, self._circles, self.source = image, _circles_array(circles), dict(source)
        if len(self._circles) == 0:
            raise ValueError("Original training recording requires at least one marked circle")
        height, width = self._image.shape[:2]
        self.tiles = tuple((x, y) for y in _tile_starts(height, self.size)
                           for x in _tile_starts(width, self.size))
        self.tile_count, self.circle_count = len(self.tiles), len(self._circles)
        self.count = max(self.requested_count, self.tile_count + self.circle_count)
        # Keep the scale range at .75..1.25 rather than shrinking large circles
        # below the documented range merely to fit a too-small crop.
        if np.any(self._circles[:, 2] * 0.75 + 4 > (self.size - 1) / 2):
            raise ValueError("View size is too small for a whole source circle at scale .75")
        for x, y in self.tiles:
            matrix = np.array([[1, 0, -x], [0, 1, -y]], dtype=np.float64)
            targets(transform_circles(self._circles, matrix),
                    _valid_mask(matrix, self._image.shape, self.size))

    def __len__(self):
        return self.count

    def set_epoch(self, epoch):
        if isinstance(epoch, bool) or not isinstance(epoch, (int, np.integer)) or epoch < 0:
            raise ValueError("epoch must be a nonnegative integer")
        self.epoch = int(epoch)

    def __getitem__(self, index):
        """Return the legacy image, all circles, and padding-valid mask."""
        return self._view(index)[:3]

    def episode(self, index, example_size=64):
        """Return a query and one or two positive examples from the full source.

        The first three arrays exactly match ``self[index]``. References share
        the query's rotation, reflection, and lighting, even when the query is
        background only. Returned radii use query pixels; unused slots are zero.
        """
        pixels, circles, valid, matrix, lighting, rng = self._view(index)
        count = int(rng.integers(1, min(2, self.circle_count) + 1))
        selected = rng.choice(self.circle_count, size=count, replace=False)
        refs, mask, radii = _example_views(self._image, self._circles[selected],
                                          matrix[:, :2], lighting, example_size)
        return pixels, circles, valid, refs, mask, radii

    def _view(self, index):
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise TypeError("view index must be an integer")
        index = int(index)
        if index < 0:
            index += self.count
        if not 0 <= index < self.count:
            raise IndexError(index)
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, self.epoch, index]))
        if index < self.tile_count:
            x, y = self.tiles[index]
            matrix = np.array([[1, 0, -x], [0, 1, -y]], dtype=np.float64)
            circles = transform_circles(self._circles, matrix)
        else:
            focus = index - self.tile_count if index < self.tile_count + self.circle_count else (
                int(rng.integers(self.circle_count)) if rng.random() < 0.8 else None
            )
            matrix, circles = self._random_transform(rng, focus)
        pixels, valid = _warp(self._image, matrix, self.size)
        lighting = {"brightness": float(rng.uniform(0.9, 1.1)),
                    "contrast": float(rng.uniform(0.9, 1.1)),
                    "gamma": float(rng.uniform(0.95, 1.05)),
                    "channel_gain": [1.0, 1.0, 1.0]}
        return _lighting(pixels, lighting, valid), circles, valid, matrix, lighting, rng

    def _random_transform(self, rng, focus):
        height, width = self._image.shape[:2]
        max_scale = 1.25 if focus is None else min(
            1.25, (self.size - 9) / (2 * self._circles[focus, 2]))
        for _ in range(100):
            theta = float(rng.uniform(0, 2 * math.pi))
            flips = rng.choice([-1, 1], size=2)
            scale = float(rng.uniform(0.75, max_scale))
            linear = scale * np.array([[math.cos(theta), -math.sin(theta)],
                                       [math.sin(theta), math.cos(theta)]]) @ np.diag(flips)
            if focus is None:
                anchor = rng.uniform([0, 0], [width - 1, height - 1])
                destination = rng.uniform(0.2 * self.size, 0.8 * self.size, size=2)
            else:
                anchor = self._circles[focus, :2]
                margin = self._circles[focus, 2] * scale + 4
                destination = rng.uniform(margin, self.size - 1 - margin, size=2)
            matrix = np.column_stack((linear, destination - linear @ anchor))
            circles = transform_circles(self._circles, matrix)
            valid = _valid_mask(matrix, self._image.shape, self.size)
            try:
                target = targets(circles, valid)
            except ValueError as exc:
                if "share target cell" in str(exc):
                    continue
                raise
            if focus is not None:
                x, y, _ = circles[focus]
                if not target["valid"][0, int(y // 4), int(x // 4)]:
                    continue
            return matrix, circles
        raise ValueError("Could not make a valid view without center collisions after 100 attempts")


def read_synthetic_fit(labels_path):
    """Read only local synthetic fit PNGs, ignoring historical source paths.

    ``labels.json`` contains a ``scenes`` list whose rows name ``id``, ``split``,
    ``sha256``, ``width``, ``height``, ``recording``, and x/y/radius ``targets``.
    Each fit row must declare ``complete_labels: true`` before its unmarked
    pixels can be negatives. The PNG must be adjacent as ``<id>.png``.
    Validation and calibration PNGs are never opened. This writes no files.
    """
    labels_path = Path(labels_path).resolve()
    payload = json.loads(labels_path.read_text())
    manifest_hash = _hash(labels_path)
    scenes, seen = [], set()
    for row in payload["scenes"]:
        if row["split"] != "fit":
            continue
        if row.get("complete_labels") is not True:
            raise ValueError("Synthetic fit scenes require complete_labels=true")
        scene_id = row["id"]
        if (not isinstance(scene_id, str) or not scene_id or Path(scene_id).name != scene_id
                or scene_id in (".", "..") or scene_id in seen):
            raise ValueError("Synthetic fit scene IDs must be unique local filenames")
        seen.add(scene_id)
        image_path = labels_path.parent / f"{scene_id}.png"
        image_hash = _hash(image_path)
        if image_hash != row["sha256"]:
            raise ValueError(f"Synthetic fit image SHA-256 mismatch: {scene_id}")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (row["height"], row["width"]):
            raise ValueError(f"Synthetic fit image dimensions do not match: {scene_id}")
        circles = _circles_array([[item["x"], item["y"], item["radius"]] for item in row["targets"]])
        height, width = image.shape[:2]
        if np.any((circles[:, 0] < 0) | (circles[:, 0] >= width) |
                  (circles[:, 1] < 0) | (circles[:, 1] >= height)):
            raise ValueError(f"Synthetic target center is outside its image: {scene_id}")
        scenes.append({"image": cv2.cvtColor(image, cv2.COLOR_BGR2RGB), "circles": circles,
                       "source": {"recording_id": row["recording"], "scene_id": scene_id,
                                  "image": image_path.name, "image_sha256": image_hash,
                                  "manifest_sha256": manifest_hash, "split": "fit",
                                  "complete_labels": True, "synthetic": True}})
    if not scenes:
        raise ValueError("Synthetic labels contain no fit scenes")
    return scenes


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
