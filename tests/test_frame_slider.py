import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_frameslider import timeline_zoom_factor_from_slider_value  # noqa: E402


class FrameSliderTests(unittest.TestCase):
    def test_timeline_zoom_factor_keeps_endpoints(self):
        self.assertEqual(timeline_zoom_factor_from_slider_value(1, 1600), 1.0)
        self.assertEqual(timeline_zoom_factor_from_slider_value(1600, 1600), 1600.0)
        self.assertEqual(timeline_zoom_factor_from_slider_value(2, 2), 2.0)

    def test_timeline_zoom_factor_is_log_scaled_for_large_ranges(self):
        maximum_zoom = 1600
        first_step_zoom = timeline_zoom_factor_from_slider_value(2, maximum_zoom)
        midpoint_zoom = timeline_zoom_factor_from_slider_value(800, maximum_zoom)

        self.assertLess(first_step_zoom, 1.01)
        self.assertGreater(midpoint_zoom, 30.0)
        self.assertLess(midpoint_zoom, 50.0)


if __name__ == "__main__":
    unittest.main()
