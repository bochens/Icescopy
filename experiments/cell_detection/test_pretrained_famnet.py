"""Density-peak geometry contracts, not pretrained-model accuracy claims."""
import unittest

import numpy as np

from detector import Circle, same_object
from pretrained_famnet import density_circles


class FamNetPeakTests(unittest.TestCase):
    def test_examples_and_prior_cells_are_protected_with_correct_pixel_mapping(self):
        yy, xx = np.mgrid[:80, :160]
        points = [(20, 40), (60, 40), (105, 40)]
        density = sum(np.exp(-((xx-x)**2+(yy-y)**2)/(2*2.**2)) for x, y in points).astype(np.float32)
        example = Circle(40.5, 80.5, 12)
        old = Circle(120.5, 80.5, 12)
        predictions, meta = density_circles(density, [160, 320], [80, 160], [example], [old])
        self.assertEqual(len(predictions), 1)
        self.assertAlmostEqual(predictions[0]['circle']['x'], 210.5)
        self.assertAlmostEqual(predictions[0]['circle']['y'], 80.5)
        self.assertFalse(any(same_object(Circle(**p['circle']), c) for p in predictions for c in [example, old]))
        self.assertGreater(meta['reference_peak'], 0)
        self.assertFalse(meta['scores_are_probabilities'])

    def test_empty_and_padded_map_does_not_create_out_of_frame_centers(self):
        example = Circle(10, 10, 3)
        predictions, meta = density_circles(np.zeros((24, 24), np.float32), [17, 19], [17, 19], [example])
        self.assertEqual(predictions, []); self.assertIsNone(meta['cutoff'])
        density = np.zeros((24, 24), np.float32); density[10, 10] = 1; density[23, 23] = 100
        predictions, _ = density_circles(density, [17, 19], [17, 19], [example])
        self.assertFalse(any(p['circle']['x'] >= 19 or p['circle']['y'] >= 17 for p in predictions))
        with self.assertRaises(ValueError): density_circles(-density, [17, 19], [17, 19], [example])


if __name__ == '__main__': unittest.main()
