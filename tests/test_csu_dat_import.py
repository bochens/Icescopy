import csv
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_temperature_import import TemperatureImportError, parse_csu_is_dat


class CSUDatImportTests(unittest.TestCase):
    def parse_rows(self, header, rows, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.dat"
            with path.open("w", encoding=encoding, newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                if header is not None:
                    writer.writerow(header)
                writer.writerows(rows)
            return parse_csu_is_dat(path)

    def test_legacy_temperature_and_named_sample_columns_are_preserved(self):
        parsed = self.parse_rows(
            ["Date", "Time", "Avg_Temp", "Picture", "Sample_0", "Sample_blank"],
            [["01/01/26", "12:00:00", "-5.25", "frame_1.png", "0", "2"]],
        )
        self.assertEqual(parsed["temperature_column"], "Avg_Temp")
        self.assertEqual(parsed["sample_columns"], ["Sample_0", "Sample_blank"])
        row = parsed["rows"][0]
        self.assertEqual(row.avg_temp, -5.25)
        self.assertEqual(row.sample_counts, {"Sample_0": 0, "Sample_blank": 2})
        self.assertEqual(row.timestamp, datetime(2026, 1, 1, 12))
        self.assertEqual(parsed["count_value_summary"], {
            "total_values": 2, "valid_values": 2, "invalid_values": 0, "positive_values": 1,
        })

    def test_cold_stage_picture_matches_exact_fractional_timestamp(self):
        parsed = self.parse_rows(
            ["Time", "", "Sample_Temp", "CP_Sink_Temp", "Sample_0", "Picture"],
            [
                ["01/02/26", "16:05:39:.36", "-5.25", "18.0", "0", r"C:\run\Image_0.png"],
                ["01/02/26", "16:05:40:.123456", "-5.5", "18.0", "1", "/run/Image_1.png"],
            ],
            encoding="utf-8-sig",
        )
        self.assertEqual(parsed["temperature_column"], "Sample_Temp")
        self.assertEqual(parsed["sample_columns"], ["Sample_0"])
        self.assertEqual(parsed["picture_to_row"], {"image_0.png": 0, "image_1.png": 1})
        first = parsed["rows"][parsed["picture_to_row"]["image_0.png"]]
        second = parsed["rows"][parsed["picture_to_row"]["image_1.png"]]
        self.assertEqual(first.timestamp, datetime(2026, 1, 2, 16, 5, 39, 360000))
        self.assertEqual(second.timestamp, datetime(2026, 1, 2, 16, 5, 40, 123456))
        self.assertEqual(first.timestamp_text, "2026-01-02T16:05:39.360")
        self.assertEqual(first.picture_name, "Image_0.png")
        self.assertEqual(first.avg_temp, -5.25)
        self.assertEqual(first.sample_counts, {"Sample_0": 0})

    def test_file_without_instrument_counts_remains_usable(self):
        parsed = self.parse_rows(
            ["Time", "", "Sample_Temp", "Picture"],
            [["01/01/26", "12:00:00", "-5", "Image_0.png"]],
        )
        self.assertEqual(parsed["sample_columns"], [])
        self.assertEqual(parsed["rows"][0].sample_counts, {})
        self.assertEqual(parsed["invalid_sample_counts_by_column"], {})
        self.assertEqual(parsed["count_value_summary"], {
            "total_values": 0, "valid_values": 0, "invalid_values": 0, "positive_values": 0,
        })

    def test_invalid_counts_are_missing_values_instead_of_zero(self):
        values = ["", "unavailable", "1.5", "-1", "nan", "inf", "0", " 3 "]
        parsed = self.parse_rows(
            ["Date", "Time", "Avg_Temp", "Picture", "Sample_0"],
            [["01/01/26", f"12:00:{index:02d}", "-5", "", value]
             for index, value in enumerate(values)],
        )
        self.assertEqual(
            [row.sample_counts["Sample_0"] for row in parsed["rows"]],
            [None, None, None, None, None, None, 0, 3],
        )
        self.assertEqual(parsed["invalid_sample_counts_by_column"], {"Sample_0": 6})
        self.assertEqual(parsed["count_value_summary"], {
            "total_values": 8, "valid_values": 2, "invalid_values": 6, "positive_values": 1,
        })

    def test_zero_counts_remain_valid_without_claiming_detector_state(self):
        parsed = self.parse_rows(
            ["Date", "Time", "Avg_Temp", "Picture", "Sample_0"],
            [["01/01/26", "12:00:00", "-5", "Image_0.png", "0"]],
        )
        self.assertEqual(parsed["rows"][0].sample_counts["Sample_0"], 0)
        self.assertEqual(parsed["count_value_summary"]["valid_values"], 1)
        self.assertEqual(parsed["count_value_summary"]["invalid_values"], 0)
        self.assertEqual(parsed["count_value_summary"]["positive_values"], 0)

    def test_both_temperature_fields_are_rejected_as_ambiguous(self):
        with self.assertRaisesRegex(TemperatureImportError, "both Avg_Temp and Sample_Temp"):
            self.parse_rows(
                ["Date", "Time", "Avg_Temp", "Sample_Temp", "Picture"],
                [["01/01/26", "12:00:00", "-5", "-6", "Image_0.png"]],
            )

    def test_duplicate_required_and_sample_headers_are_rejected(self):
        for duplicate in ("Avg_Temp", "Picture", "Sample_0", "sample_0"):
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(TemperatureImportError, "duplicate"):
                self.parse_rows(
                    ["Date", "Time", "Avg_Temp", "Picture", "Sample_0", duplicate],
                    [["01/01/26", "12:00:00", "-5", "Image_0.png", "0", "0"]],
                )

    def test_duplicate_picture_basenames_are_rejected_across_platform_paths(self):
        with self.assertRaisesRegex(TemperatureImportError, "lines 2 and 4"):
            self.parse_rows(
                ["Date", "Time", "Sample_Temp", "Picture"],
                [
                    ["01/01/26", "12:00:00", "-5", r"C:\first\Image_0.png"],
                    [],
                    ["01/01/26", "12:00:01", "-6", "/second/IMAGE_0.PNG"],
                ],
            )

    def test_blank_lines_do_not_create_records_or_break_picture_indexes(self):
        parsed = self.parse_rows(
            ["Date", "Time", "Sample_Temp", "Picture"],
            [
                [],
                ["01/01/26", "12:00:00", "-5", ""],
                ["", "", "", ""],
                ["01/01/26", "12:00:01", "-6", "Image_0.png"],
                [],
            ],
        )
        self.assertEqual([row.row_index for row in parsed["rows"]], [0, 1])
        self.assertEqual(parsed["picture_to_row"], {"image_0.png": 1})

    def test_short_rows_preserve_missing_count_values(self):
        parsed = self.parse_rows(
            ["Date", "Time", "Avg_Temp", "Picture", "Sample_0"],
            [["01/01/26", "12:00:00", "-5", "Image_0.png"]],
        )
        self.assertIsNone(parsed["rows"][0].sample_counts["Sample_0"])
        self.assertEqual(parsed["count_value_summary"]["invalid_values"], 1)

    def test_unavailable_time_and_temperature_remain_unavailable(self):
        for value in ("missing", "nan", "inf", "-inf"):
            with self.subTest(value=value):
                parsed = self.parse_rows(
                    ["Date", "Time", "Sample_Temp", "Picture"],
                    [["invalid date", "12:00:00", value, "Image_0.png"]],
                )
                self.assertIsNone(parsed["rows"][0].timestamp)
                self.assertIsNone(parsed["rows"][0].avg_temp)

    def test_missing_required_fields_and_empty_records_are_rejected(self):
        cases = (
            (None, [], "empty"),
            ([], [], "no header"),
            (["Date", "Time", "Picture"], [["01/01/26", "12:00:00", "Image_0.png"]], "temperature|Avg_Temp"),
            (["Date", "Time", "Avg_Temp"], [["01/01/26", "12:00:00", "-5"]], "Picture"),
            (["Date", "Time", "Avg_Temp", "Picture"], [[], ["", "", "", ""]], "no data rows"),
        )
        for header, rows, message in cases:
            with self.subTest(header=header), self.assertRaisesRegex(TemperatureImportError, message):
                self.parse_rows(header, rows)


if __name__ == "__main__":
    unittest.main()
