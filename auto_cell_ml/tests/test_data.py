"""Geometry and source-boundary checks for the independent training crops."""

import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image
import pytest

from auto_cell_ml.code import data


def _fixture(folder, pixels=None):
    folder.mkdir(exist_ok=True)
    if pixels is None:
        yy, xx = np.mgrid[:64, :96]
        pixels = np.stack((xx * 2, yy * 3, xx + yy), axis=2).astype(np.uint8)
    image = folder / "image.png"
    Image.fromarray(pixels).save(image)
    circles = [[12.25, 12.5, 4], [40.5, 30.75, 5], [80.25, 50.5, 4]]
    session = folder / "training.icescopy"
    state = {
        "schema_version": 6,
        "frame_source": {"kind": "image_sequence", "image_paths": ["unused.png", "image.png"]},
        "image_index": 1,
        "cell_items": [{"circle_pixel_positions": [x, y], "circle_sizes": r,
                        "circle_positions": [x + 100, y + 100], "cell_id": i}
                       for i, (x, y, r) in enumerate(circles)],
        "keyframe_cell_items_dict": {"1": [{"circle_pixel_positions": [1, 1], "circle_sizes": 1}]},
        "image_edit_state": {"exposure": 5, "contrast": 80,
                             "crop_state": {"width": 10, "height": 10, "angle": 90}},
    }
    with zipfile.ZipFile(session, "w") as archive:
        archive.writestr("session.json", json.dumps(state))
        archive.writestr("grayscale.csv", "This must never be read")
    manifest = folder / "datasets.json"
    manifest.write_text(json.dumps({"setups": [{
        "setup": "synthetic",
        "train": {"recording_id": "recording-A", "image": image.name,
                  "session": session.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                  "label_status": "user_marked", "circle_count": len(circles)},
        "evaluation": {"image": "evaluation/forbidden.png", "labels": "evaluation/forbidden.json"},
    }]}))
    return manifest, np.asarray(circles), pixels


def test_rotation_reflection_uniform_scale_and_corner_positions():
    circles = np.array([[0, 0, 2], [10, 0, 3], [10, 20, 4], [0, 20, 5]])
    matrix = np.array([[0, -2, 80], [-2, 0, 60]], float)
    np.testing.assert_allclose(data.transform_circles(circles, matrix),
                               [[80, 60, 4], [80, 40, 6], [40, 40, 8], [40, 60, 10]])
    rotation = np.array([[0, -1, 31], [1, 0, 0]], float)
    np.testing.assert_allclose(data.transform_circles(circles, rotation)[:, 2], circles[:, 2])
    for invalid in ([[2, 0, 0], [0, 1, 0]], [[1, 0.2, 0], [0, 1, 0]]):
        with pytest.raises(ValueError, match="uniform scale"):
            data.transform_circles(circles, invalid)


def test_labels_move_with_synthetic_pixel_marks_and_padding():
    pixels = np.zeros((32, 32, 3), np.uint8)
    circles = np.array([[7, 9, 2], [21, 18, 3]], float)
    pixels[9, 7] = [100, 200, 50]
    pixels[18, 21] = [200, 50, 100]
    matrix = np.array([[0, -1, 31], [1, 0, 0]], float)
    warped, valid = data._warp(pixels, matrix, 32)
    moved = data.transform_circles(circles, matrix)
    assert valid.all()
    for original, transformed in zip(circles, moved):
        np.testing.assert_array_equal(warped[int(transformed[1]), int(transformed[0])],
                                      pixels[int(original[1]), int(original[0])])
    _, cropped_valid = data._warp(pixels, np.array([[1, 0, -8], [0, 1, 0]], float), 32)
    assert cropped_valid[:, :24].all()
    assert not cropped_valid[:, 24:].any()


def test_partial_disks_are_retained_even_with_center_outside_crop():
    circles = np.array([[9, 12, 4], [11, 10, 3], [100, 100, 8]], float)
    moved = data.transform_circles(circles, [[1, 0, -10], [0, 1, -3]])
    np.testing.assert_allclose(moved, [[-1, 9, 4], [1, 7, 3], [90, 97, 8]])
    result = data.targets(moved, np.ones((32, 32), bool))
    assert result["center"].sum() == 1
    assert result["center"][0, 1, 0] == 1


