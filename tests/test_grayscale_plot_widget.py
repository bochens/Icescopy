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

    def test_cell_switch_autoscales_visible_plot_ranges(self):
        headers, rows = self.sample_plot_data()
        widget = self.make_widget()

        widget.update_plot_data(headers, rows, [], [1], current_image_index=4)
        widget.plot_item.setRange(xRange=(2.0, 5.0), yRange=(95.0, 112.0), padding=0)

        widget.update_plot_data(headers, rows, [], [2], current_image_index=4)

        _x_range, y_range = widget.plot_item.vb.viewRange()
        self.assertGreater(y_range[0], 150.0)
        self.assertGreater(y_range[1], 210.0)


if __name__ == "__main__":
    unittest.main()
