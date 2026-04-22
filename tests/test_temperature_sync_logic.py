import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_temperature_import import (  # noqa: E402
    build_cycle_ids_from_start_indexes,
    detect_cycle_start_indexes_from_temperatures,
    reconcile_counts_by_cycle,
    reconcile_cumulative_counts,
)


class TemperatureSyncLogicTests(unittest.TestCase):
    def test_reconcile_without_anchors_repairs_monotonicity_and_clamps(self):
        corrected = reconcile_cumulative_counts(
            [0, 1, 1, 0, 3, 6],
            {},
            4,
        )
        self.assertEqual(corrected, [0, 1, 1, 1, 3, 4])

    def test_reconcile_preserves_in_range_values_between_anchors(self):
        corrected = reconcile_cumulative_counts(
            [0, 0, 2, 2, 6, 8],
            {1: 1, 4: 4},
            10,
        )
        self.assertEqual(corrected, [0, 1, 2, 2, 4, 8])

    def test_reconcile_clips_early_overshoot_to_next_anchor(self):
        corrected = reconcile_cumulative_counts(
            [0, 0, 5, 2, 6, 8],
            {1: 1, 4: 4},
            10,
        )
        self.assertEqual(corrected, [0, 1, 4, 4, 4, 8])

    def test_reconcile_upgrades_non_monotone_anchors(self):
        corrected = reconcile_cumulative_counts(
            [0, 2, 1, 0],
            {1: 2, 3: 1},
            3,
        )
        self.assertEqual(corrected, [0, 2, 2, 2])

    def test_cycle_detection_ignores_small_threshold_jitter(self):
        cycle_starts = detect_cycle_start_indexes_from_temperatures(
            [5.05, 5.01, 4.999, 5.002, 4.99],
            5.0,
            warmup_hysteresis_c=0.02,
        )
        self.assertEqual(cycle_starts, [0])

    def test_cycle_detection_detects_real_warmups(self):
        cycle_starts = detect_cycle_start_indexes_from_temperatures(
            [5.05, 4.90, 4.95, 5.10, 4.80, 5.12],
            5.0,
            warmup_hysteresis_c=0.02,
        )
        self.assertEqual(cycle_starts, [0, 3, 5])

    def test_build_cycle_ids_from_start_indexes(self):
        cycle_ids = build_cycle_ids_from_start_indexes(7, [0, 3, 5])
        self.assertEqual(cycle_ids, [0, 0, 0, 1, 1, 2, 2])

    def test_reconcile_counts_by_cycle_resets_each_segment(self):
        corrected = reconcile_counts_by_cycle(
            [0, 0, 2, 0, 0, 2],
            {1: 1, 4: 1},
            2,
            [0, 0, 0, 1, 1, 1],
        )
        self.assertEqual(corrected, [0, 1, 2, 0, 1, 2])


if __name__ == "__main__":
    unittest.main()
