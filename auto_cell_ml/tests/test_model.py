"""Check negative supervision, learned geometry, export, and inference seams."""
import sys
import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from infer import detect, read_rgb, tile_intervals
from model import DropletNet, FORMAT, export_onnx, load_model, loss
from data import targets
from train import fit


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_confident_false_positive_is_penalized_and_padding_ignored(self):
        target = {"center": torch.zeros(1, 1, 2, 2), "valid": torch.ones(1, 1, 2, 2),
                  "offsets": torch.zeros(1, 2, 2, 2), "log_radius": torch.zeros(1, 1, 2, 2)}
        logits = torch.full((1, 1, 2, 2), -5.0, requires_grad=True)
        pred = {"center": logits, "offsets": target["offsets"], "log_radius": target["log_radius"]}
        base = loss(pred, target)["total"].item()
        with torch.no_grad():
            logits[0, 0, 0, 0] = 5
        terms = loss(pred, target)
        self.assertGreater(terms["total"].item(), base + 4)
        terms["total"].backward()
        self.assertGreater(logits.grad[0, 0, 0, 0].item(), 0)
        target["valid"][0, 0, 0, 0] = 0
        self.assertLess(loss(pred, target)["total"].item(), base)

    def test_shape_training_gradient_and_export_roundtrip(self):
        torch.manual_seed(7)
        net = DropletNet().train()
        image = torch.rand(1, 3, 64, 64)
        p = net(image)
        self.assertEqual(tuple(p["center"].shape), (1, 1, 16, 16))
        target = {"center": torch.zeros_like(p["center"]), "valid": torch.ones_like(p["center"]),
                  "offsets": torch.full_like(p["offsets"], 0.3), "log_radius": torch.zeros_like(p["log_radius"])}
        target["center"][0, 0, 8, 8] = 1
        optimizer = torch.optim.Adam(net.parameters(), lr=0.001)
        first = loss(p, target)["total"].item()
        for _ in range(8):
            optimizer.zero_grad()
            value = loss(net(image), target)["total"]
            value.backward()
            optimizer.step()
        self.assertLess(loss(net(image), target)["total"].item(), first)
        self.assertTrue(any(p.grad is not None and p.grad.abs().sum() > 0 for p in net.encoder.parameters()))
        net.eval()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.pt"
            torch.save({"format": FORMAT, "state_dict": net.state_dict()}, path)
            restored, _ = load_model(path)
            for k, expected in net(image).items():
                torch.testing.assert_close(restored(image)[k], expected)

    def test_small_cnn_learns_filled_center_and_rejects_empty_circle(self):
        torch.manual_seed(3)
        yy, xx = np.mgrid[:64, :64]
        pixels = np.full((64, 64, 3), 95, np.uint8)
        for x, y in ((18.5, 18.5), (44.5, 44.5)):
            distance = np.hypot(xx - x, yy - y)
            pixels[np.abs(distance - 6) < 1] = 230
            if x < 30:
                pixels[distance < 5] = 35
        image = torch.from_numpy(pixels.transpose(2, 0, 1).copy()).float()[None] / 255
        target = {key: torch.from_numpy(value)[None]
                  for key, value in targets([[18.5, 18.5, 6]], np.ones((64, 64), bool)).items()}
        net = DropletNet().train()
        optimizer = torch.optim.AdamW(net.parameters(), lr=0.001)
        first = float(loss(net(image), target)["total"].detach())
        for _ in range(100):
            optimizer.zero_grad(set_to_none=True)
            terms = loss(net(image), target)
            terms["total"].backward()
            optimizer.step()
        prediction = net(image)
        self.assertLess(float(loss(prediction, target)["total"].detach()), first / 5)
        self.assertGreater(float(prediction["center"][0, 0, 4, 4].sigmoid().detach()), 0.5)
        self.assertLess(float(prediction["center"][0, 0, 11, 11].sigmoid().detach()), 0.5)
        self.assertEqual(sum(parameter.numel() for parameter in net.parameters()), 92788)
        self.assertFalse(any(isinstance(module, (torch.nn.BatchNorm2d, torch.nn.GroupNorm))
                             for module in net.modules()))

    def test_training_views_smoke_preserves_outputs_and_requires_no_pretrained_file(self):
        class Views:
            def __init__(self, manifest, setup, *, size, count, seed):
                self.source = {"recording_id": "fixture-A", "image_sha256": "fixture-source"}
                self.setup, self.size, self.tile_count, self.circle_count = setup, size, 1, 1
            def __len__(self):
                return 2
            def set_epoch(self, epoch):
                self.epoch = epoch
            def __getitem__(self, index):
                return np.zeros((self.size, self.size, 3), np.uint8), [[12, 12, 3]], np.ones((self.size, self.size), bool)
        with tempfile.TemporaryDirectory() as folder, mock.patch("train.data.TrainingViews", Views), \
                mock.patch("torch.hub.load_state_dict_from_url", side_effect=AssertionError("No pretrained download")):
            manifest = Path(folder) / "datasets.json"
            manifest.write_text("{}")
            destination = Path(folder) / "model"
            path = fit(manifest, destination, setup="fixture", epochs=1, views=2, size=32, batch_size=2)
            metadata = json.loads((destination / "metadata.json").read_text())
            self.assertEqual(metadata["format"], FORMAT)
            self.assertFalse(metadata["pretrained"] or metadata["evaluation_used_for_training"])
            self.assertEqual(metadata["source"]["recording_id"], "fixture-A")
            history = json.loads((destination / "training.json").read_text())
            self.assertEqual(history[0]["positive_grid_cells"], 2)
            self.assertEqual(history[0]["negative_grid_cells"], 126)
            self.assertEqual(load_model(path)[1]["setup"], "fixture")
            with self.assertRaises(FileExistsError):
                fit(manifest, destination, setup="fixture", epochs=1, views=2, size=32)
            self.assertEqual(manifest.read_text(), "{}")

    def test_optional_onnx_export_or_explicit_dependency_limitation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.onnx"
            model = DropletNet().eval()
            if importlib.util.find_spec("onnx") is None:
                with self.assertRaisesRegex(RuntimeError, "onnx"):
                    export_onnx(model, path, size=32)
                self.assertFalse(path.exists())
                return
            export_onnx(model, path, size=32)
            import cv2
            image = torch.rand(1, 3, 32, 32)
            with torch.inference_mode():
                prediction = model(image)
                expected = torch.cat([prediction[key] for key in ("center", "offsets", "log_radius")], dim=1).numpy()
            runtime = cv2.dnn.readNetFromONNX(str(path))
            runtime.setInput(image.numpy())
            np.testing.assert_allclose(runtime.forward(), expected, rtol=1e-4, atol=1e-5)
            with self.assertRaises(FileExistsError):
                export_onnx(model, path)

    def test_tile_ownership_has_no_gaps_or_double_owned_pixels(self):
        for length in (1, 384, 385, 640, 1280, 2592):
            intervals = tile_intervals(length, 384, 96)
            owners = np.zeros(length)
            for origin, left, right in intervals:
                self.assertGreaterEqual(left, origin)
                self.assertLessEqual(right, origin + 384)
                owners += (np.arange(length) >= left) & (np.arange(length) < right)
            np.testing.assert_array_equal(owners, np.ones(length))

    def test_detector_decodes_center_radius_and_rejects_padding(self):
        class Fixed(torch.nn.Module):
            stride = 4
            def forward(self, x):
                b = len(x);side = x.shape[-1] // 4
                logits = torch.full((b, 1, side, side), -20.)
                logits[:, :, 2, 2] = 20
                logits[:, :, -1, -1] = 20
                return {"center": logits, "offsets": torch.full((b, 2, side, side), 0.25),
                        "log_radius": torch.zeros(b, 1, side, side)}
        found = detect(Fixed(), np.zeros((20, 20, 3), dtype=np.uint8), size=32)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["x"], found[0]["y"], found[0]["radius"]), (9, 9, 16))

    def test_16bit_intensity_is_scaled_not_clipped(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "image.png"
            Image.fromarray(np.array([[0, 32768, 65535]], dtype=np.uint16)).save(path)
            rgb = read_rgb(path)
            np.testing.assert_array_equal(rgb[0, :, 0], [0, 128, 255])

    def test_overlap_predictions_cannot_duplicate_or_drop_a_seam_circle(self):
        class Seam(torch.nn.Module):
            stride = 4
            def __init__(self, centers):
                super().__init__()
                self.centers = centers
            def forward(self, x):
                side = x.shape[-1] // 4
                logits = torch.full((len(x), 1, side, side), -20.)
                offsets = torch.full((len(x), 2, side, side), 0.25)
                for b, center in enumerate(self.centers):
                    local_x = center - b * 256
                    logits[b, 0, 25, int(local_x // 4)] = 20
                    offsets[b, 0, 25, int(local_x // 4)] = local_x / 4 % 1
                return {"center": logits, "offsets": offsets,
                        "log_radius": torch.zeros(len(x), 1, side, side)}
        for centers in ([317, 321], [321, 317]):
            found = detect(Seam(centers), np.zeros((200, 640, 3), dtype=np.uint8))
            self.assertEqual(len(found), 1)

    def test_intersecting_distinct_cells_more_than_one_radius_apart_survive(self):
        class Fixed(torch.nn.Module):
            stride = 4
            def forward(self, image):
                logits = torch.full((1, 1, 16, 16), -20.)
                logits[0, 0, 5, [5, 11]] = 20
                return {"center": logits, "offsets": torch.full((1, 2, 16, 16), 0.25),
                        "log_radius": torch.zeros_like(logits)}
        found = detect(Fixed(), np.zeros((64, 64, 3), np.uint8), size=64)
        self.assertEqual([circle["x"] for circle in found], [21, 45])


if __name__ == "__main__":
    unittest.main()
