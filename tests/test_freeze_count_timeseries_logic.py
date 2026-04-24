import sys
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_temperature_import import (  # noqa: E402
    IMAGE_TIMESTAMP_SOURCE_GENERATED,
    TEMPERATURE_UNIT_KELVIN,
    TIMESTAMP_STYLE_YEAR2_COMPACT,
    TIMESTAMP_STYLE_YEAR2_SLASH,
    TIMESTAMP_STYLE_YEAR4_COMPACT,
    TIMESTAMP_STYLE_YEAR4_DASH,
    TIMESTAMP_STYLE_YEAR4_T,
    TIMESTAMP_STYLE_EPOCH_SECONDS,
    TIMESTAMP_STYLE_EPOCH_MILLISECONDS,
    TIMESTAMP_STYLE_EXIF,
    apply_blank_correction,
    build_cycle_ids_from_start_indexes,
    compute_blank_correction_by_index,
    detect_cycle_start_indexes_from_temperatures,
    parse_flexible_datetime_text,
    parse_generic_image_timestamp,
    parse_timestamp_text,
    parse_standard_temperature_csv,
    resolve_image_timestamps,
    TemperatureImportError,
    reconcile_counts_by_cycle,
    reconcile_cumulative_counts,
)


class FreezeCountTimeseriesLogicTests(unittest.TestCase):
    def expected_epoch_utc_naive(self, seconds_value):
        return datetime.fromtimestamp(seconds_value, tz=timezone.utc).replace(tzinfo=None)

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

    def test_parse_flexible_datetime_text_accepts_common_unambiguous_formats(self):
        self.assertEqual(
            parse_flexible_datetime_text("2026-04-22 23:15:01"),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_flexible_datetime_text("2026/04/22 23:15"),
            datetime(2026, 4, 22, 23, 15, 0),
        )
        self.assertEqual(
            parse_flexible_datetime_text("22/04/2026 23:15:01"),
            datetime(2026, 4, 22, 23, 15, 1),
        )

    def test_parse_flexible_datetime_text_rejects_ambiguous_slash_dates(self):
        self.assertIsNone(parse_flexible_datetime_text("04/05/2026 12:30:00"))

    def test_parse_flexible_datetime_text_rejects_timezone_qualified_values(self):
        self.assertIsNone(parse_flexible_datetime_text("2026-04-22T23:15:01Z"))

    def test_parse_timestamp_text_accepts_exif_and_epoch_styles(self):
        self.assertEqual(
            parse_timestamp_text("2026:04:22 23:15:01", TIMESTAMP_STYLE_EXIF),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertIsNone(parse_timestamp_text("1713827701"))
        self.assertEqual(
            parse_timestamp_text("1713827701", TIMESTAMP_STYLE_EPOCH_SECONDS),
            self.expected_epoch_utc_naive(1713827701.0),
        )
        self.assertEqual(
            parse_timestamp_text("1713827701000", TIMESTAMP_STYLE_EPOCH_MILLISECONDS),
            self.expected_epoch_utc_naive(1713827701.0),
        )
        self.assertIsNone(parse_timestamp_text("17138277010", TIMESTAMP_STYLE_EPOCH_SECONDS))
        self.assertIsNone(parse_timestamp_text("17138277010", TIMESTAMP_STYLE_EPOCH_MILLISECONDS))

    def test_parse_timestamp_text_accepts_explicit_text_styles(self):
        self.assertEqual(
            parse_timestamp_text("2026-04-22 23:15:01", TIMESTAMP_STYLE_YEAR4_DASH),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("2026-04-22T23:15:01", TIMESTAMP_STYLE_YEAR4_T),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("20260422_231501", TIMESTAMP_STYLE_YEAR4_COMPACT),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("20260422 231501", TIMESTAMP_STYLE_YEAR4_COMPACT),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("260422_231501", TIMESTAMP_STYLE_YEAR2_COMPACT),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("260422 231501", TIMESTAMP_STYLE_YEAR2_COMPACT),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("260422 2315", TIMESTAMP_STYLE_YEAR2_COMPACT),
            datetime(2026, 4, 22, 23, 15, 0),
        )
        self.assertEqual(
            parse_timestamp_text("260422-231501", TIMESTAMP_STYLE_YEAR2_COMPACT),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_timestamp_text("26/04/22 23:15:01", TIMESTAMP_STYLE_YEAR2_SLASH),
            datetime(2026, 4, 22, 23, 15, 1),
        )

    def test_parse_standard_temperature_csv_skips_header_and_sorts_rows(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "temperature.csv"
            file_path.write_text(
                "datetime,temperature_C,ignored\n"
                "2026-04-22 12:05:00,-12.4,abc\n"
                "2026-04-22 12:00:00,-11.8,xyz\n",
                encoding="utf-8",
            )
            parsed = parse_standard_temperature_csv(file_path)

        self.assertEqual(parsed.timeseries_row_count, 2)
        self.assertEqual(
            parsed.timeseries_datetimes,
            [
                datetime(2026, 4, 22, 12, 0, 0),
                datetime(2026, 4, 22, 12, 5, 0),
            ],
        )
        self.assertEqual(parsed.temperature_values, [-11.8, -12.4])

    def test_parse_standard_temperature_csv_rejects_duplicate_timestamps(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "temperature.csv"
            file_path.write_text(
                "datetime,temperature_C\n"
                "2026-04-22 12:00:00,-11.8\n"
                "2026-04-22 12:00:00,-12.4\n",
                encoding="utf-8",
            )
            with self.assertRaises(TemperatureImportError):
                parse_standard_temperature_csv(file_path)

    def test_parse_standard_temperature_csv_converts_kelvin_to_celsius(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "temperature.csv"
            file_path.write_text(
                "timestamp,temperature_K\n"
                "1713827701000,260.15\n"
                "1713827761000,261.15\n",
                encoding="utf-8",
            )
            parsed = parse_standard_temperature_csv(
                file_path,
                timestamp_style=TIMESTAMP_STYLE_EPOCH_MILLISECONDS,
                temperature_unit=TEMPERATURE_UNIT_KELVIN,
            )

        self.assertEqual(parsed.temperature_values, [-13.0, -12.0])

    def test_parse_generic_image_timestamp_accepts_common_filename_patterns(self):
        self.assertEqual(
            parse_generic_image_timestamp("2026-04-22-23-15-01-123456.png"),
            datetime(2026, 4, 22, 23, 15, 1, 123456),
        )
        self.assertEqual(
            parse_generic_image_timestamp("capture_20260422_231501.png"),
            datetime(2026, 4, 22, 23, 15, 1),
        )
        self.assertEqual(
            parse_generic_image_timestamp("frame_2026_04_22_23_15_01.png"),
            datetime(2026, 4, 22, 23, 15, 1),
        )

    def test_parse_generic_image_timestamp_rejects_short_numeric_filenames(self):
        self.assertIsNone(parse_generic_image_timestamp("0.png"))
        self.assertIsNone(parse_generic_image_timestamp("1.png"))
        self.assertIsNone(parse_generic_image_timestamp("1234.png"))

    def test_parse_generic_image_timestamp_accepts_epoch_filename_when_explicit(self):
        self.assertEqual(
            parse_generic_image_timestamp(
                "1713827701.png",
                TIMESTAMP_STYLE_EPOCH_SECONDS,
            ),
            self.expected_epoch_utc_naive(1713827701.0),
        )

    def test_resolve_image_timestamps_generated_source_uses_first_timestamp_and_interval(self):
        resolved = resolve_image_timestamps(
            ["/tmp/a.png", "/tmp/b.png", "/tmp/c.png"],
            ["a.png", "b.png", "c.png"],
            source=IMAGE_TIMESTAMP_SOURCE_GENERATED,
            timestamp_style=TIMESTAMP_STYLE_EXIF,
            generated_start_text="2026:04:22 23:15:01",
            frame_interval_seconds=2.5,
        )

        self.assertEqual(
            resolved.image_timestamps,
            [
                datetime(2026, 4, 22, 23, 15, 1),
                datetime(2026, 4, 22, 23, 15, 3, 500000),
                datetime(2026, 4, 22, 23, 15, 6),
            ],
        )
        self.assertEqual(resolved.parsed_count, 3)

    def test_blank_correction_helpers_adjust_totals_and_frozen_counts(self):
        correction = compute_blank_correction_by_index(
            ["blank_a"],
            {"blank_a": [0, 1, 2], "sample_a": [0, 2, 3]},
            3,
        )
        self.assertEqual(correction, [0, 1, 2])
        self.assertEqual(apply_blank_correction(4, 3, correction[2]), (2, 1, 0.5))


if __name__ == "__main__":
    unittest.main()
