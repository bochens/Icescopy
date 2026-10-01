"""Protect placement reporting against the broad-match error in the old preview."""
import unittest

from detector import Circle
from joint_metrics import match_centers, measure_scene


class JointMetricTests(unittest.TestCase):
    def test_offset_circle_is_recovered_but_not_centered(self):
        scene = {'targets': [{'x': 30., 'y': 30., 'radius': 10.}],
                 'center_negatives': [{'x': 39.2, 'y': 30., 'radius': 10.}]}
        result = measure_scene(scene, [Circle(39.2, 30., 10.)], [])
        self.assertEqual((result['found'], result['centered'], result['extras']), (1, 0, 0))
        self.assertEqual(result['offset_indices'], [0])
        self.assertEqual(result['invalid_center_indices'], [0])
        self.assertIsNone(result['precision'])

    def test_assignment_preserves_two_matches(self):
        # Taking the closest pair first would lose one of these two valid matches.
        found = match_centers([Circle(3., 0., 1.), Circle(-4., 0., 1.)],
                              [Circle(0., 0., 10.), Circle(10., 0., 10.)], 1.)
        self.assertEqual(len(found), 2)
        self.assertEqual({(r['prediction'], r['reference']) for r in found}, {(0, 1), (1, 0)})

    def test_each_reference_uses_its_own_radius_and_seeds_are_excluded(self):
        scene = {'targets': [{'x': 0., 'y': 0., 'radius': 1.},
                             {'x': 100., 'y': 0., 'radius': 20.},
                             {'x': 200., 'y': 0., 'radius': 2.}], 'complete_labels': True}
        result = measure_scene(scene, [Circle(105., 0., 20.), Circle(205., 0., 2.)], [0])
        self.assertEqual((result['remaining'], result['found'], result['centered']), (2, 1, 1))
        self.assertEqual(result['extra_indices'], [1])
        self.assertEqual(result['precision'], .5)


if __name__ == '__main__':
    unittest.main()
