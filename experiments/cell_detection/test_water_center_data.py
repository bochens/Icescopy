"""Invalid-center labels and transforms, not detector accuracy measurements."""
import copy
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from hybrid_data import augment_training, sha256
from water_center_data import CenterTriplets, build_center_crops, check_center_manifest
from test_water_data import manual_scene


def center_scene():
    scene = manual_scene(); scene['targets'][0]['radius'] = 10; scene['sha256'] = 'fixture-pixels'
    scene.update(center_negative_review_complete=True, center_negatives=[
        {'id': 0, 'x': 38., 'y': 32., 'radius': 10., 'kind': 'miscentered',
         'provenance': {'type': 'reviewed_shifted_center'}}])
    return scene


class CenterDataTests(unittest.TestCase):
    def test_context_can_overlap_water_without_empty_water_label(self):
        scene = center_scene(); original = copy.deepcopy(scene); original.pop('center_negatives')
        checked = check_center_manifest({'scenes': [scene]}, {'scenes': [original]})
        self.assertEqual(len(checked), 1)
        self.assertLess(abs(scene['center_negatives'][0]['x']-scene['targets'][0]['x']), 10)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); image = np.zeros((96, 128, 3), np.uint8)
            cv2.circle(image, (32, 32), 10, (255, 255, 255), -1)
            cv2.circle(image, (72, 32), 6, (255, 255, 255), -1)
            path = folder/'source.png'; cv2.imwrite(str(path), image)
            scene.update(source=str(path), sha256=sha256(path))
            rows = build_center_crops([scene], folder)
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r['label'] == 0 and r['label_source'] == 'explicit_reviewed_invalid_center' for r in rows))
            self.assertTrue(all(r['circle'] == r['source_circle'] for r in rows))
            # The water can cover the central pixel while the selection center
            # is wrong. This explicitly checks that negative does not mean dry.
            crops = np.load(folder/'crops.npy')
            self.assertTrue(np.all(crops[:, 47:49, 47:49].mean(axis=(1, 2, 3)) > 140))

    def test_review_geometry_and_center_separation_are_required(self):
        scene = center_scene(); original = copy.deepcopy(scene); original.pop('center_negatives')
        bad = copy.deepcopy(scene); bad['center_negatives'][0]['x'] = 35
        with self.assertRaisesRegex(ValueError, 'too close'):
            check_center_manifest({'scenes': [bad]}, {'scenes': [original]})
        bad = copy.deepcopy(scene); bad['targets'][0]['radius'] = 11
        with self.assertRaisesRegex(ValueError, 'Original labels'):
            check_center_manifest({'scenes': [bad]}, {'scenes': [original]})
        bad = copy.deepcopy(scene); bad['center_negative_review_complete'] = False
        with self.assertRaisesRegex(ValueError, 'completed review'):
            check_center_manifest({'scenes': [bad]}, {'scenes': [original]})

    def test_no_translation_transform_preserves_off_center_marker(self):
        patch = np.zeros((96, 96, 3), np.float32)
        cv2.circle(patch, (66, 48), 3, (1, 1, 1), -1)
        rng = np.random.default_rng(61004)
        for _ in range(40):
            transformed = augment_training(patch, rng, translate=False)
            ys, xs = np.where(transformed.mean(axis=2) > 120)
            self.assertGreater(np.hypot(xs.mean()-47.5, ys.mean()-47.5), 15.)

    def test_actual_update_coverage_and_equal_old_new_sampling(self):
        records = []
        scene_counts = [(50, 55), (160, 225), (90, 212), (16, 20), (105, 157)]
        for group, (positive, centers) in enumerate(scene_counts):
            for label, kind, count in [(1, 'targets', positive), (0, 'negatives', 3), (0, 'center_negatives', centers)]:
                for identity in range(count):
                    records.append({'index': len(records), 'domain': 'real', 'group': str(group), 'scene_id': str(group),
                                    'split': 'fit', 'label': label, 'object_id': kind+':'+str(identity),
                                    'label_source': 'explicit_reviewed_invalid_center' if kind == 'center_negatives'
                                    else 'user_positive' if label else 'explicit_reviewed_negative'})
        for label, count in [(1, 10), (0, 3)]:
            for identity in range(count):
                records.append({'index': len(records), 'domain': 'synthetic', 'group': 'replay', 'scene_id': 'replay',
                                'split': 'fit', 'label': label, 'object_id': str(label)+':'+str(identity)})
        sampler = CenterTriplets(records, 'fit'); rng = np.random.default_rng(61004)
        kinds = {'old': 0, 'new': 0}
        for epoch in range(4):
            for _ in range(40):
                samples = sampler.sample(rng, 32)
                for a, p, n in samples:
                    self.assertNotEqual(records[a]['object_id'], records[p]['object_id'])
                    self.assertEqual(records[a]['scene_id'], records[n]['scene_id'])
                    if records[n]['domain'] == 'real':
                        kinds['new' if records[n]['label_source'] == 'explicit_reviewed_invalid_center' else 'old'] += 1
                if epoch == 0 and not sampler.updated:
                    self.assertFalse(sampler.all_manual_updated())
                sampler.mark_updated(samples)
            self.assertEqual(sampler.all_manual_updated(), epoch == 3)
        self.assertEqual(kinds['old'], kinds['new'])
        self.assertEqual(sum(c['updated_centers'] for c in sampler.negative_coverage().values()), 669)
        self.assertEqual(sum(c['updated_objects'] for c in sampler.object_coverage()['real'].values()), 421)


if __name__ == '__main__':
    unittest.main()
