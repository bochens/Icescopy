"""Raw-pixel transform, learned target/distractor scores, and portable storage."""
import hashlib
import json
import shutil

import cv2
import numpy as np
import pytest

from auto_cell_ml.code import opencv_nn as nn
from auto_cell_ml.code.image_samples import suppress_centers


def test_raw_rgb_patch_transform_and_batch_bound():
    yy, xx = np.mgrid[:41, :41]
    image = np.stack((xx * 5, yy * 5, np.full_like(xx, 255)), axis=2).astype(np.uint8)
    patch = nn.pixel_patches(image, [[20, 20]], 14 / 3).reshape(15, 15, 3)
    np.testing.assert_allclose(patch[0, 0], image[13, 13] / 127.5 - 1, atol=1e-6)
    np.testing.assert_allclose(patch[7, 7], image[20, 20] / 127.5 - 1, atol=1e-6)
    np.testing.assert_allclose(patch[-1, -1], image[27, 27] / 127.5 - 1, atol=1e-6)
    assert patch.dtype == np.float32 and patch.max() <= 1 and patch.min() >= -1
    with pytest.raises(ValueError, match="32767"):
        nn.pixel_patches(image, np.zeros((32767, 2)), 5)


def _source(folder, monkeypatch):
    folder.mkdir()
    yy, xx = np.mgrid[:72, :72]
    image = np.full((72, 72, 3), 95, np.uint8)
    for x, y in ((18.7, 19.3), (48.7, 45.3)):
        distance = np.hypot(xx - x, yy - y)
        image[np.abs(distance - 5) < 1] = [230, 170, 210]
        if x < 30:
            image[distance < 4] = [35, 50, 60]
    path = folder / "image.png"
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    circles = np.array([[18.7, 19.3, 5]])
    manifest = folder / "datasets.json"
    manifest.write_text(json.dumps({"setups": [{"setup": "fixture", "train": {"image": "image.png"},
                                                "evaluation": {"image": "must-not-open.png"}}]}))
    def reader(selected_manifest, setup):
        assert selected_manifest == manifest.resolve() and setup == "fixture"
        return image.copy(), circles.copy(), {"recording_id": "recording-A", "circle_count": 1,
                                               "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    monkeypatch.setattr(nn, "_read_source", reader)
    return manifest, image, path


def test_original_frame_learner_storage_scores_and_inference_has_no_circle_gate(tmp_path, monkeypatch):
    manifest, image, original_image = _source(tmp_path / "source", monkeypatch)
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}
    original_patches = nn._patches
    def bounded(pixels, points, radius):
        assert len(points) <= 4096
        return original_patches(pixels, points, radius)
    monkeypatch.setattr(nn, "_patches", bounded)
    path, metadata = nn.fit(manifest, tmp_path / "model", setup="fixture", max_samples=600, threads=1)
    assert metadata["augmentation"] is False and metadata["training_image_count"] == 1
    assert metadata["config"]["layers"] == [675, 32, 16, 1]
    assert metadata["config"]["input_scaling"] is False and metadata["config"]["output_scaling"] is False
    check = metadata["training_sample_check"]
    assert np.isfinite(check["mean_squared_error"]) and check["positive_total"] == metadata["positive_count"]
    model, _ = nn.load_model(path)
    patches = nn.pixel_patches(image, [[18.7, 19.3], [48.7, 45.3], [10, 60]], 5)
    scores = nn._scores(model, patches)
    assert scores[0] > 0 and (scores[1:] < 0).all()
    shutil.copytree(path.parent, tmp_path / "moved")
    restored, _ = nn.load_model(tmp_path / "moved")
    np.testing.assert_array_equal(scores, nn._scores(restored, patches))
    def forbidden(*args, **kwargs):
        raise AssertionError("Dense neural inference must not call a circle finder")
    monkeypatch.setattr(cv2, "HoughCircles", forbidden)
    circles = nn.detect(restored, image, radius=5)
    assert any(np.hypot(c["x"] - 18.7, c["y"] - 19.3) < 2 for c in circles)
    assert all(np.hypot(c["x"] - 48.7, c["y"] - 45.3) > 5 for c in circles)
    result = nn.evaluate(path, original_image, tmp_path / "preview")
    assert result["evaluation_labels_used"] is False and "accuracy" not in result
    assert (tmp_path / "preview/overlay.jpg").is_file()
    with pytest.raises(FileExistsError):
        nn.fit(manifest, path.parent, setup="fixture")
    with pytest.raises(FileExistsError):
        nn.evaluate(path, original_image, tmp_path / "preview")
    assert originals == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest.parent.iterdir()}


def test_signed_scores_use_shared_radius_suppression():
    circles = [{"x": x, "y": 0, "radius": 10, "score": score}
               for x, score in ((10, .8), (13, .5), (25, .4))]
    assert [c["x"] for c in suppress_centers(circles, score_key="score")] == [10, 25]
