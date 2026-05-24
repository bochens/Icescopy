import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication  # noqa: E402
from icescopy_freezfinder import compute_convolution_center_offset  # noqa: E402
from icescopy_plot import GrayscalePlotWidget  # noqa: E402


class GrayscalePlotWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_widget(self):
        widget = GrayscalePlotWidget()
        self.addCleanup(widget.close)
        return widget

    def sample_plot_data(self):
        headers = [
            "file_name",
            "flag_state",
            "cell_1_grayscale",
            "cell_2_grayscale",
        ]
        rows = [
            [f"image_{index}.png", "", str(100 + index), str(200 + index * 2)]
            for index in range(10)
        ]
        return headers, rows

    def test_current_frame_marker_uses_matching_file_name_row(self):
        headers, rows = self.sample_plot_data()
        reordered_rows = [rows[5], rows[6], rows[7]]
        widget = self.make_widget()

        widget.update_plot_data(
            headers,
            reordered_rows,
            [],
            [1],
            current_image_index=5,
            current_image_name="image_5.png",
        )

        self.assertIsNotNone(widget.current_frame_line)
        self.assertAlmostEqual(float(widget.current_frame_line.value()), 0.0)

    def test_fast_path_updates_current_frame_marker_position(self):
        headers, rows = self.sample_plot_data()
        widget = self.make_widget()

        widget.update_plot_data(headers, rows, [], [1], current_image_index=2)
        self.assertIsNotNone(widget.current_frame_line)
        self.assertAlmostEqual(float(widget.current_frame_line.value()), 2.0)

        widget.update_plot_data(headers, rows, [], [1], current_image_index=7)

        self.assertIsNotNone(widget.current_frame_line)
        self.assertAlmostEqual(float(widget.current_frame_line.value()), 7.0)

    def test_index_only_current_frame_marker_does_not_build_file_name_map(self):
        headers, rows = self.sample_plot_data()
        widget = self.make_widget()

        widget.update_plot_data(headers, rows, [], [1], current_image_index=2)
        widget.set_current_image_index(7, current_image_name=None)

        self.assertIsNone(widget._row_indexes_by_file_name_cache)
        self.assertIsNotNone(widget.current_frame_line)
        self.assertAlmostEqual(float(widget.current_frame_line.value()), 7.0)

    def test_subpixel_current_frame_marker_update_is_skipped_until_forced(self):
        headers, rows = self.sample_plot_data()
        widget = self.make_widget()
        widget.update_plot_data(headers, rows, [], [1], current_image_index=2)
        self.assertIsNotNone(widget.current_frame_line)

        widget._last_current_frame_widget_x = 100.0
        widget._current_frame_widget_x = lambda frame_x: 100.4
        widget.set_current_image_index(7, current_image_name=None)

        self.assertAlmostEqual(float(widget.current_frame_line.value()), 2.0)

        widget.set_current_image_index(7, current_image_name=None, force=True)
        self.assertAlmostEqual(float(widget.current_frame_line.value()), 7.0)

    def test_peak_downsample_preserves_bucket_extrema(self):
        widget = self.make_widget()
        x_values = list(range(100))
        y_values = [0.0] * 100
        y_values[10] = -5.0
        y_values[11] = 7.0
        y_values[60] = -3.0
        y_values[61] = 9.0

        _sampled_x, sampled_y = widget._peak_downsample_arrays(
            x_values,
            y_values,
            max_points=10,
        )

        self.assertIn(-5.0, sampled_y)
        self.assertIn(7.0, sampled_y)
        self.assertIn(-3.0, sampled_y)
        self.assertIn(9.0, sampled_y)

    def test_cell_switch_autoscales_visible_plot_ranges(self):
        headers, rows = self.sample_plot_data()
        widget = self.make_widget()

        widget.update_plot_data(headers, rows, [], [1], current_image_index=4)
        widget.plot_item.setRange(xRange=(2.0, 5.0), yRange=(95.0, 112.0), padding=0)

        widget.update_plot_data(headers, rows, [], [2], current_image_index=4)

        _x_range, y_range = widget.plot_item.vb.viewRange()
        self.assertGreater(y_range[0], 150.0)
        self.assertGreater(y_range[1], 210.0)

    def test_front_padding_shifts_convolution_display_back_to_real_frame_index(self):
        widget = self.make_widget()
        y_values = [100.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        widget.head_extend_points = 2
        widget.tail_extend_points = 3
        widget.convolution_half_window_points = 2
        widget.convolution_ramp_points = 0

        x_values, convolved_values = widget._convolution_for_cell(1, y_values)

        expected_offset = compute_convolution_center_offset(
            len(y_values) + widget.head_extend_points + widget.tail_extend_points,
            convolution_half_window_points=widget.convolution_half_window_points,
            convolution_ramp_points=widget.convolution_ramp_points,
        ) - widget.head_extend_points
        self.assertEqual(len(x_values), len(convolved_values))
        self.assertAlmostEqual(float(x_values[0]), expected_offset)


if __name__ == "__main__":
    unittest.main()
