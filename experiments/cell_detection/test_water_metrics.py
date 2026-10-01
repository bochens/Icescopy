"""Small contract checks, not estimates of detector accuracy."""
import unittest

import numpy as np

from detector import Circle
from water_compare import fit_matched_head
from water_metrics import calibrate_f2, f2_key, fixed_trials, native_diagnostic


class WaterMetricTests(unittest.TestCase):
    def test_native_reference_radii_and_unknown_selections(self):
        truth = [Circle(0, 0, 2), Circle(30, 0, 10), Circle(60, 0, 3)]
        circles = [Circle(0, 0, 2), Circle(37, 0, 2), Circle(80, 0, 2), Circle(100, 0, 2)]
        distance = np.linalg.norm(np.asarray([[c.x, c.y] for c in circles])[:, None]-
                                  np.asarray([[c.x, c.y] for c in truth])[None], axis=2)
        item = {'truth': truth, 'circles': circles, 'distance': distance,
                'scene': {'complete_labels': False, 'negatives': [{'x': 80, 'y': 0, 'radius': 3}]}}
        result = native_diagnostic(item, np.asarray([1., .9, .8, .7]), [0], .5)
        self.assertEqual(result['found'], 1)
        self.assertEqual(result['missed_ids'], [2])
        self.assertEqual(result['known_negative_indices'], [2])
        self.assertEqual(result['unclassified_indices'], [3])
        self.assertEqual(result['accepted'], [1, 2, 3])
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['false_detections'])
        self.assertEqual(result['duplicate_existing'], 0)

    def test_predeclared_trials_and_f2_cost(self):
        self.assertEqual(fixed_trials(5), [[0], [2], [4], [0, 2], [2, 4]])
        # Missing one object and accepting four extras have the same F2 penalty.
        self.assertAlmostEqual(f2_key(9, 0, 10, .5)[0], f2_key(9, 4, 9, .5)[0])

    def test_calibration_rejects_manual_training(self):
        with self.assertRaisesRegex(ValueError, 'separate'):
            calibrate_f2([{'scene': {'split': 'fit', 'recording': 'manual', 'complete_labels': False}}], 0, {})

    def test_exact_f2_sweep_keeps_targets_and_rejects_lower_score_extra(self):
        truth = [Circle(x, 0, 3) for x in (0, 40, 80)]
        circles = truth+[Circle(120, 0, 3)]
        candidate = np.asarray([[1., 0.]]*3+[[-1., 0.]])
        example = np.asarray([[1., 0.]]*3)
        def bank(vectors):
            return {'gray': vectors, 'edges': vectors, 'embedding': vectors,
                    'profiles': np.zeros((len(vectors), 4))}
        item = {'truth': truth, 'circles': circles,
                'distance': np.abs(np.asarray([c.x for c in circles])[:, None]-np.asarray([c.x for c in truth])[None]),
                'banks': (bank(candidate),), 'examples': (bank(example),),
                'scene': {'id': 'calibration', 'group': 'reserved', 'split': 'calibration',
                          'recording': 'neural-synthetic-contract', 'complete_labels': True,
                          'rendering': {'family': 'contract'}}}
        head = {'mean': [0]*5, 'scale': [1]*5, 'weights': [0, 0, 0, 0, 10], 'bias': 0}
        result = calibrate_f2([item], 0, head)
        self.assertEqual(result['f2'], 1.)
        self.assertEqual(result['found'], result['remaining'])
        self.assertEqual(result['false_detections'], 0)
        self.assertGreater(result['threshold'], .99)
        self.assertGreater(result['search']['verified_trials'], 0)

    def test_equal_group_weights_ignore_repeated_identical_variants(self):
        def fixture(repeats):
            records = []; vectors = []
            for domain, count in [('real', repeats), ('synthetic', 1)]:
                for variant in range(count):
                    for label, object_id, vector in [(1, 'a', [1., 0.]), (1, 'b', [.8, .6]), (0, 'c', [0., 1.])]:
                        records.append({'index': len(records), 'split': 'fit', 'domain': domain, 'group': domain,
                                        'label': label, 'object_id': object_id, 'label_source':
                                        'user_positive' if label else 'explicit_reviewed_negative'})
                        vectors.append(vector)
            values = np.asarray(vectors)
            return records, {'gray': values, 'edges': values, 'embedding': values,
                             'profiles': np.column_stack([values, values])}
        one = fit_matched_head(*fixture(1), 'test')
        many = fit_matched_head(*fixture(5), 'test')
        np.testing.assert_allclose(one['weights'], many['weights'], atol=1e-9)
        np.testing.assert_allclose(one['mean'], many['mean'], atol=1e-12)
        np.testing.assert_allclose(one['bias'], many['bias'], atol=1e-9)


if __name__ == '__main__':
    unittest.main()
