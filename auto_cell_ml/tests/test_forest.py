"""Original-frame supervision, direct detection, and portable OpenCV storage."""
import hashlib
import json
import shutil

import cv2
import numpy as np
import pytest

from auto_cell_ml.code import forest


def test_unmarked_centers_negative_marked_centers_positive_padding_unknown():
    valid = np.ones((32, 32), bool)
    valid[:, :4] = False
    points, labels = forest.sample_points([], valid, budget=200)
    assert not labels.any() and (points[:, 0] >= 4).all()
    assert points[:, 0].max() >= 30 and points[:, 1].min() == 0
    circles = [[10.3, 12.7, 5], [25, 22, 4], [-9, 20, 5]]
    points, labels = forest.sample_points(circles, valid, budget=200)
    assert len(np.unique(points[labels == 1], axis=0)) == labels.sum()
    for x, y, _ in circles[:2]:
        assert np.any(np.linalg.norm(points[labels == 1] - [x, y], axis=1) < 1e-5)
        assert (np.linalg.norm(points[labels == 0] - [x, y], axis=1) > 1.5).all()


def _training(folder, monkeypatch):
    folder.mkdir()
    yy, xx = np.mgrid[:72, :72]
    image = np.full((72, 72, 3), 95, np.uint8)
    circles = np.array([[18.7, 19.3, 5], [48.7, 45.3, 5]], float)
    for x, y, radius in circles:
        distance = np.hypot(xx - x, yy - y)
        image[np.abs(distance - radius) < 1] = [230, 170, 210]
        image[distance < radius - 1] = [35, 50, 60]
    path = folder / "image.png"
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    provenance = {"recording_id": "recording-A", "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "session_sha256": "fixture-only", "circle_count": len(circles)}
    manifest = folder / "datasets.json"
    manifest.write_text(json.dumps({"setups": [{"setup": "fixture", "train": {"image": "image.png"},
                                                "evaluation": {"image": "must-not-open.png"}}]}))
    def trusted_reader(selected_manifest, setup):
        assert selected_manifest == manifest.resolve() and setup == "fixture"
        return image.copy(), circles.copy(), provenance.copy()
    monkeypatch.setattr(forest, "_read_source", trusted_reader)
    return manifest, image, circles


def test_original_only_learner_fractional_centers_portable_votes_no_inference_gate(tmp_path, monkeypatch):
    manifest, image, circles = _training(tmp_path / "source", monkeypatch)
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}
    original_features = forest._features
    def bounded_features(prepared, points, radius):
        assert len(points) <= 4096
        return original_features(prepared, points, radius)
    monkeypatch.setattr(forest, "_features", bounded_features)
    path, metadata = forest.fit(manifest, tmp_path / "trained", setup="fixture", max_samples=8000,
                                trees=32, max_depth=14, threads=1)
    assert path.name == "model.xml.gz" and metadata["fixed_radius"] == pytest.approx(5)
    assert metadata["augmentation"] is False and metadata["training_image_count"] == 1
    assert metadata["sample_count"] <= 8000 and metadata["positive_count"] > 0
    assert metadata["negative_frame_coverage"]["occupied_tiles"] == 64
    model, _ = forest.load_model(path)
    descriptor = forest._features(forest._prepare(image, 5), circles[:, :2], 5)
    votes = model.getVotes(descriptor, 0)
    shutil.copytree(path.parent, tmp_path / "moved")
    restored, _ = forest.load_model(tmp_path / "moved")
    np.testing.assert_array_equal(votes, restored.getVotes(descriptor, 0))
    def forbidden(*args, **kwargs):
        raise AssertionError("Inference cannot call a circle finder")
    monkeypatch.setattr(cv2, "HoughCircles", forbidden)
    detected = forest.detect(restored, image, radius=5)
    assert len(detected) == len(circles)
    for x, y, _ in circles:
        assert min(np.hypot(c["x"] - x, c["y"] - y) for c in detected) < 2
    assert forest.detect(restored, np.full_like(image, 95), radius=5) == []
    result = forest.evaluate(path, manifest.parent / "image.png", tmp_path / "evaluation")
    assert result["evaluation_labels_used"] is False and "accuracy" not in result
    assert (tmp_path / "evaluation/overlay.jpg").exists()
    with pytest.raises(FileExistsError):
        forest.fit(manifest, path.parent, setup="fixture")
    with pytest.raises(FileExistsError):
        forest.evaluate(path, manifest.parent / "image.png", tmp_path / "evaluation")
    assert originals == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}


def test_unmarked_circle_proposals_sampled_and_marked_support_excluded():
    image = np.full((96, 96, 3), 80, np.uint8)
    cv2.circle(image, (22, 26), 8, (200, 200, 200), 2)
    cv2.circle(image, (68, 66), 8, (200, 200, 200), 2)
    valid = np.ones(image.shape[:2], bool)
    valid[:, :4] = False
    points, labels, stats = forest.sample_points([[22, 26, 8]], valid, budget=500,
                                                 image=image, radius=8, return_details=True)
    negatives = points[labels == 0]
    assert (np.linalg.norm(negatives - [22, 26], axis=1) > 1.5).all()
    assert np.linalg.norm(negatives - [68, 66], axis=1).min() < 2
    assert forest._usable(points, valid).all()
    assert stats["negative_circle_proposals"] > 0 and stats["negative_edge_proposals"] > 0
    assert stats["negative_spatial"] > 0 and stats["negative_near_marked"] > 0


def test_duplicate_suppression_preserves_distinct_overlapping_cells():
    circles = [{"x": x, "y": 20, "radius": 10, "confidence": score}
               for x, score in ((20, .9), (23, .8), (35, .7))]
    assert [c["x"] for c in forest.suppress_centers(circles)] == [20, 35]


def test_uint16_full_range_decode(tmp_path):
    path = tmp_path / "gray.png"
    cv2.imwrite(str(path), np.array([[0, 32768, 65535]], np.uint16))
    pixels = forest.read_rgb(path)
    np.testing.assert_array_equal(pixels[0, :, 0], [0, 128, 255])
    np.testing.assert_array_equal(pixels[..., 0], pixels[..., 2])
