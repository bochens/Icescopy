"""Check example conditioning, dense supervision, staged provenance and inference."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image
import torch
from torchvision.models import mobilenet_v3_small

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from infer import detect, read_rgb, run, tile_intervals
from model import DropletNet, FORMAT, export_onnx, load_model, loss
from data import targets
from train import fit


def _references(batch=1):
    return (torch.rand(batch, 2, 3, 64, 64), torch.tensor([[True, False]]).expand(batch, -1),
            torch.tensor([[6., 0.]]).expand(batch, -1))


def _source(folder, name, circles):
    pixels = np.full((32, 32, 3), 90, np.uint8)
    yy, xx = np.mgrid[:32, :32]
    for x, y, r in circles:
        pixels[np.hypot(xx - x, yy - y) < r] = 30
    image = folder / (name + ".png")
    Image.fromarray(pixels).save(image)
    session = folder / (name + ".icescopy")
    state = {"schema_version": 6, "frame_source": {"kind": "image_sequence", "image_paths": [image.name]},
             "image_index": 0, "cell_items": [{"circle_pixel_positions": [x, y], "circle_sizes": r, "cell_id": i}
             for i, (x, y, r) in enumerate(circles)]}
    with zipfile.ZipFile(session, "w") as archive:
        archive.writestr("session.json", json.dumps(state))
    return {"setup": name, "train": {"recording_id": name, "image": image.name, "session": session.name,
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(), "label_status": "user_marked",
            "circle_count": len(circles)}, "evaluation": {"image": "evaluation/forbidden.png"}}


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.storage = tempfile.TemporaryDirectory()
        cls.pretrained = Path(cls.storage.name) / "local-backbone.pth"
        torch.manual_seed(11)
        torch.save(mobilenet_v3_small(weights=None).state_dict(), cls.pretrained)

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def test_confident_background_is_penalized_and_padding_ignored(self):
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

    def test_arbitrary_count_and_preaggregated_reference_match(self):
        net = DropletNet(self.pretrained).eval()
        query = torch.rand(1, 3, 64, 64)
        refs = torch.rand(1, 5, 3, 64, 64)
        radii = torch.tensor([[6., 7., 8., 9., 10.]])
        with torch.inference_mode():
            for count in (1, 2, 3, 5):
                picked = refs[:, :count]
                direct = net(query, picked, torch.ones(1, count, dtype=torch.bool), radii[:, :count])
                descriptor = net.encode_reference(picked.reshape(count, 3, 64, 64)).mean(0, keepdim=True)
                separate = net.predict_with_reference(query, descriptor, radii[:, :count].mean().reshape(1, 1, 1, 1))
                for key in direct:
                    torch.testing.assert_close(direct[key], separate[key])
            repeated = net(query, refs[:, :1].expand(-1, 5, -1, -1, -1),
                           torch.ones(1, 5, dtype=torch.bool), radii[:, :1].expand(-1, 5))
            single = net(query, refs[:, :1], torch.ones(1, 1, dtype=torch.bool), radii[:, :1])
            torch.testing.assert_close(repeated['center'], single['center'], atol=1e-5, rtol=1e-5)

    def test_appearance_radius_mask_conditioning_and_reference_gradients(self):
        torch.manual_seed(7)
        net = DropletNet(self.pretrained).train()
        image = torch.rand(1, 3, 64, 64)
        examples, mask, radii = _references()
        examples.requires_grad_()
        first = net(image, examples, mask, radii)
        self.assertEqual(tuple(first["center"].shape), (1, 1, 16, 16))
        changed = examples.detach().clone(); changed[:, 0] = 0
        self.assertGreater((net(image, changed, mask, radii)["center"] - first["center"]).abs().max().item(), 1e-7)
        larger = radii.clone(); larger[:, 0] = 24
        self.assertGreater((net(image, examples, mask, larger)["center"] - first["center"]).abs().max().item(), 1e-5)
        inactive = examples.detach().clone(); inactive[:, 1] = 1
        torch.testing.assert_close(net(image, inactive, mask, torch.tensor([[6., 999.]]))["center"], first["center"])
        target = {key: torch.from_numpy(value)[None] for key, value in
                  targets([[18.5, 18.5, 6]], np.ones((64, 64), bool)).items()}
        loss(first, target)["total"].backward()
        self.assertGreater(examples.grad[:, 0].abs().sum().item(), 0)
        self.assertEqual(examples.grad[:, 1].abs().sum().item(), 0)
        self.assertFalse(any(module.training for module in net.encoder.modules() if isinstance(module, torch.nn.BatchNorm2d)))
        with self.assertRaisesRegex(ValueError, "active examples"):
            net(image, examples, torch.zeros_like(mask), radii)

    def test_bounded_learning_and_portable_weight_roundtrip(self):
        torch.manual_seed(4)
        net = DropletNet(self.pretrained).train()
        image = torch.rand(1, 3, 32, 32)
        examples, mask, radii = _references()
        target = {key: torch.from_numpy(value)[None] for key, value in
                  targets([[12.3, 12.7, 6]], np.ones((32, 32), bool)).items()}
        optimizer = torch.optim.Adam(net.parameters(), lr=.001)
        initial = loss(net(image, examples, mask, radii), target)["total"].item()
        for _ in range(8):
            optimizer.zero_grad(set_to_none=True)
            terms = loss(net(image, examples, mask, radii), target)
            terms["total"].backward()
            optimizer.step()
        self.assertLess(loss(net(image, examples, mask, radii), target)["total"].item(), initial)
        net.eval()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.pt"
            torch.save({"format": FORMAT, "state_dict": net.state_dict()}, path)
            moved = Path(temp) / "relocated.pt"; path.rename(moved)
            restored, _ = load_model(moved)
            for key, expected in net(image, examples, mask, radii).items():
                torch.testing.assert_close(restored(image, examples, mask, radii)[key], expected)

    def test_pretrained_initialization_is_strict_and_never_downloads(self):
        with mock.patch("torch.hub.load_state_dict_from_url", side_effect=AssertionError("No download")):
            net = DropletNet(self.pretrained)
        original = torch.load(self.pretrained, weights_only=True)
        torch.testing.assert_close(net.encoder[0][0].weight, original["features.0.0.weight"])
        with tempfile.TemporaryDirectory() as temp:
            original.pop("classifier.3.bias")
            broken = Path(temp) / "broken.pth"; torch.save(original, broken)
            with self.assertRaises(RuntimeError):
                DropletNet(broken)

    def test_staged_and_warm_fit_preserve_sources_weights_and_epoch_history(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            rows = [_source(folder, "first", [[10, 10, 3]]), _source(folder, "second", [[10, 10, 3], [23, 23, 3]])]
            rows.append({"setup": "unmarked", "train": {"label_status": "unlabeled"}})
            manifest = folder / "datasets.json"; manifest.write_text(json.dumps({"setups": rows}))
            syn = folder / "fit.png"; Image.fromarray(np.full((32, 32, 3), 100, np.uint8)).save(syn)
            synthetic = folder / "labels.json"
            synthetic.write_text(json.dumps({"scenes": [
                {"id": "fit", "split": "fit", "complete_labels": True, "width": 32, "height": 32,
                 "sha256": hashlib.sha256(syn.read_bytes()).hexdigest(), "recording": "synthetic",
                 "targets": [{"x": 12, "y": 12, "radius": 3}]},
                {"id": "heldout", "split": "validation"}]}))
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.iterdir()}
            original_open = Path.open
            def guarded(path, *args, **kwargs):
                self.assertNotIn("evaluation", path.parts)
                self.assertNotIn("heldout", path.name)
                return original_open(path, *args, **kwargs)
            destination = folder / "model"
            options = dict(pretrained=self.pretrained, synthetic_manifest=synthetic, all_setups=True,
                           views=1, synthetic_views=1, size=32, batch_size=2, threads=2)
            with mock.patch.object(Path, "open", guarded), mock.patch("torch.hub.load_state_dict_from_url", side_effect=AssertionError("No download")):
                result = fit(manifest, destination, synthetic_epochs=1, epochs=1, **options)
            metadata = json.loads((destination / "metadata.json").read_text())
            self.assertEqual(metadata["format"], FORMAT)
            self.assertEqual(metadata["setup"], "general")
            self.assertEqual(metadata["setups"], ["first", "second"])
            self.assertEqual([stage["stage"] for stage in metadata["stages"]], ["synthetic", "real"])
            self.assertEqual([source["views_per_epoch"] for source in metadata["source"]], [3, 3])
            self.assertFalse(metadata["evaluation_used_for_training"] or metadata["conditioning"]["runtime_training"])
            self.assertTrue(metadata["pretrained"])
            self.assertEqual(load_model(result)[1]["format"], FORMAT)
            for row in json.loads((destination / "training.json").read_text()):
                self.assertGreater(row["positive_grid_cells"], 0)
                self.assertGreater(row["negative_grid_cells"], 0)
                self.assertEqual(row["positive_grid_cells"] + row["negative_grid_cells"], row["valid_grid_cells"])
            for path, digest in before.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                fit(manifest, destination, pretrained=self.pretrained, synthetic_manifest=synthetic, all_setups=True)
            self.assertEqual(set(destination.iterdir()), {destination / name for name in ("model.pt", "metadata.json", "training.json")})
            # Older exports have epochs but no cumulative field. Their weights
            # and optimizer state are deliberately treated separately.
            payload = torch.load(result, weights_only=True)
            payload.pop("total_real_epochs")
            parent = folder / "parent.pt"; torch.save(payload, parent)
            parent_sha = hashlib.sha256(parent.read_bytes()).hexdigest()
            loaded = {}
            real_adam = torch.optim.AdamW
            def inspect_load(path, device):
                net, info = load_model(path, device)
                loaded["model"] = net
                return net, info
            def fresh_optimizer(groups, **kwargs):
                for key, value in loaded["model"].state_dict().items():
                    torch.testing.assert_close(value, payload["state_dict"][key])
                optimizer = real_adam(groups, **kwargs)
                self.assertEqual(len(optimizer.state), 0)
                self.assertEqual([group["lr"] for group in optimizer.param_groups], [.0001, .0005])
                return optimizer
            continued = folder / "continued"
            with mock.patch("train.data.read_synthetic_fit", side_effect=AssertionError("No synthetic reread")), \
                    mock.patch("train.load_model", side_effect=inspect_load), \
                    mock.patch("train.torch.optim.AdamW", side_effect=fresh_optimizer):
                warm = fit(manifest, continued, initial_model=parent, synthetic_epochs=0, epochs=2,
                           encoder_learning_rate=.0001, head_learning_rate=.0005, **options)
            current = json.loads((continued / "metadata.json").read_text())
            self.assertEqual(current["initialization"], "saved model weights with fresh optimizer")
            self.assertEqual(current["optimizer"]["state_initialization"], "fresh")
            self.assertEqual(current["parent_model_sha256"], parent_sha)
            self.assertEqual(current["total_real_epochs"], 3)
            self.assertEqual(current["parent_provenance"]["source"], payload["source"])
            self.assertEqual(current["synthetic_manifest_sha256"], payload["synthetic_manifest_sha256"])
            self.assertEqual([(row["stage"], row["epoch"]) for row in json.loads((continued / "training.json").read_text())],
                             [("real", 2), ("real", 3)])
            self.assertEqual((current["stages"][0]["first_epoch"], current["stages"][0]["last_epoch"]), (2, 3))
            self.assertEqual(hashlib.sha256(parent.read_bytes()).hexdigest(), parent_sha)
            self.assertFalse(all(torch.equal(value, payload["state_dict"][key]) for key, value in
                                 torch.load(warm, weights_only=True)["state_dict"].items()))
            for key, bad in (("setups", ["different"]), ("crop_size", 64),
                             ("training_manifest_sha256", "wrong"), ("pretrained_sha256", "wrong"),
                             ("synthetic_manifest_sha256", "wrong"), ("source", [])):
                incompatible = folder / "incompatible.pt"
                torch.save({**payload, key: bad}, incompatible)
                rejected = folder / "rejected"
                with self.assertRaisesRegex(ValueError, "incompatible"):
                    fit(manifest, rejected, initial_model=incompatible, synthetic_epochs=0, epochs=1, **options)
                self.assertFalse(rejected.exists())
            for initial, synthetic_epochs in ((None, 0), (parent, 1)):
                with self.assertRaisesRegex(ValueError, "synthetic_epochs"):
                    fit(manifest, folder / "invalid-stage", initial_model=initial,
                        synthetic_epochs=synthetic_epochs, epochs=1, **options)

    def test_optional_onnx_dependency_is_explicit(self):
        if importlib.util.find_spec("onnx") is not None:
            self.skipTest("ONNX runtime verification is separate when its dependency is installed")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.onnx"
            with self.assertRaisesRegex(RuntimeError, "onnx"):
                export_onnx(DropletNet().eval(), path, size=32)
            self.assertFalse(path.exists())

    def test_tile_ownership_has_no_gaps_or_double_owned_pixels(self):
        for length in (1, 384, 385, 640, 1280, 2592):
            owners = np.zeros(length)
            for origin, left, right in tile_intervals(length, 384, 96):
                self.assertGreaterEqual(left, origin); self.assertLessEqual(right, origin + 384)
                owners += (np.arange(length) >= left) & (np.arange(length) < right)
            np.testing.assert_array_equal(owners, np.ones(length))

    def test_detector_decodes_geometry_padding_and_excludes_all_existing(self):
        class Fixed(torch.nn.Module):
            stride = 4
            def forward(self, x, examples, mask, radii):
                b = len(x); side = x.shape[-1] // 4
                logits = torch.full((b, 1, side, side), -20.)
                logits[:, :, 2, 2] = 20; logits[:, :, -1, -1] = 20
                return {"center": logits, "offsets": torch.full((b, 2, side, side), .25), "log_radius": torch.zeros(b, 1, side, side)}
        image = np.zeros((20, 20, 3), np.uint8)
        found = detect(Fixed(), image, examples=[[0, 0, 1]], size=32)
        self.assertEqual([(c["x"], c["y"], c["radius"]) for c in found], [(9, 9, 16)])
        self.assertEqual(detect(Fixed(), image, examples=[[9, 9, 2]], size=32), [])
        self.assertEqual(detect(Fixed(), image, examples=[[0, 0, 1]], existing_circles=[[9, 9, 2]], size=32), [])

    def test_seam_suppression_and_overlapping_distinct_centers(self):
        class Seam(torch.nn.Module):
            stride = 4
            def __init__(self, centers):
                super().__init__(); self.centers = centers
            def forward(self, x, examples, mask, radii):
                side = x.shape[-1] // 4
                logits = torch.full((len(x), 1, side, side), -20.)
                offsets = torch.full((len(x), 2, side, side), .25)
                for b, center in enumerate(self.centers):
                    local_x = center - b * 256
                    logits[b, 0, 25, int(local_x // 4)] = 20
                    offsets[b, 0, 25, int(local_x // 4)] = local_x / 4 % 1
                return {"center": logits, "offsets": offsets, "log_radius": torch.zeros(len(x), 1, side, side)}
        for centers in ([317, 321], [321, 317], [317, 341]):
            found = detect(Seam(centers), np.zeros((200, 640, 3), np.uint8), examples=[[5, 5, 2]])
            self.assertEqual(len(found), 1 if abs(centers[0] - centers[1]) < 16 else 2)

    def test_read_uint16_and_inference_output_keeps_seeds_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); image = folder / "image.png"
            Image.fromarray(np.tile(np.array([0, 32768, 65535], np.uint16), (32, 1))).save(image)
            np.testing.assert_array_equal(read_rgb(image)[0, :, 0], [0, 128, 255])
            model = folder / "model.pt"
            torch.save({"format": FORMAT, "setup": "general", "crop_size": 32,
                        "state_dict": DropletNet().state_dict()}, model)
            prefix = folder / "prediction"
            result = run(model, image, prefix, examples=[[1, 15, 1]], threads=2)
            self.assertEqual(result["examples"], [[1., 15., 1.]])
            self.assertFalse(result["runtime_training"])
            self.assertNotIn("accuracy", result)
            with self.assertRaises(FileExistsError):
                run(model, image, prefix, examples=[[1, 15, 1]])


if __name__ == "__main__":
    unittest.main()