def test_offsets_reconstruct_centers_and_radius_is_not_clipped():
    circles = np.array([[3.25, 4.75, 64], [19.4, 24.1, 0.01], [33, 4, 5]])
    result = data.targets(circles, np.ones((32, 32), bool))
    assert result["center"].shape == (1, 8, 8)
    assert result["center"].sum() == 2
    for x, y, radius in circles[:2]:
        col, row = int(x // 4), int(y // 4)
        xy = 4 * (np.array([col, row]) + result["offsets"][:, row, col])
        np.testing.assert_allclose(xy, [x, y], atol=1e-6)
        np.testing.assert_allclose(16 * np.exp(result["log_radius"][0, row, col]), radius, rtol=1e-6)


def test_padding_requires_complete_valid_block_and_collisions_fail():
    valid = np.ones((32, 32), bool)
    valid[7, 7] = False
    result = data.targets([[4.1, 4.1, 2]], valid)
    assert result["valid"].sum() == 63
    assert result["valid"][0, 1, 1] == 0
    assert result["center"].sum() == 0
    with pytest.raises(ValueError, match="share target cell"):
        data.targets([[8.1, 9.1, 2], [10.9, 11.9, 2]], valid)


def test_original_saved_frame_and_16_bit_decoding(tmp_path):
    pixels = np.zeros((64, 96), np.uint16)
    pixels[:, 32:64] = 32768
    pixels[:, 64:] = 65535
    manifest, circles, _ = _fixture(tmp_path, pixels)
    decoded, saved_circles, source = data._read_source(manifest, "synthetic")
    np.testing.assert_array_equal(decoded[20, [10, 40, 80], 0], [0, 128, 255])
    np.testing.assert_array_equal(decoded[..., 0], decoded[..., 1])
    np.testing.assert_allclose(saved_circles, circles)
    assert source["saved_frame_index"] == 1
    assert not (tmp_path / "unused.png").exists()


def test_generation_reproducibility_coverage_and_no_evaluation_reads(tmp_path, monkeypatch):
    manifest, circles, _ = _fixture(tmp_path / "source")
    source_hashes = {path: data._hash(path) for path in manifest.parent.iterdir()}
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert "evaluation" not in path.parts, "Evaluation files must remain unopened"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    first = tmp_path / "first"
    second = tmp_path / "second"
    data.generate(manifest, "synthetic", first, count=12, size=64, seed=27)
    data.generate(manifest, "synthetic", second, count=12, size=64, seed=27)
    first_files = {p.name: p.read_bytes() for p in first.iterdir()}
    assert first_files == {p.name: p.read_bytes() for p in second.iterdir()}
    assert len(first_files) == 12 * 3 + 2
    result = json.loads((first / "manifest.json").read_text())
    assert result["setup"] == "synthetic" and result["split"] == "train"
    assert result["count"] == len(result["samples"]) == 12
    covered, coverage_positions = set(), []
    for sample in result["samples"]:
        label = json.loads((first / sample["labels"]).read_text())
        moved = np.asarray(label["circles"])
        np.testing.assert_allclose(moved, data.transform_circles(circles, label["affine_matrix"]))
        assert len(moved) == len(circles)
        assert label["seed"] == 27 and label["recording_id"] == "recording-A"
        assert label["source"]["image_sha256"] == result["source"]["image_sha256"]
        with Image.open(first / sample["valid_mask"]) as image:
            valid = np.asarray(image) == 255
        target = data.targets(moved, valid)
        for x, y, _ in moved:
            if 0 <= x < 64 and 0 <= y < 64 and target["valid"][0, int(y // 4), int(x // 4)]:
                assert target["center"][0, int(y // 4), int(x // 4)] == 1
        focus = label["coverage_circle_index"]
        if focus is not None:
            x, y, radius = moved[focus]
            assert radius <= x <= 63 - radius and radius <= y <= 63 - radius
            assert target["center"][0, int(y // 4), int(x // 4)] == 1
            coverage_positions.append([x, y])
            covered.add(focus)
    assert covered == set(range(len(circles)))
    assert np.ptp(coverage_positions, axis=0).min() > 4
    assert source_hashes == {path: data._hash(path) for path in manifest.parent.iterdir()}


def test_existing_output_and_invalid_requests_fail_before_writing(tmp_path):
    manifest, _, _ = _fixture(tmp_path / "source")
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "user.txt"
    sentinel.write_text("keep this")
    with pytest.raises(FileExistsError):
        data.generate(tmp_path / "nonexistent.json", "synthetic", existing)
    assert sentinel.read_text() == "keep this"
    invalid = [{"count": 0}, {"count": -1}, {"count": 2}, {"size": 31},
               {"size": 33}, {"seed": -1}, {"count": 3.5}]
    for number, arguments in enumerate(invalid):
        output = tmp_path / f"bad-{number}"
        with pytest.raises(ValueError):
            data.generate(manifest, "synthetic", output, **arguments)
        assert not output.exists()


def test_in_memory_tiles_cover_every_source_pixel_and_expand_count(tmp_path):
    pixels = np.zeros((75, 91, 3), np.uint8)
    manifest, circles, _ = _fixture(tmp_path, pixels)
    files_before = {path.name for path in tmp_path.iterdir()}
    views = data.TrainingViews(manifest, "synthetic", size=32, count=1, seed=8)
    assert len(views) == views.count == views.tile_count + len(circles) == 12
    assert views.requested_count == 1
    for epoch in (0, 2):
        views.set_epoch(epoch)
        coverage = np.zeros(pixels.shape[:2], bool)
        for index, (x, y) in enumerate(views.tiles):
            image, moved, valid = views[index]
            assert image.shape == (32, 32, 3) and image.dtype == np.uint8
            assert valid.dtype == bool and valid.all()
            np.testing.assert_allclose(moved, circles - np.array([x, y, 0]))
            coverage[y:y + 32, x:x + 32] |= valid
        assert coverage.all()
    assert files_before == {path.name for path in tmp_path.iterdir()}


def test_in_memory_views_epoch_determinism_and_whole_circle_geometry(tmp_path):
    manifest, circles, _ = _fixture(tmp_path)
    first = data.TrainingViews(manifest, "synthetic", size=64, count=12, seed=19)
    second = data.TrainingViews(manifest, "synthetic", size=64, count=12, seed=19)
    for index in range(len(first)):
        for actual, expected in zip(first[index], second[index]):
            np.testing.assert_array_equal(actual, expected)
    changed = first[first.tile_count]
    first.set_epoch(1)
    second.set_epoch(1)
    assert not np.array_equal(changed[1], first[first.tile_count][1])
    positions = []
    for focus in range(len(circles)):
        image, moved, valid = first[first.tile_count + focus]
        for actual, expected in zip((image, moved, valid), second[second.tile_count + focus]):
            np.testing.assert_array_equal(actual, expected)
        assert len(moved) == len(circles)
        x, y, radius = moved[focus]
        assert radius <= x <= 63 - radius and radius <= y <= 63 - radius
        assert data.targets(moved, valid)["center"][0, int(y // 4), int(x // 4)] == 1
        scale = moved[:, 2] / circles[:, 2]
        np.testing.assert_allclose(scale, scale[0])
        assert 0.75 <= scale[0] <= 1.25
        np.testing.assert_allclose(np.linalg.norm(moved[1, :2] - moved[0, :2]),
                                   scale[0] * np.linalg.norm(circles[1, :2] - circles[0, :2]))
        assert not image[~valid].any()
        positions.append([x, y])
    assert np.ptp(positions, axis=0).min() > 2


def test_in_memory_padding_and_all_known_background_remain_valid(tmp_path, monkeypatch):
    manifest, circles, pixels = _fixture(tmp_path)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert "evaluation" not in path.parts
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    views = data.TrainingViews(manifest, "synthetic", size=128, count=1)
    image, moved, valid = views[0]
    assert valid[:64, :96].all()
    assert not valid[64:].any() and not valid[:, 96:].any()
    assert not image[~valid].any()
    np.testing.assert_allclose(moved, circles)
    target = data.targets(moved, valid)
    assert target["valid"].sum() == (64 // 4) * (96 // 4)
    assert target["center"].sum() == len(circles)
    assert np.count_nonzero(target["valid"] - target["center"]) == 384 - len(circles)


def test_in_memory_view_input_and_epoch_validation(tmp_path):
    manifest, _, _ = _fixture(tmp_path)
    for options in ({"count": 0}, {"size": 31}, {"size": 33}, {"seed": -1}):
        with pytest.raises(ValueError):
            data.TrainingViews(manifest, "synthetic", **options)
    views = data.TrainingViews(manifest, "synthetic", size=64, count=1)
    for epoch in (-1, 0.5, True):
        with pytest.raises(ValueError):
            views.set_epoch(epoch)
    with pytest.raises(IndexError):
        views[len(views)]


def test_synthetic_fit_reader_uses_verified_local_pngs_only(tmp_path):
    manifest, circles, pixels = _fixture(tmp_path)
    image_path = tmp_path / "fit-local.png"
    Image.fromarray(pixels).save(image_path)
    labels = tmp_path / "labels.json"
    fit = {"id": "fit-local", "split": "fit", "recording": "synthetic-recording",
           "complete_labels": True,
           "source": "/must/not/be/read/stale.png", "width": 96, "height": 64,
           "sha256": data._hash(image_path),
           "targets": [{"x": x, "y": y, "radius": r} for x, y, r in circles]}
    labels.write_text(json.dumps({"scenes": [fit, {"id": "missing", "split": "validation"},
                                            {"id": "missing-too", "split": "calibration"}]}))
    scenes = data.read_synthetic_fit(labels)
    assert len(scenes) == 1
    np.testing.assert_array_equal(scenes[0]["image"], pixels)
    np.testing.assert_allclose(scenes[0]["circles"], circles)
    assert scenes[0]["source"]["split"] == "fit"
    assert scenes[0]["source"]["image_sha256"] == data._hash(image_path)
    fit["sha256"] = "wrong"
    labels.write_text(json.dumps({"scenes": [fit]}))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        data.read_synthetic_fit(labels)


def test_synthetic_fit_reader_rejects_incomplete_labels_before_image_read(tmp_path):
    labels = tmp_path / "labels.json"
    for value in (False, None, 1):
        labels.write_text(json.dumps({"scenes": [{"id": "absent", "split": "fit",
                                                 "complete_labels": value}]}))
        with pytest.raises(ValueError, match="complete_labels=true"):
            data.read_synthetic_fit(labels)
    labels.write_text(json.dumps({"scenes": [{"id": "absent", "split": "fit"}]}))
    with pytest.raises(ValueError, match="complete_labels=true"):
        data.read_synthetic_fit(labels)


def test_original_training_requires_marked_circles(tmp_path):
    manifest, _, _ = _fixture(tmp_path)
    session = tmp_path / "training.icescopy"
    with zipfile.ZipFile(session) as archive:
        payload = json.loads(archive.read("session.json"))
    payload["cell_items"] = []
    payload["keyframe_cell_items_dict"] = {}
    with zipfile.ZipFile(session, "w") as archive:
        archive.writestr("session.json", json.dumps(payload))
    with pytest.raises(ValueError, match="marked circles"):
        data.TrainingViews(manifest, "synthetic")


def _scene_views(image, circles, *, size=64, count=12, seed=3):
    return data.TrainingViews.from_scene(
        image, circles, {"synthetic": True, "split": "fit", "complete_labels": True,
                         "recording_id": "verified-scene"},
        setup="synthetic", size=size, count=count, seed=seed)


def test_episode_shared_orientation_lighting_and_query_radius(monkeypatch):
    image = np.zeros((128, 128, 3), np.uint8)
    image[64, 67, 0] = 255
    image[68, 64, 1] = 255
    source_circle = np.array([[64, 64, 8]], float)
    views = _scene_views(image, source_circle)
    linear = np.array([[0, -1.25], [-1.25, 0]])
    matrix = np.column_stack((linear, [31.5, 31.5] - linear @ source_circle[0, :2]))
    monkeypatch.setattr(views, "_random_transform",
                        lambda rng, focus: (matrix, data.transform_circles(source_circle, matrix)))
    lighting_calls = []
    original_lighting = data._lighting

    def record_lighting(pixels, params, valid):
        lighting_calls.append(dict(params))
        return original_lighting(pixels, params, valid)

    monkeypatch.setattr(data, "_lighting", record_lighting)
    query, circles, valid, refs, mask, radii = views.episode(views.tile_count)
    assert lighting_calls[0] == lighting_calls[1]
    np.testing.assert_array_equal(mask, [True, False])
    np.testing.assert_allclose(radii, [10, 0])
    assert not refs[1].any()
    np.testing.assert_allclose(circles, [[31.5, 31.5, 10]])
    # Original red (+3x) and green (+4y) marks share reflected/rotated axes.
    expected_query = [(31.5, 27.75), (26.5, 31.5)]
    expected_refs = [(31.5, 23.5), (20.833333, 31.5)]
    for channel in (0, 1):
        row, col = np.unravel_index(np.argmax(query[..., channel]), query.shape[:2])
        np.testing.assert_allclose([col, row], expected_query[channel], atol=0.75)
        row, col = np.unravel_index(np.argmax(refs[0, ..., channel]), refs.shape[1:3])
        np.testing.assert_allclose([col, row], expected_refs[channel], atol=0.75)
    for actual, expected in zip((query, circles, valid), views[views.tile_count]):
        np.testing.assert_array_equal(actual, expected)


def test_background_query_keeps_positive_full_source_examples():
    image = np.zeros((96, 96, 3), np.uint8)
    image[16, 16] = [255, 40, 20]
    views = _scene_views(image, [[16, 16, 4]], size=32, count=1)
    index = views.tiles.index((64, 64))
    query, circles, valid, refs, mask, radii = views.episode(index)
    assert data.targets(circles, valid)["center"].sum() == 0
    assert valid.all()
    np.testing.assert_array_equal(mask, [True, False])
    np.testing.assert_allclose(radii, [4, 0])
    assert refs[0, ..., 0].max() > query[..., 0].max() + 100
    row, col = np.unravel_index(np.argmax(refs[0, ..., 0]), refs.shape[1:3])
    np.testing.assert_allclose([col, row], [31.5, 31.5], atol=0.5)


def test_episode_reproducibility_epoch_changes_and_one_or_two_examples(tmp_path):
    manifest, circles, image = _fixture(tmp_path)
    first = _scene_views(image, circles, count=16, seed=17)
    second = _scene_views(image, circles, count=16, seed=17)
    example_counts = set()
    for index in range(len(first)):
        episode = first.episode(index)
        for actual, expected in zip(episode, second.episode(index)):
            np.testing.assert_array_equal(actual, expected)
        _, moved, _, refs, mask, radii = episode
        assert refs.shape == (2, 64, 64, 3) and refs.dtype == np.uint8
        assert mask.shape == (2,) and mask.dtype == bool
        assert radii.dtype == np.float32
        assert np.all(np.isclose(radii[mask, None], moved[:, 2]).any(axis=1))
        assert not refs[~mask].any() and not radii[~mask].any()
        example_counts.add(int(mask.sum()))
    assert example_counts == {1, 2}
    original = first.episode(first.tile_count)
    first.set_epoch(1)
    second.set_epoch(1)
    changed = first.episode(first.tile_count)
    assert not np.array_equal(original[1], changed[1])
    assert not np.array_equal(original[3], changed[3])
    for actual, expected in zip(changed, second.episode(second.tile_count)):
        np.testing.assert_array_equal(actual, expected)


def test_runtime_examples_keep_original_radii_and_require_one_or_two_marks():
    image = np.zeros((80, 100, 3), np.uint8)
    image[20, 20] = [250, 80, 40]
    image[50, 70] = [40, 120, 250]
    refs, mask, radii = data.extract_examples(image, [[20, 20, 5], [70, 50, 8]])
    assert refs.shape == (2, 64, 64, 3)
    np.testing.assert_array_equal(mask, [True, True])
    np.testing.assert_array_equal(radii, [5, 8])
    assert refs[0, 31:33, 31:33, 0].max() > 100
    assert refs[1, 31:33, 31:33, 2].max() > 100
    for circles in ([], [[20, 20, 5]] * 3, [[101, 20, 5]]):
        with pytest.raises(ValueError):
            data.extract_examples(image, circles)
