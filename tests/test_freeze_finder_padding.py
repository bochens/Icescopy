import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_freezfinder import compute_convolution_timeseries, compute_freeze_result_rows  # noqa: E402


class FreezeFinderPaddingTests(unittest.TestCase):
    def test_front_padding_repeats_first_value_before_convolution(self):
        raw = np.asarray([10.0, 20.0, 30.0])
        centered, _convolved = compute_convolution_timeseries(
            raw,
            head_extend_points=2,
            tail_extend_points=3,
        )

        expected_padded = np.asarray([10.0, 10.0, 10.0, 20.0, 30.0, 30.0, 30.0, 30.0])
        self.assertTrue(np.allclose(centered + expected_padded.mean(), expected_padded))

    def test_front_padding_detects_early_freeze_without_padded_index_output(self):
        raw = np.asarray([100.0, 0.0, 0.0, 0.0, 0.0, 0.0]).reshape(-1, 1)
        frame_names = [f"frame_{index}" for index in range(raw.shape[0])]

        no_padding_rows, _ = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=0,
            tail_extend_points=0,
            convolution_half_window_points=2,
        )
        front_padding_rows, front_padding_peaks = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=2,
            tail_extend_points=0,
            convolution_half_window_points=2,
        )

        self.assertEqual(no_padding_rows, [])
        self.assertEqual(front_padding_rows, [["cell_0", "1", "frame_1"]])
        self.assertTrue(np.all(front_padding_peaks[0] >= 0))

    def test_freeze_rows_map_limited_window_rows_to_source_frame_indexes(self):
        raw = np.asarray([100.0, 0.0, 0.0, 0.0, 0.0, 0.0]).reshape(-1, 1)
        frame_names = [f"frame_{index}" for index in range(raw.shape[0])]

        rows, _ = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=2,
            tail_extend_points=0,
            convolution_half_window_points=2,
            frame_indexes=[20, 21, 22, 23, 24, 25],
        )

        self.assertEqual(rows, [["cell_0", "21", "frame_1"]])


if __name__ == "__main__":
    unittest.main()
