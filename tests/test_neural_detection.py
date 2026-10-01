"""CPU inference geometry and example-count contract without training dependencies."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import icescopy_neural_detection as detection


class FakeNet:
    def __init__(self, reference=False, centers=None):
        self.reference, self.centers = reference, centers
        self.inputs, self.calls, self.descriptors = {}, 0, []
    def empty(self):
        return False
    def setPreferableBackend(self, backend):
        self.backend = backend
    def setPreferableTarget(self, target):
        self.target = target
    def setInput(self, value, name):
        self.inputs[name] = value.copy()
    def forward(self, name):
        index = self.calls; self.calls += 1
        if self.reference:
            assert name == "descriptor"
            descriptor = np.full((1, 32, 1, 1), self.inputs["rgb"].mean(), np.float32)
            self.descriptors.append(descriptor.copy())
            return descriptor
        assert name == "prediction"
        raw = np.zeros((1, 4, 64, 64), np.float32)
        raw[:, 0] = -20; raw[:, 1:3] = .25
        centers = self.centers[index] if self.centers is not None else [(9, 9), (253, 253)]
        for x, y in centers:
            col, row = int(x // 4), int(y // 4)
            raw[0, 0, row, col] = 20
            raw[0, 1, row, col] = x / 4 % 1
            raw[0, 2, row, col] = y / 4 % 1
        return raw


class NeuralDetectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        for name in ("droplet_detector.onnx", "droplet_reference.onnx"):
            (self.root / name).write_bytes(name.encode())
        self.payload = {"format": detection.MODEL_FORMAT, "name": "General droplets",
            "model_file": "droplet_detector.onnx", "sha256": self.sha("droplet_detector.onnx"),
            "reference_model_file": "droplet_reference.onnx", "reference_sha256": self.sha("droplet_reference.onnx"),
            "tile_size": 256, "example_size": 64, "stride": 4, "threshold": .5,
            "default_reference": [value / 100 for value in range(32)], "default_radius": 7.,
            "provenance": {"setups": ["first", "second"]}}
        self.metadata = self.root / "droplet_detector.json"
        self.write_metadata()

    def sha(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def write_metadata(self):
        self.metadata.write_text(json.dumps(self.payload))

    def detector(self, centers=None):
        reference, query = FakeNet(True), FakeNet(centers=centers)
        def load(path):
            return reference if Path(path).name == "droplet_reference.onnx" else query
        with patch.object(cv2.dnn, "readNetFromONNX", side_effect=load):
            engine = detection.NeuralDetector(detection.load_model(self.metadata))
        return engine, reference, query

    def test_metadata_is_portable_validated_and_immutable(self):
        config = detection.load_model(self.metadata)
        self.assertEqual(config.onnx_path, (self.root / "droplet_detector.onnx").resolve())
        self.assertEqual(config.reference_onnx_path.name, "droplet_reference.onnx")
        with self.assertRaises(FrozenInstanceError):
            config.tile_size = 128
        with self.assertRaises(TypeError):
            config.metadata["name"] = "changed"
        with self.assertRaises(TypeError):
            config.metadata["provenance"]["setups"][0] = "changed"
        models = self.root / "models"; models.mkdir()
        for file in tuple(self.root.iterdir()):
            if file.is_file():
                file.rename(models / file.name)
        with patch.object(detection, "find_resources_dir", return_value=self.root):
            self.assertEqual(detection.load_model().onnx_path.parent, models.resolve())

    def test_missing_corrupt_and_incompatible_model_files_have_clear_errors(self):
        for key, value in (("format", "old"), ("tile_size", 128), ("default_reference", [0]),
                           ("default_radius", 0), ("model_file", "/absolute/model.onnx")):
            original = self.payload[key]; self.payload[key] = value; self.write_metadata()
            with self.assertRaises(ValueError):
                detection.load_model(self.metadata)
            self.payload[key] = original
        self.write_metadata()
        (self.root / "droplet_detector.onnx").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            detection.load_model(self.metadata)
        (self.root / "droplet_detector.onnx").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "missing"):
            detection.load_model(self.metadata)

    def test_reference_pixels_match_developer_extraction_including_fractional_padding(self):
        from auto_cell_ml.code.data import extract_examples
        yy, xx = np.mgrid[:70, :90]
        rgb = np.stack((xx * 2, yy * 3, xx + yy), axis=-1).astype(np.uint8)
        circles = [detection.Circle(.3, 2.7, 8.4), detection.Circle(43.25, 31.5, 5.8)]
        expected, _, _ = extract_examples(rgb, [[c.x, c.y, c.radius] for c in circles])
        for index, circle in enumerate(circles):
            blob = detection._reference_blob(rgb, circle, 64)
            np.testing.assert_array_equal(blob[0], expected[index].transpose(2, 0, 1).astype(np.float32) / 255)

    def test_zero_one_two_three_and_five_examples_use_correct_average_and_cpu(self):
        yy, xx = np.mgrid[:128, :128]
        rgb = np.stack((xx * 2, yy * 2, xx + yy), axis=-1).astype(np.uint8)
        choices = [detection.Circle(x, y, r) for x, y, r in ((5, 5, 2), (20, 20, 3), (50, 20, 4), (80, 50, 6), (100, 70, 7))]
        for count in (0, 1, 2, 3, 5):
            with self.subTest(count=count):
                engine, reference, query = self.detector()
                engine.predict(rgb, examples=choices[:count])
                self.assertEqual(reference.calls, count)
                self.assertEqual(query.calls, 1)
                self.assertEqual(query.backend, cv2.dnn.DNN_BACKEND_OPENCV)
                self.assertEqual(query.target, cv2.dnn.DNN_TARGET_CPU)
                expected = (np.mean(np.stack(reference.descriptors), axis=0, dtype=np.float32) if count else
                            np.asarray(engine.config.default_reference, np.float32).reshape(1, 32, 1, 1))
                np.testing.assert_array_equal(query.inputs["reference"], expected)
                radius = np.mean([c.radius for c in choices[:count]]) if count else engine.config.default_radius
                self.assertAlmostEqual(float(query.inputs["reference_radius"].item()), radius, places=6)

    def test_geometry_padding_selected_and_protected_exclusion(self):
        rgb = np.zeros((20, 20, 3), np.uint8)
        engine, _, _ = self.detector()
        found = engine.predict(rgb)
        self.assertEqual(found[0]["circle"], {"x": 9., "y": 9., "radius": 16.})
        self.assertEqual(len(found), 1)
        self.assertGreaterEqual(found[0]["score"], .5)
        self.assertEqual(engine.predict(rgb, examples=(detection.Circle(9, 9, 2),)), [])
        self.assertEqual(engine.predict(rgb, protected=(detection.Circle(9, 9, 2),)), [])

    def test_overlapping_tiles_deduplicate_but_distinct_intersecting_cells_survive(self):
        rgb = np.zeros((128, 448, 3), np.uint8)
        for second, expected in ((227, 1), (245, 2)):
            engine, _, _ = self.detector(centers=[[(225, 100)], [(second - 192, 100)]])
            found = engine.predict(rgb)
            self.assertEqual(len(found), expected)
        self.assertTrue(detection.same_object(detection.Circle(0, 0, 16), detection.Circle(15.99, 0, 20)))
        self.assertFalse(detection.same_object(detection.Circle(0, 0, 16), detection.Circle(16, 0, 20)))

    def test_cancel_between_examples_or_tiles_returns_no_partial_result(self):
        rgb = np.zeros((128, 448, 3), np.uint8)
        engine, ref, query = self.detector()
        self.assertEqual(engine.predict(rgb, examples=(detection.Circle(20, 20, 3), detection.Circle(30, 30, 3)),
                                        cancelled=lambda: ref.calls > 0), [])
        self.assertEqual((ref.calls, query.calls), (1, 0))
        engine, _, query = self.detector()
        self.assertEqual(engine.predict(rgb, cancelled=lambda: query.calls > 0), [])
        self.assertEqual(query.calls, 1)

    def test_invalid_image_and_examples_fail_before_network_forward(self):
        engine, reference, query = self.detector()
        for rgb in (np.zeros((0, 20, 3), np.uint8), np.zeros((20, 20), np.uint8), np.zeros((20, 20, 3), np.float32)):
            with self.assertRaisesRegex(ValueError, "RGB uint8"):
                engine.predict(rgb)
        with self.assertRaisesRegex(ValueError, "inside"):
            engine.predict(np.zeros((20, 20, 3), np.uint8), examples=(detection.Circle(25, 2, 3),))
        with self.assertRaises(ValueError):
            detection.Circle(1, 2, float("nan"))
        self.assertEqual((reference.calls, query.calls), (0, 0))


if __name__ == "__main__":
    unittest.main()
