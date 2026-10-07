import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_freezfinder import (  # noqa: E402
    compute_convolution_timeseries,
    compute_freeze_event_indexes,
    compute_freeze_result_rows,
)


class FreezeFinderPaddingTests(unittest.TestCase):
    def test_long_windows_locate_the_actual_step_for_both_polarities(self):
        # Zero uses a pattern twice as long as the padded signal. Also cover
        # explicit windows on either side of the pattern/signal length boundary.
        for brightening in (False, True):
            for head, tail in ((0, 0), (20, 20), (20, 5)):
                for half_window, onset in ((0, 40), (1000, 40), (100, 60), (10, 40)):
                    with self.subTest(brightening=brightening, padding=(head, tail), half_window=half_window):
                        before, after = (50., 120.) if brightening else (120., 50.)
                        raw = np.r_[np.full(onset, before), np.full(120-onset, after)]
                        events = compute_freeze_event_indexes(
                            raw, width=5, prominence=60,
                            head_extend_points=head, tail_extend_points=tail,
                            convolution_half_window_points=half_window,
                            convolution_ramp_points=2,
                            detect_brightening=brightening,
                        )
                        self.assertEqual(events.tolist(), [onset])

    def test_full_window_keeps_source_frame_numbers_after_a_missing_gap(self):
        raw = np.r_[np.full(8, np.nan), np.full(40, 120.), np.full(80, 50.)]
        source_frames = list(range(300, 300 + len(raw)))
        names = [f'frame_{frame}' for frame in source_frames]
        rows, _ = compute_freeze_result_rows(
            names, None, raw[:, None], width=5, prominence=60,
            head_extend_points=20, tail_extend_points=5,
            convolution_half_window_points=0, convolution_ramp_points=2,
            frame_indexes=source_frames,
        )
        self.assertEqual(rows, [['cell_0', '348', 'frame_348']])

    def test_full_window_does_not_add_events_to_constant_or_single_frame_data(self):
        for length in (1, 120):
            for brightening in (False, True):
                with self.subTest(length=length, brightening=brightening):
                    events = compute_freeze_event_indexes(
                        np.full(length, 70.), convolution_half_window_points=0,
                        detect_brightening=brightening,
                    )
                    self.assertEqual(events.tolist(), [])

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
            convolution_half_window_points=2, convolution_ramp_points=0,
        )
        front_padding_rows, front_padding_peaks = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=2,
            tail_extend_points=0,
            convolution_half_window_points=2, convolution_ramp_points=0,
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
            convolution_half_window_points=2, convolution_ramp_points=0,
            frame_indexes=[20, 21, 22, 23, 24, 25],
        )

        self.assertEqual(rows, [["cell_0", "21", "frame_1"]])

    def test_missing_cell_value_does_not_poison_later_freeze_detection(self):
        raw = np.asarray([np.nan, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0]).reshape(-1, 1)
        frame_names = [f"frame_{index}" for index in range(raw.shape[0])]

        rows, peaks = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=2,
            tail_extend_points=0,
            convolution_half_window_points=2, convolution_ramp_points=0,
            frame_indexes=[30, 31, 32, 33, 34, 35, 36],
        )

        self.assertEqual(rows, [["cell_0", "32", "frame_2"]])
        self.assertEqual(peaks[0].tolist(), [2])

    def test_missing_gap_does_not_create_a_synthetic_freeze(self):
        raw = np.asarray([100.0, 100.0, np.nan, 0.0, 0.0]).reshape(-1, 1)
        frame_names = [f"frame_{index}" for index in range(raw.shape[0])]

        rows, peaks = compute_freeze_result_rows(
            frame_names,
            np.array([""] * len(frame_names), dtype=object),
            raw,
            width=0.1,
            prominence=1.0,
            head_extend_points=2,
            tail_extend_points=2,
            convolution_half_window_points=2, convolution_ramp_points=0,
        )

        self.assertEqual(rows, [])
        self.assertEqual(peaks[0].tolist(), [])


if __name__ == "__main__":
    unittest.main()
