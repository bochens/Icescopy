import os
import sys
import unittest
from pathlib import Path

import numpy as np


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication  # noqa: E402

from icescopy_aux import Image_analysis_thread  # noqa: E402


class FakeFrameSource:
    def source_path(self):
        return ""

    def frame_key(self, frame_index):
        return f"frame-{frame_index}"


class RoiMeanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_worker(self):
        return Image_analysis_thread(
            filePath=None,
            imagePaths=[],
            imageNames=[],
            list_of_cell_items=[],
            frame_source=FakeFrameSource(),
        )

    def test_roi_mean_matches_boolean_mask_mean(self):
        worker = self.make_worker()
        image = np.arange(30, dtype=np.uint8).reshape(5, 6)
        center_x = 2.2
        center_y = 2.1
        radius = 1.8

        actual = worker.gray_scale_mean_from_array(
            0,
            image,
            [(center_x, center_y)],
            [radius],
        )[0]

        left = max(0, int(np.floor(center_x - radius)))
        right = min(image.shape[1], int(np.ceil(center_x + radius)) + 1)
        top = max(0, int(np.floor(center_y - radius)))
        bottom = min(image.shape[0], int(np.ceil(center_y + radius)) + 1)
        yy, xx = np.ogrid[: bottom - top, : right - left]
        mask = ((xx - (center_x - left)) ** 2 + (yy - (center_y - top)) ** 2) <= radius**2
        expected = float(np.sum(image[top:bottom, left:right][mask]) / np.count_nonzero(mask))

        self.assertAlmostEqual(actual, expected)

    def test_roi_descriptor_cache_reuses_geometry(self):
        worker = self.make_worker()
        image = np.arange(100, dtype=np.uint8).reshape(10, 10)

        first = worker.gray_scale_mean_from_array(0, image, [(5.0, 5.0)], [2.0])[0]
        self.assertEqual(len(worker._roi_descriptor_cache), 1)
        second = worker.gray_scale_mean_from_array(1, image, [(5.0, 5.0)], [2.0])[0]

        self.assertEqual(len(worker._roi_descriptor_cache), 1)
        self.assertEqual(first, second)

    def test_roi_mean_accepts_strided_luma_view(self):
        worker = self.make_worker()
        padded_image = np.arange(40, dtype=np.uint8).reshape(5, 8)
        image = padded_image[:, :6]
        self.assertFalse(image.flags.c_contiguous)

        actual = worker.gray_scale_mean_from_array(0, image, [(3.0, 2.0)], [1.5])[0]

        yy, xx = np.ogrid[:5, :6]
        mask = ((xx - 3.0) ** 2 + (yy - 2.0) ** 2) <= 1.5**2
        expected = float(np.sum(image[mask]) / np.count_nonzero(mask))
        self.assertAlmostEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
