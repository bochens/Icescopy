"""Guard reserved pixels, exact translated labels and training-only updates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from hybrid_data import sha256
from joint_data import TileSchedule, active_scenes
from joint_spatial import FORMAT, check_spatial_manifest


class SpatialSplitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.parent_model = {'path': '/synthetic-only.pt', 'sha256': 'synthetic-parent'}
        old = folder/'old.json'; old.write_text(json.dumps({'starting_encoder': self.parent_model}))
        source = {'id': 'plate', 'width': 100, 'height': 300, 'source': '/original.png', 'sha256': 'original',
                  'targets': [dict(id=i, x=25.+25*(i % 2), y=50.+100*(i//2), radius=5.) for i in range(6)],
                  'negatives': [], 'center_negatives': []}
        parent = folder/'parent.json'
        parent.write_text(json.dumps({'previous_manual_manifest': {'path': str(old), 'sha256': sha256(old)}, 'scenes': [source]}))
        self.manifest = {'format_version': FORMAT, 'parent_manual_manifest': {'path': str(parent), 'sha256': sha256(parent)},
                         'starting_encoder': self.parent_model, 'scenes': []}
        for n, split in enumerate(('fit', 'validation', 'test')):
            pixels = folder/(split+'.png'); pixels.write_bytes(split.encode())
            self.manifest['scenes'].append(dict(id=split, group=split, split=split, original_scene_id='plate',
                original_source=source['source'], original_sha256=source['sha256'], source=str(pixels), sha256=sha256(pixels),
                source_bbox=[0, n*100, 100, (n+1)*100], width=100, height=100,
                targets=[dict(c, y=c['y']-n*100) for c in source['targets'][2*n:2*n+2]], negatives=[], center_negatives=[]))
        # The older whole-image contract has its own tests. Exercise the new
        # split contract with small fixtures instead of private training files.
        guard = patch('joint_spatial.check_center_manifest', return_value=[source]); guard.start(); self.addCleanup(guard.stop)

    def test_exact_translation_and_reserved_test_exclusion(self):
        self.assertEqual(len(check_spatial_manifest(self.manifest)), 3)
        root = Path(self.temp.name); real = root/'split.json'; real.write_text(json.dumps(self.manifest))
        synthetic = root/'synthetic.json'; synthetic.write_text('{}')
        with patch('joint_data.check_manifest', return_value=[]):
            _, scenes = active_scenes(real, synthetic)
        self.assertEqual({row['split'] for row in scenes}, {'fit', 'validation'})

    def test_changed_label_and_real_trained_parent_are_rejected(self):
        changed = copy.deepcopy(self.manifest); changed['scenes'][0]['targets'][0]['x'] += 1
        with self.assertRaisesRegex(ValueError, 'exact contained'):
            check_spatial_manifest(changed)
        changed = copy.deepcopy(self.manifest); changed['starting_encoder']['sha256'] = 'real-trained'
        with self.assertRaisesRegex(ValueError, 'synthetic-only'):
            check_spatial_manifest(changed)

    def test_overlapping_pixels_rejected_even_without_shared_circles(self):
        changed = copy.deepcopy(self.manifest)
        changed['scenes'][0]['source_bbox'][3] = 110; changed['scenes'][0]['height'] = 110
        with self.assertRaisesRegex(ValueError, 'pixels overlap'):
            check_spatial_manifest(changed)

    def test_validation_cannot_enter_optimizer_or_coverage_requirement(self):
        scenes = [dict(row, domain='real') for row in self.manifest['scenes'][:2]]
        records = [dict(index=i, scene_id=s['id'], group=s['group'], split=s['split'], domain='real',
                        positive_ids=[r['id'] for r in s['targets']], invalid_center_ids=[], old_negative_ids=[])
                   for i, s in enumerate(scenes)]
        records.append(dict(index=2, scene_id='synthetic', group='synthetic', split='fit', domain='synthetic',
                            positive_ids=[0], invalid_center_ids=[], old_negative_ids=[]))
        schedule = TileSchedule(records, scenes)
        indices = schedule.sample(np.random.default_rng(1))
        self.assertNotIn(1, indices)
        schedule.mark_updated(indices)
        self.assertTrue(schedule.all_positives_updated())
        self.assertEqual(set(schedule.coverage()), {'fit'})


if __name__ == '__main__': unittest.main()
