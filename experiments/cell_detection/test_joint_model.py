"""Actual conditioning, weight updates and strict joint-checkpoint contracts."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
import torch

from detector import Circle
from joint_model import JointDetector, JointNetwork, input_tensor, save_joint
from joint_train import joint_loss, optimizer_for, CONFIG
from neural_model import batchnorm_buffers, prefix_state, tensor_hash


class JointModelTests(unittest.TestCase):
    def test_reviewed_negative_bce_penalizes_modest_confidence_only_where_known(self):
        logits = torch.full((1, 1, 3, 3), float(np.log(.2/.8)), requires_grad=True)
        heat = torch.zeros_like(logits); heat[0, 0, 0, 0] = 1
        mask = heat.clone(); mask[0, 0, 1, 1] = 1
        target = {'heat': heat, 'mask': mask, 'center_mask': heat,
                  'offset': torch.zeros((1, 2, 3, 3)), 'radius': torch.zeros_like(heat),
                  'reviewed_negative_mask': mask.clone()}
        predicted = {'logits': logits, 'offset': torch.zeros((1, 2, 3, 3)), 'log_radius': torch.zeros_like(heat)}
        with_bce, parts = joint_loss(predicted, target)
        without_bce, _ = joint_loss(predicted, target, dict(CONFIG, reviewed_negative_bce_weight=0.))
        self.assertAlmostEqual(parts['reviewed_negative_bce'], -np.log(.8), places=6)
        (with_bce-without_bce).backward()
        self.assertAlmostEqual(float(logits.grad[0, 0, 1, 1]), .2, places=6)
        self.assertAlmostEqual(float(logits.grad[0, 0, 0, 0]), 0., places=7)  # Float32 subtraction cancels to rounding precision.
        self.assertEqual(float(logits.grad[0, 0, 2, 2]), 0.)  # Unknown remains unknown.

    def test_content_conditioning_changes_predictions_before_and_after_update(self):
        torch.set_num_threads(2); torch.manual_seed(71)
        network = JointNetwork().train(True)
        pixels = np.random.default_rng(71).random((1, 128, 128, 3), dtype=np.float32)
        pixels[:, :, :64] *= np.array([.2, .5, .8]); pixels[:, :, 64:] *= np.array([.9, .3, .1])
        maps = network.prefix_maps(input_tensor(pixels))
        left = torch.tensor([[[8., 16., 4.]]]); right = torch.tensor([[[24., 16., 4.]]])
        frozen = tensor_hash(prefix_state(network.backbone)); bn = tensor_hash(batchnorm_buffers(network.backbone))
        before = network.backbone[10].state_dict()['block.0.0.weight'].detach().clone()
        features = network.decode(maps)
        descriptor_difference = float((network.queries(features, left)-network.queries(features, right)).abs().max().detach())
        first = network.predictions(features, left); other = network.predictions(features, right)
        self.assertGreater(descriptor_difference, 1e-4)
        self.assertGreater(float((first['logits']-other['logits']).abs().max().detach()), 1e-7)
        heat = torch.zeros_like(first['logits']); heat[:, :, 16, 8] = 1
        center_mask = heat.clone()
        target = {'heat': heat, 'mask': torch.ones_like(heat), 'center_mask': center_mask,
                  'offset': torch.full_like(first['offset'], .25), 'radius': torch.zeros_like(first['log_radius']),
                  'reviewed_negative_mask': torch.zeros_like(heat)}
        optimizer = optimizer_for(network, CONFIG); loss, _ = joint_loss(first, target)
        loss.backward(); optimizer.step()
        self.assertFalse(torch.equal(before, network.backbone[10].state_dict()['block.0.0.weight']))
        self.assertEqual(frozen, tensor_hash(prefix_state(network.backbone)))
        self.assertEqual(bn, tensor_hash(batchnorm_buffers(network.backbone)))
        with torch.no_grad():
            updated = network.decode(maps)
            self.assertGreater(float((network.predictions(updated, left)['logits']-network.predictions(updated, right)['logits']).abs().max()), 1e-7)
        self.assertTrue(all(not layer.training for layer in network.backbone.modules() if isinstance(layer, torch.nn.BatchNorm2d)))

    def test_reload_and_queries_outside_first_tile(self):
        torch.set_num_threads(2); torch.manual_seed(9)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'joint.pt'; save_joint(path, JointNetwork(), {'test': True})
            detector = JointDetector(path, threads=2)
            image = np.random.default_rng(9).random((96, 520, 3), dtype=np.float32)
            prepared = detector.prepare_frame(image, 16.)
            query = [Circle(450., 48., 16.)]
            # Query lies beyond the first stitched core; it is pooled from the
            # same global feature canvas, not clamped to the first tile.
            first = detector.predict_prepared(prepared, query, threshold=.99)
            reloaded = JointDetector(path, threads=2)
            second_prepared = reloaded.prepare_frame(image, 16.)
            self.assertTrue(torch.equal(prepared['features'], second_prepared['features']))
            self.assertEqual(first, reloaded.predict_prepared(second_prepared, query, threshold=.99))
            coordinates = torch.tensor([[[450/4, 48/4, 16/4]]])
            wrong_first_tile = torch.tensor([[[200/4, 48/4, 16/4]]])
            with torch.no_grad():
                global_query = detector.network.queries(prepared['features'], coordinates)
                clamped_query = detector.network.queries(prepared['features'], wrong_first_tile)
            self.assertGreater(float((global_query-clamped_query).abs().max()), 1e-5)
            with self.assertRaises(ValueError): detector.predict(image, [], threshold=.5)
            with self.assertRaises(ValueError): detector.predict_prepared(prepared, [Circle(521, 48, 16)], threshold=.5)
            with self.assertRaises(ValueError): detector.prepare_frame(np.empty((0, 3, 3), np.float32), 16)


if __name__ == '__main__': unittest.main()
