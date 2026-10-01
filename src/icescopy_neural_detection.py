"""Example-guided droplet inference using bundled OpenCV CPU networks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import stat
import struct
import tempfile
from types import MappingProxyType
from typing import Mapping
import zipfile

import cv2
import numpy as np

from icescopy_validate import find_resources_dir

MODEL_FORMAT = "icescopy-droplet-onnx-v2"
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_GRAPH_BYTES = 32 * 1024 * 1024
MAX_TEXT_BYTES = 1024 * 1024
MAX_BUNDLE_MEMBERS = 8
MAX_ZIP_DIRECTORY_BYTES = 64 * 1024
OPTIONAL_BUNDLE_FILES = {"README.md", "README.txt", "LICENSE", "LICENSE.md", "LICENSE.txt", "TORCHVISION-LICENSE.txt"}


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float

    def __post_init__(self):
        for name in ("x", "y", "radius"):
            try:
                value = float(getattr(self, name))
            except (TypeError, ValueError) as exc:
                raise ValueError("Circle coordinates must be finite and radius positive") from exc
            if not math.isfinite(value) or (name == "radius" and value <= 0):
                raise ValueError("Circle coordinates must be finite and radius positive")
            object.__setattr__(self, name, value)


def _circle(value):
    if isinstance(value, Circle):
        return value
    try:
        if isinstance(value, Mapping):
            return Circle(value["x"], value["y"], value["radius"])
        return Circle(value.x, value.y, value.radius)
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError("Expected a circle with x, y and radius") from exc


def same_object(a, b):
    """Exactly one smaller radius is the minimum separation for distinct centers."""
    a, b = _circle(a), _circle(b)
    return math.hypot(a.x - b.x, a.y - b.y) < min(a.radius, b.radius)


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model_id: str
    version: str
    onnx_path: Path
    reference_onnx_path: Path
    threshold: float
    tile_size: int
    stride: int
    example_size: int
    default_reference: tuple[float, ...]
    default_radius: float
    metadata: Mapping
    # A worker's reference to this frozen config keeps extracted graphs alive.
    # TemporaryDirectory cleans up when the final config reference is released.
    _storage: tempfile.TemporaryDirectory | None = field(default=None, repr=False, compare=False)

    def __del__(self):
        storage = getattr(self, "_storage", None)
        if storage is not None:
            storage.cleanup()


def _local_onnx_name(filename):
    if (not isinstance(filename, str) or not filename or Path(filename).name != filename
            or any(char in filename for char in ("/", "\\", ":", "\x00")) or Path(filename).suffix.lower() != ".onnx"):
        raise ValueError("Model filenames must name local ONNX files beside the metadata")
    return filename


def _checked_model_file(folder, filename, digest):
    filename = _local_onnx_name(filename)
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise ValueError("Model metadata must include a valid SHA-256 hash")
    path = (folder / filename).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Bundled droplet model is missing: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest.lower():
        raise ValueError(f"Droplet model SHA-256 mismatch: {path.name}")
    return path


def _read_metadata(raw):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Droplet model metadata is not valid JSON") from exc


def _check_zip_directory(path):
    # Check the bounded ZIP footer before zipfile allocates member objects.
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 65577))
        tail = stream.read()
    position = tail.rfind(b"PK\x05\x06")
    while position >= 0:
        if len(tail) - position >= 22:
            record = struct.unpack_from("<4s4H2LH", tail, position)
            if position + 22 + record[7] == len(tail):
                break
        position = tail.rfind(b"PK\x05\x06", 0, position)
    if position < 0:
        raise ValueError("Droplet model bundle is not a valid ZIP archive")
    if record[1] or record[2] or record[3] != record[4] or not 1 <= record[4] <= MAX_BUNDLE_MEMBERS or record[5] > MAX_ZIP_DIRECTORY_BYTES:
        raise ValueError("Droplet model bundle exceeds its ZIP directory limits")
    if position >= 20 and tail[position - 20:position - 16] == b"PK\x06\x07":
        raise ValueError("ZIP64 droplet model bundles are unsupported")


def _unpack_bundle(path):
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("Droplet model bundle exceeds the 64 MiB size limit")
    _check_zip_directory(path)
    storage = tempfile.TemporaryDirectory(prefix="icescopy-model-")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not 1 <= len(members) <= MAX_BUNDLE_MEMBERS or sum(info.file_size for info in members) > MAX_BUNDLE_BYTES:
                raise ValueError("Droplet model bundle exceeds its member or unpacked size limit")
            names = set()
            for info in members:
                filename = info.filename
                kind = stat.S_IFMT(info.external_attr >> 16)
                if (not filename or Path(filename).name != filename or any(char in filename for char in ("/", "\\", ":", "\x00"))
                        or info.orig_filename != filename or filename.casefold() in names or info.is_dir()
                        or kind not in (0, stat.S_IFREG) or info.flag_bits & 1
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError("Droplet model bundle contains an unsafe or duplicate member")
                limit = MAX_GRAPH_BYTES if filename.lower().endswith(".onnx") else MAX_TEXT_BYTES
                if info.file_size > limit:
                    raise ValueError(f"Droplet model bundle member is too large: {filename}")
                names.add(filename.casefold())
            if "droplet_detector.json" not in archive.namelist():
                raise ValueError("Droplet model bundle is missing droplet_detector.json")
            payload = _read_metadata(archive.read("droplet_detector.json"))
            if not isinstance(payload, dict):
                raise ValueError("Droplet model metadata must be an object")
            graphs = [_local_onnx_name(payload.get(key)) for key in ("model_file", "reference_model_file")]
            required = {"droplet_detector.json", *graphs}
            if len(required) != 3 or not required.issubset(archive.namelist()):
                raise ValueError("Droplet model bundle must contain its two distinct ONNX graphs")
            if set(archive.namelist()) - required - OPTIONAL_BUNDLE_FILES:
                raise ValueError("Droplet model bundle contains unexpected files")
            for filename in required:
                (Path(storage.name) / filename).write_bytes(archive.read(filename))
        return storage
    except Exception as exc:
        storage.cleanup()
        if isinstance(exc, (zipfile.BadZipFile, NotImplementedError, RuntimeError)):
            raise ValueError("Droplet model bundle is not a valid readable ZIP archive") from exc
        raise


def load_model(path=None):
    """Load portable JSON or one .icescopy-model bundle; never fall back on error."""
    path = (Path(path) if path is not None else find_resources_dir() / "models" / "droplet_detector.json").resolve()
    storage = _unpack_bundle(path) if path.suffix.lower() == ".icescopy-model" else None
    try:
        metadata_path = Path(storage.name) / "droplet_detector.json" if storage is not None else path
        if metadata_path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("Droplet model metadata exceeds the 1 MiB size limit")
        return _load_config(metadata_path, storage)
    except Exception:
        if storage is not None:
            storage.cleanup()
        raise


def _load_config(path, storage):
    payload = _read_metadata(path.read_bytes())
    if not isinstance(payload, dict) or payload.get("format") != MODEL_FORMAT:
        raise ValueError("Unsupported bundled droplet model format")
    for key, expected in (("tile_size", 256), ("example_size", 64), ("stride", 4)):
        if type(payload.get(key)) is not int or payload[key] != expected:
            raise ValueError(f"Droplet model requires {key}={expected}")
    if payload.get("threshold") != 0.5:
        raise ValueError("Droplet model requires the fixed threshold 0.5")
    for key in ("name", "model_id", "version"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f"Droplet model metadata requires a nonempty {key}")
    try:
        reference = np.asarray(payload["default_reference"], np.float32)
        radius = float(payload["default_radius"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Droplet model must include its training-derived default reference and radius") from exc
    if reference.shape != (32,) or not np.isfinite(reference).all() or not math.isfinite(radius) or not 0 < radius <= np.finfo(np.float32).max:
        raise ValueError("Default reference must contain 32 finite values and a positive finite radius")
    detector = _checked_model_file(path.parent, payload.get("model_file"), payload.get("sha256"))
    encoder = _checked_model_file(path.parent, payload.get("reference_model_file"), payload.get("reference_sha256"))
    return ModelConfig(payload["name"].strip(), payload["model_id"].strip(), payload["version"].strip(),
                       detector, encoder, 0.5, 256, 4, 64,
                       tuple(float(v) for v in reference), radius, _freeze(payload), storage)


def _reference_blob(image, circle, size):
    """Match developer extraction: three-radius field, pixel center at 31.5."""
    factor = size / (3 * circle.radius)
    matrix = np.array([[factor, 0, (size - 1) / 2 - factor * circle.x],
                       [0, factor, (size - 1) / 2 - factor * circle.y]], np.float64)
    pixels = cv2.warpAffine(image, matrix, (size, size), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    inverse = cv2.invertAffineTransform(matrix)
    yy, xx = np.mgrid[:size, :size]
    sx = inverse[0, 0] * xx + inverse[0, 1] * yy + inverse[0, 2]
    sy = inverse[1, 0] * xx + inverse[1, 1] * yy + inverse[1, 2]
    valid = (sx >= 0) & (sx <= image.shape[1] - 1) & (sy >= 0) & (sy <= image.shape[0] - 1)
    pixels[~valid] = 0
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=np.float32) / 255


def _tile_starts(length, size):
    last = max(length - size, 0)
    starts = list(range(0, last + 1, size - size // 4))
    if starts[-1] != last:
        starts.append(last)
    return starts


def _cpu_network(path):
    try:
        # Python handles Unicode Windows paths; OpenCV accepts the ONNX bytes.
        model_bytes = np.frombuffer(path.read_bytes(), dtype=np.uint8)
        net = cv2.dnn.readNetFromONNX(model_bytes)
        if net.empty():
            raise ValueError(f"Empty droplet ONNX network: {path.name}")
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        return net
    except (OSError, cv2.error) as exc:
        raise ValueError(f"Cannot load droplet ONNX network {path.name}: {exc}") from exc


class NeuralDetector:
    """One CPU detector; selected examples never trigger fitting or weight changes."""
    def __init__(self, config):
        if not isinstance(config, ModelConfig):
            raise TypeError("NeuralDetector requires validated metadata from load_model")
        self.config = config
        self.reference_net = _cpu_network(config.reference_onnx_path)
        self.net = _cpu_network(config.onnx_path)

    def predict(self, rgb, *, examples=(), protected=(), cancelled=None):
        """Return new circles; cancellation returns no partial detections."""
        if cancelled is not None and not callable(cancelled):
            raise ValueError("cancelled must be callable")
        is_cancelled = cancelled if cancelled is not None else lambda: False
        if is_cancelled():
            return []
        rgb = np.asarray(rgb)
        if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8 or not rgb.size:
            raise ValueError("Expected a nonempty RGB uint8 image")
        height, width = rgb.shape[:2]
        examples = tuple(_circle(c) for c in examples)
        protected = tuple(_circle(c) for c in protected)
        if any(not (0 <= c.x < width and 0 <= c.y < height) or c.radius > np.finfo(np.float32).max for c in examples):
            raise ValueError("Example centers must be inside the image and radii fit float32")
        descriptors = []
        try:
            for circle in examples:
                if is_cancelled():
                    return []
                self.reference_net.setInput(_reference_blob(rgb, circle, self.config.example_size), "rgb")
                descriptor = self.reference_net.forward("descriptor")
                if descriptor.shape != (1, 32, 1, 1) or not np.isfinite(descriptor).all():
                    raise ValueError("Reference network must return 32 finite descriptor values")
                descriptors.append(descriptor.copy())
            if examples:
                reference = np.mean(np.stack(descriptors), axis=0, dtype=np.float32)
                radius = float(np.mean(np.asarray([c.radius for c in examples], np.float32), dtype=np.float32))
            else:
                reference = np.asarray(self.config.default_reference, np.float32).reshape(1, 32, 1, 1)
                radius = self.config.default_radius
            reference_radius = np.asarray([[[[radius]]]], np.float32)
            found = []
            size, stride = self.config.tile_size, self.config.stride
            for y in _tile_starts(height, size):
                for x in _tile_starts(width, size):
                    if is_cancelled():
                        return []
                    patch = rgb[y:y + size, x:x + size]
                    padded = np.zeros((size, size, 3), np.uint8)
                    padded[:len(patch), :patch.shape[1]] = patch
                    self.net.setInput(np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32) / 255, "rgb")
                    self.net.setInput(reference, "reference")
                    self.net.setInput(reference_radius, "reference_radius")
                    raw = self.net.forward("prediction")
                    if raw.shape != (1, 4, size // stride, size // stride) or not np.isfinite(raw).all():
                        raise ValueError("Detector network returned invalid center/geometry output")
                    scores = 1 / (1 + np.exp(-np.clip(raw[0, 0], -80, 80)))
                    maxima = (scores >= self.config.threshold) & (scores == cv2.dilate(scores, np.ones((3, 3), np.uint8)))
                    for row, col in np.argwhere(maxima):
                        cx, cy = x + stride * (col + float(raw[0, 1, row, col])), y + stride * (row + float(raw[0, 2, row, col]))
                        rlog = float(raw[0, 3, row, col])
                        if not (0 <= cx < width and 0 <= cy < height and -10 < rlog < 10):
                            continue
                        r = 16 * math.exp(rlog)
                        if 0 < r <= max(width, height):
                            found.append((Circle(cx, cy, r), float(scores[row, col])))
        except cv2.error as exc:
            raise ValueError(f"Droplet model inference failed: {exc}") from exc
        if is_cancelled():
            return []
        kept = []
        for circle, score in sorted(found, key=lambda item: item[1], reverse=True):
            if all(not same_object(circle, other) for other, _ in kept):
                kept.append((circle, score))
        exclusions = examples + protected
        return [{"circle": asdict(circle), "score": score} for circle, score in sorted(kept, key=lambda item: (item[0].y, item[0].x))
                if all(not same_object(circle, old) for old in exclusions)]


def validate_model(config):
    """Check both external graphs on fresh CPU networks without changing settings."""
    engine = NeuralDetector(config)
    try:
        engine.reference_net.setInput(np.zeros((1, 3, 64, 64), np.float32), "rgb")
        reference = engine.reference_net.forward("descriptor")
        if reference.shape != (1, 32, 1, 1) or not np.isfinite(reference).all():
            raise ValueError("Reference network must return 32 finite descriptor values")
        engine.net.setInput(np.zeros((1, 3, 256, 256), np.float32), "rgb")
        engine.net.setInput(reference, "reference")
        engine.net.setInput(np.full((1, 1, 1, 1), 16, np.float32), "reference_radius")
        raw = engine.net.forward("prediction")
        if raw.shape != (1, 4, 64, 64) or not np.isfinite(raw).all():
            raise ValueError("Detector network returned invalid center/geometry output")
    except cv2.error as exc:
        raise ValueError(f"Droplet model compatibility check failed: {exc}") from exc
