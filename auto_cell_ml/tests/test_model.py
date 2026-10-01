"""Check negative supervision, learned geometry, export, and inference seams."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from infer import detect, read_rgb, tile_intervals
from model import DropletNet, load_model, loss


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
            torch.save({"format": "icescopy-droplet-net-v1", "state_dict": net.state_dict()}, path)
            restored, _ = load_model(path)
            for k, expected in net(image).items():
                torch.testing.assert_close(restored(image)[k], expected)

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


if __name__ == "__main__":
    unittest.main()
