"""Center supervision, direct learned detection, and portable OpenCV storage."""
import hashlib
import json
import shutil

import cv2
import numpy as np
import pytest

from auto_cell_ml.code import data, forest


def test_all_unmarked_valid_centers_are_negative_and_only_padding_unknown():
    valid = np.ones((32, 32), bool)
    valid[:, :4] = False
    points, labels = forest.sample_points([], valid, budget=200)
    assert not labels.any()
    assert (points[:, 0] >= 4).all()
    assert points[:, 0].max() >= 30 and points[:, 1].min() == 0
    circles = [[10.3, 12.7, 5], [25, 22, 4], [-9, 20, 5]]
    points, labels = forest.sample_points(circles, valid, budget=200)
    for x, y, _ in circles[:2]:
        assert np.any(np.linalg.norm(points[labels == 1] - [x, y], axis=1) < 1e-5)
        assert (np.linalg.norm(points[labels == 0] - [x, y], axis=1) > 1.5).all()


def _training(folder):
    folder.mkdir()
    yy, xx = np.mgrid[:72, :72]
    source = np.full((72, 72, 3), 95, np.uint8)
    circles = np.array([[18.7, 19.3, 5], [48.7, 45.3, 5]], float)
    for x, y, radius in circles:
        distance = np.hypot(xx - x, yy - y)
        source[np.abs(distance - radius) < 1] = [230, 170, 210]
        source[distance < radius - 1] = [35, 50, 60]
    provenance = {"recording_id": "recording-A", "image_sha256": hashlib.sha256(source.tobytes()).hexdigest(),
                  "session_sha256": "fixture-only"}
    rows = []
    for index, scale in enumerate((0.8, 1, 1.2, 1)):
        matrix = cv2.getRotationMatrix2D((36, 36), index * 90, scale)
        image, valid = data._warp(source, matrix, 72)
        transformed = data.transform_circles(circles, matrix)
        label = {"split": "train", "setup": "fixture", "circles": transformed.tolist(), "scale": scale,
                 "recording_id": "recording-A", "source": provenance}
        paths = {"image": f"{index}.png", "labels": f"{index}.json", "valid_mask": f"{index}.valid.png",
                 "sample_index": index, "recording_id": "recording-A"}
        cv2.imwrite(str(folder / paths["image"]), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(folder / paths["valid_mask"]), valid.astype(np.uint8) * 255)
        (folder / paths["labels"]).write_text(json.dumps(label))
        points, targets = forest.sample_points(transformed, valid, budget=100)
        assert forest._usable(points, valid).all() and targets.any()
        rows.append(paths)
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({"split": "train", "setup": "fixture", "samples": rows, "source": provenance,
                                    "evaluation": {"image": "must-not-open.png"}}))
    return manifest, source, circles


def test_direct_learner_fractional_centers_portable_votes_and_preserved_inputs(tmp_path, monkeypatch):
    manifest, image, circles = _training(tmp_path / "crops")
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}
    def forbidden(*args, **kwargs):
        raise AssertionError("Direct center learning cannot call a circle finder")
    monkeypatch.setattr(cv2, "HoughCircles", forbidden)
    path, metadata = forest.fit(manifest, tmp_path / "trained", max_samples=4000, trees=32, max_depth=14, threads=1)
    assert path.name == "model.xml.gz" and metadata["fixed_radius"] == pytest.approx(5)
    assert metadata["sample_count"] <= 4000
    assert metadata["positive_count"] > 0 and metadata["negative_count"] > 0
    model, _ = forest.load_model(path)
    descriptor = forest._features(forest._prepare(image, 5), circles[:, :2], 5)
    votes = model.getVotes(descriptor, 0)
    shutil.copytree(path.parent, tmp_path / "moved")
    restored, _ = forest.load_model(tmp_path / "moved")
    np.testing.assert_array_equal(votes, restored.getVotes(descriptor, 0))
    detected = forest.detect(restored, image, radius=5)
    assert len(detected) == len(circles)
    for x, y, _ in circles:
        assert min(np.hypot(c["x"] - x, c["y"] - y) for c in detected) < 2
    assert forest.detect(restored, np.full_like(image, 95), radius=5) == []
    result = forest.evaluate(path, manifest.parent / "1.png", tmp_path / "evaluation")
    assert result["evaluation_labels_used"] is False and "accuracy" not in result
    assert (tmp_path / "evaluation/overlay.jpg").exists()
    with pytest.raises(FileExistsError):
        forest.fit(manifest, path.parent)
    with pytest.raises(FileExistsError):
        forest.evaluate(path, manifest.parent / "1.png", tmp_path / "evaluation")
    assert originals == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}


def test_uint16_full_range_decode(tmp_path):
    path = tmp_path / "gray.png"
    cv2.imwrite(str(path), np.array([[0, 32768, 65535]], np.uint16))
    pixels = forest.read_rgb(path)
    np.testing.assert_array_equal(pixels[0, :, 0], [0, 128, 255])
    np.testing.assert_array_equal(pixels[..., 0], pixels[..., 2])


def test_mixed_recordings_are_rejected_before_model_writing(tmp_path):
    manifest, _, _ = _training(tmp_path / "crops")
    rows = json.loads(manifest.read_text())
    rows["samples"][1]["recording_id"] = "different-recording"
    manifest.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="recording_id"):
        forest.fit(manifest, tmp_path / "model", max_samples=200)
    assert not (tmp_path / "model").exists()
