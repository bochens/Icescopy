"""Geometry and supervision contracts; these are not accuracy tests."""
import unittest
import numpy as np

from joint_data import TileSchedule, affine_for, circle_usable, make_tile, targets_for, transformed
from joint_model import HALO, STRIDE, TILE


class JointGeometryTests(unittest.TestCase):
    def scene(self):
        return {'id': 'one', 'group': 'one', 'domain': 'real', 'split': 'fit', 'complete_labels': False,
                'targets': [{'id': 0, 'x': 192., 'y': 192., 'radius': 16.},
                            {'id': 1, 'x': 240., 'y': 192., 'radius': 20.}],
                'negatives': [{'id': 0, 'x': 110., 'y': 120., 'radius': 16.}],
                'center_negatives': [{'id': 1, 'x': 202., 'y': 192., 'radius': 16.}]}

    def test_unknown_and_halo_are_ignored_but_invalid_point_is_negative(self):
        scene = self.scene(); valid = np.ones((TILE, TILE), bool)
        target, positives, invalid, old = targets_for(scene, np.array([[1, 0, 0], [0, 1, 0]], np.float32), valid)
        self.assertEqual(set(positives), {0, 1}); self.assertEqual(invalid, [1]); self.assertEqual(old, [0])
        self.assertEqual(target['heat'][0, 48, 48], 1)
        self.assertEqual(target['heat'][0, 48, 50], 0)
        self.assertEqual(target['mask'][0, 48, 50], 1)
        # A neighbor outside the old0.35r neighborhood but inside the actual
        # droplet must be negative supervision, not an unpenalized rim peak.
        self.assertEqual(target['mask'][0, 46, 46], 1)
        self.assertEqual(target['heat'][0, 46, 46], 0)
        # Full reviewed empty radius is supervised, including its outer half.
        self.assertEqual(target['mask'][0, 30, 31], 1)
        self.assertEqual(target['reviewed_negative_mask'][0, 30, 31], 1)
        self.assertEqual(target['reviewed_negative_mask'][0, 48, 48], 0)
        self.assertEqual(target['mask'][0, 40, 40], 0)
        self.assertFalse(target['mask'][:, :HALO//STRIDE].any())
        self.assertFalse(target['mask'][:, :, -HALO//STRIDE:].any())

    def test_one_affine_retains_circles_and_valid_pixels(self):
        scene = self.scene(); image = np.zeros((384, 384, 3), np.float32)
        image[176:209, 176:209] = 1
        rng = np.random.default_rng(12); matrix = affine_for(scene, scene['targets'][0], rng)
        rows = transformed(scene['targets'], matrix)
        scale = np.linalg.norm(matrix[0, :2])
        self.assertAlmostEqual(rows[1]['radius']/rows[0]['radius'], 20/16)
        self.assertAlmostEqual(np.hypot(rows[1]['x']-rows[0]['x'], rows[1]['y']-rows[0]['y']), 48*scale, places=4)
        tile, target, queries, record = make_tile(scene, image, scene['targets'][0], np.random.default_rng(12))
        self.assertEqual(tile.shape, (384, 384, 3)); self.assertTrue(record['positive_ids'])
        self.assertTrue(np.all(queries[:, :2] >= 0)); self.assertTrue(np.all(queries[:, :2] < 96))
        # Reflection is visible context, never a manufactured background label.
        valid = np.ones((384, 384), bool); valid[:, :180] = False
        complete = dict(scene, complete_labels=True)
        partial, ids, _, _ = targets_for(complete, np.array([[1, 0, -40], [0, 1, 0]], np.float32), valid)
        self.assertNotIn(0, ids)
        self.assertEqual(partial['mask'][0, 48, 43], 0)

    def test_rounding_at_last_pixel_is_safe_and_updates_are_actual(self):
        self.assertFalse(circle_usable({'x': 367.8, 'y': 192., 'radius': 16.}, np.ones((384, 384), bool)))
        scene = self.scene()
        records = [{'index': 0, 'group': 'one', 'domain': 'real', 'split': 'fit', 'positive_ids': [0, 1],
                    'invalid_center_ids': [1], 'old_negative_ids': [0]},
                   {'index': 1, 'group': 'synthetic', 'domain': 'synthetic', 'split': 'fit',
                    'positive_ids': [3], 'invalid_center_ids': [], 'old_negative_ids': []}]
        schedule = TileSchedule(records, [scene]); sampled = schedule.sample(np.random.default_rng(1))
        self.assertFalse(schedule.all_positives_updated())
        schedule.mark_updated(sampled)
        self.assertTrue(schedule.all_positives_updated())
        self.assertEqual(schedule.coverage()['one']['updated_invalid_centers'], 1)
        self.assertEqual(schedule.coverage()['one']['updated_old_negatives'], 1)


if __name__ == '__main__': unittest.main()
