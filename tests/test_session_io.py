import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from Icescopy import IceScopy  # noqa: E402
from icescopy_session_io import (  # noqa: E402
    FREEZE_COUNT_TIMESERIES_CSV_FILENAME,
    FREEZE_CSV_FILENAME,
    GRAYSCALE_CSV_FILENAME,
    SESSION_STATE_FILENAME,
    build_freeze_count_timeseries_csv_text,
    load_session_bundle,
    save_session_bundle,
)


class SessionIoTests(unittest.TestCase):
    def test_refresh_freeze_count_timeseries_metadata_preserves_rows_and_relabels_headers(self):
        fake_window = SimpleNamespace(
            freeze_count_timeseries_headers=[
                "timestamp",
                "temperature_C",
                "Sample_0 (n=2) number total",
                "Sample_0 (n=2) number frozen",
                "Sample_0 (n=2) fraction frozen",
            ],
            freeze_count_timeseries_rows=[
                ["2026-04-22 12:00:00", "-12.3", "2", "1", "0.500000"]
            ],
            freeze_count_timeseries_summary={
                "sample_column_metadata": [
                    {
                        "sample_id": "0",
                        "sample_name": "Sample_0",
                        "sample_long_name": "",
                        "collection_start": "",
                        "collection_end": "",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                    }
                ],
                "sample_total_cells": [
                    {"sample_id": "0", "sample_name": "Sample_0", "total_cells": 2, "role": "sample"}
                ],
                "matched_samples": ["Sample_0"],
                "matched_blank_samples": [],
            },
            sample_catalog={
                0: {
                    "sample_name": "Marine Aerosol",
                    "sample_long_name": "MOASIC marine aerosol",
                    "collection_start": "",
                    "collection_end": "",
                    "sample_type": "air",
                    "dilution": "11",
                    "air_volume_L": "120",
                    "filter_fraction_used": "0.25",
                    "suspension_volume_mL": "4",
                    "dry_mass_g": "",
                    "sample_note": "",
                }
            },
            update_freeze_count_timeseries_table=lambda: None,
            update_session_actions_state=lambda: None,
        )
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]
        fake_window.sample_name_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]["sample_name"]
        fake_window.build_freeze_count_timeseries_sample_column_metadata = (
            lambda sample: IceScopy.build_freeze_count_timeseries_sample_column_metadata(fake_window, sample)
        )
        fake_window.relabel_freeze_count_timeseries_header_sample_name = (
            lambda header_text, sample_name: IceScopy.relabel_freeze_count_timeseries_header_sample_name(
                fake_window,
                header_text,
                sample_name,
            )
        )

        refreshed = IceScopy.refresh_freeze_count_timeseries_metadata_from_sample_catalog(
            fake_window,
            relabel_headers=True,
        )

        self.assertTrue(refreshed)
        self.assertEqual(
            fake_window.freeze_count_timeseries_headers[2:5],
            [
                "Marine Aerosol (n=2) number total",
                "Marine Aerosol (n=2) number frozen",
                "Marine Aerosol (n=2) fraction frozen",
            ],
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_rows,
            [["2026-04-22 12:00:00", "-12.3", "2", "1", "0.500000"]],
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_summary["sample_column_metadata"][0]["sample_long_name"],
            "MOASIC marine aerosol",
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_summary["matched_samples"],
            ["Marine Aerosol"],
        )

    def test_refresh_freeze_count_timeseries_metadata_only_does_not_refresh_visible_table(self):
        refresh_calls = []
        fake_window = SimpleNamespace(
            freeze_count_timeseries_headers=[
                "timestamp",
                "temperature_C",
                "Sample_0 (n=2) number total",
                "Sample_0 (n=2) number frozen",
                "Sample_0 (n=2) fraction frozen",
            ],
            freeze_count_timeseries_rows=[
                ["2026-04-22 12:00:00", "-12.3", "2", "1", "0.500000"]
            ],
            freeze_count_timeseries_summary={
                "sample_column_metadata": [
                    {
                        "sample_id": "0",
                        "sample_name": "Sample_0",
                        "sample_long_name": "",
                        "collection_start": "",
                        "collection_end": "",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                    }
                ],
            },
            sample_catalog={
                0: {
                    "sample_name": "Sample_0",
                    "sample_long_name": "",
                    "collection_start": "",
                    "collection_end": "",
                    "sample_type": "soil",
                    "dilution": "1",
                    "air_volume_L": "",
                    "filter_fraction_used": "",
                    "suspension_volume_mL": "4",
                    "dry_mass_g": "0.2",
                    "sample_note": "",
                }
            },
            update_freeze_count_timeseries_table=lambda: refresh_calls.append("table"),
            update_session_actions_state=lambda: None,
        )
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]
        fake_window.sample_name_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]["sample_name"]
        fake_window.build_freeze_count_timeseries_sample_column_metadata = (
            lambda sample: IceScopy.build_freeze_count_timeseries_sample_column_metadata(fake_window, sample)
        )
        fake_window.relabel_freeze_count_timeseries_header_sample_name = (
            lambda header_text, sample_name: IceScopy.relabel_freeze_count_timeseries_header_sample_name(
                fake_window,
                header_text,
                sample_name,
            )
        )

        refreshed = IceScopy.refresh_freeze_count_timeseries_metadata_from_sample_catalog(
            fake_window,
            relabel_headers=False,
        )

        self.assertTrue(refreshed)
        self.assertEqual(refresh_calls, [])
        self.assertEqual(
            fake_window.freeze_count_timeseries_summary["sample_column_metadata"][0]["sample_type"],
            "soil",
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_headers[2],
            "Sample_0 (n=2) number total",
        )

    def test_freeze_count_timeseries_grouping_uses_sample_id_not_sample_name(self):
        fake_window = SimpleNamespace(
            cell_records_by_id={
                10: SimpleNamespace(sample_id="1"),
                11: SimpleNamespace(sample_id="2"),
            },
            sample_catalog={
                1: {
                    "sample_name": "Same Name",
                    "sample_long_name": "",
                    "collection_start": "",
                    "collection_end": "",
                    "sample_type": "air",
                    "dilution": "1",
                    "air_volume_L": "100",
                    "filter_fraction_used": "0.5",
                    "suspension_volume_mL": "2",
                    "dry_mass_g": "",
                    "sample_note": "",
                },
                2: {
                    "sample_name": "Same Name",
                    "sample_long_name": "",
                    "collection_start": "",
                    "collection_end": "",
                    "sample_type": "soil",
                    "dilution": "2",
                    "air_volume_L": "",
                    "filter_fraction_used": "",
                    "suspension_volume_mL": "5",
                    "dry_mass_g": "0.25",
                    "sample_note": "",
                },
            },
        )
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]

        groups = IceScopy.build_freeze_count_timeseries_sample_groups(fake_window, grouping_mode="samples")

        self.assertEqual(sorted(groups.keys()), ["1", "2"])
        self.assertEqual(groups["1"]["sample_name"], "Same Name")
        self.assertEqual(groups["2"]["sample_name"], "Same Name")
        self.assertEqual(groups["1"]["cell_ids"], [10])
        self.assertEqual(groups["2"]["cell_ids"], [11])

    def test_missing_metadata_report_lists_session_and_sample_gaps(self):
        fake_window = SimpleNamespace(
            serialize_session_metadata=lambda: {
                "project_name": "",
                "user_name": "User",
                "institution": "",
                "date": "2026-04-22",
                "well_volume_uL": "",
            },
            freeze_count_timeseries_summary={
                "sample_column_metadata": [
                    {
                        "sample_id": "1",
                        "sample_name": "Sample A",
                        "sample_long_name": "",
                        "collection_start": "",
                        "collection_end": "",
                        "sample_type": "air",
                        "dilution": "",
                        "air_volume_L": "",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "",
                        "dry_mass_g": "",
                        "column_indices": [3, 4, 5],
                    }
                ]
            },
        )
        fake_window.freeze_count_timeseries_sample_column_metadata = (
            lambda: list(fake_window.freeze_count_timeseries_summary["sample_column_metadata"])
        )

        report_lines = IceScopy.build_freeze_count_timeseries_missing_metadata_report(fake_window)

        self.assertTrue(report_lines)
        self.assertIn("Missing metadata values were written as nan in the exported Freeze Count Timeseries CSV.", report_lines[0])
        self.assertIn("- project_name", report_lines)
        self.assertIn("- institution", report_lines)
        self.assertIn("- well_volume_uL", report_lines)
        self.assertIn(
            "- Sample 1 (Sample A): sample_long_name, collection_start, collection_end, dilution, air_volume_L, suspension_volume_mL, dry_mass_g",
            report_lines,
        )

    def test_build_freeze_count_timeseries_csv_text_writes_preamble_and_metadata_rows(self):
        headers = [
            "timestamp",
            "temperature_C",
            "cycle",
            "Sample A (n=2) number total",
            "Sample A (n=2) number frozen",
            "Sample A (n=2) fraction frozen",
        ]
        rows = [["2026-04-22T12:00:00.000", "-12.300", "0", "2", "1", "0.500000"]]
        csv_text = build_freeze_count_timeseries_csv_text(
            headers,
            rows,
            session_metadata={
                "project_name": "Proj",
                "user_name": "User",
                "institution": "Inst",
                "date": "2026-04-22",
                "well_volume_uL": "50",
            },
            summary={
                "reset_temperature": 5.0,
                "sample_column_metadata": [
                    {
                        "sample_id": "1",
                        "sample_name": "Sample A",
                        "sample_long_name": "Long A",
                        "collection_start": "2026-04-22T12:00:00",
                        "collection_end": "2026-04-22T18:00:00",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                        "sample_note": "note",
                        "column_indices": [3, 4, 5],
                    }
                ],
            },
            exported_at="2026-04-22T12:30:00",
        )

        self.assertIn("# format_name: icescopy_freeze_count_timeseries\n", csv_text)
        self.assertIn("# file_version: 1\n", csv_text)
        self.assertIn("# project_name: Proj\n", csv_text)
        self.assertIn("# well_volume_uL: 50\n", csv_text)
        self.assertIn("# reset_temperature_C: 5.0\n", csv_text)
        self.assertIn("# sample_id,1\n", csv_text)
        self.assertIn("# sample_name,Sample A\n", csv_text)
        self.assertIn("# collection_start,2026-04-22T12:00:00\n", csv_text)
        self.assertIn("# collection_end,2026-04-22T18:00:00\n", csv_text)
        self.assertIn("# sample_type,air\n", csv_text)
        non_comment_lines = [
            line for line in csv_text.splitlines()
            if not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            non_comment_lines[0],
            "timestamp,temperature_C,cycle,Sample A (n=2) number total,Sample A (n=2) number frozen,Sample A (n=2) fraction frozen",
        )
        self.assertIn("2026-04-22T12:00:00.000,-12.300,0,2,1,0.500000", csv_text)

    def test_build_freeze_count_timeseries_csv_text_uses_nan_for_missing_metadata_values(self):
        headers = [
            "timestamp",
            "temperature_C",
            "cycle",
            "Sample A (n=1) number total",
            "Sample A (n=1) number frozen",
            "Sample A (n=1) fraction frozen",
        ]
        rows = [["2026-04-22T12:00:00.000", "-12.300", "0", "1", "0", "0.000000"]]
        csv_text = build_freeze_count_timeseries_csv_text(
            headers,
            rows,
            session_metadata={},
            summary={
                "sample_column_metadata": [
                    {
                        "sample_id": "1",
                        "sample_name": "Sample A",
                        "sample_long_name": "",
                        "collection_start": "",
                        "collection_end": "",
                        "sample_type": "air",
                        "dilution": "",
                        "air_volume_L": "",
                        "filter_fraction_used": "",
                        "suspension_volume_mL": "",
                        "dry_mass_g": "",
                        "column_indices": [3, 4, 5],
                    }
                ],
            },
            exported_at="2026-04-22T12:30:00",
        )

        self.assertIn("# project_name: nan\n", csv_text)
        self.assertIn("# well_volume_uL: nan\n", csv_text)
        self.assertIn("# reset_temperature_C: nan\n", csv_text)
        self.assertIn("# sample_long_name,nan\n", csv_text)
        self.assertIn("# collection_start,nan\n", csv_text)
        self.assertIn("# collection_end,nan\n", csv_text)
        self.assertIn("# air_volume_L,nan\n", csv_text)

    def test_session_bundle_stores_all_three_tables_as_csv(self):
        payload = {
            "image_paths": ["/tmp/example.png"],
            "image_names": ["example.png"],
            "session_metadata": {
                "project_name": "Proj",
                "user_name": "User",
                "institution": "Inst",
                "date": "2026-04-22",
                "well_volume_uL": "50",
            },
            "sample_catalog": {
                "1": {
                    "sample_name": "Sample A",
                    "sample_long_name": "Long A",
                    "collection_start": "2026-04-22T12:00:00",
                    "collection_end": "2026-04-22T18:00:00",
                    "sample_type": "air",
                    "dilution": "1",
                    "air_volume_L": "100",
                    "filter_fraction_used": "0.5",
                    "suspension_volume_mL": "2",
                    "dry_mass_g": "",
                    "sample_note": "note",
                }
            },
            "freeze_count_timeseries_summary": {
                "source_type": "csu",
                "reset_temperature": 5.0,
                "sample_column_metadata": [
                    {
                        "sample_id": "1",
                        "sample_name": "Sample A",
                        "sample_long_name": "Long A",
                        "collection_start": "2026-04-22T12:00:00",
                        "collection_end": "2026-04-22T18:00:00",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                        "sample_note": "note",
                        "column_indices": [2],
                    }
                ],
            },
        }

        grayscale_headers = ["image_name", "cell_0_grayscale"]
        grayscale_rows = [["frame_0001.png", "123.4"]]
        freeze_headers = ["cell", "image_index", "image_name"]
        freeze_rows = [["cell_0", "4", "frame_0005.png"]]
        temperature_headers = ["timestamp", "temperature_C", "sample_A fraction frozen"]
        temperature_rows = [["2026-04-22 12:00:00", "-12.3", "0.500000"]]

        with tempfile.TemporaryDirectory() as td:
            bundle_path = Path(td) / "session.icescopy"

            save_session_bundle(
                bundle_path,
                payload,
                grayscale_headers,
                grayscale_rows,
                freeze_headers,
                freeze_rows,
                temperature_headers,
                temperature_rows,
            )

            with zipfile.ZipFile(bundle_path, "r") as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    sorted(
                        [
                            SESSION_STATE_FILENAME,
                            GRAYSCALE_CSV_FILENAME,
                            FREEZE_CSV_FILENAME,
                            FREEZE_COUNT_TIMESERIES_CSV_FILENAME,
                        ]
                    ),
                )
                session_payload = json.loads(
                    archive.read(SESSION_STATE_FILENAME).decode("utf-8")
                )
                self.assertNotIn("grayscale_results_headers", session_payload)
                self.assertNotIn("grayscale_results_rows", session_payload)
                self.assertNotIn("freeze_results_headers", session_payload)
                self.assertNotIn("freeze_results_rows", session_payload)
                self.assertNotIn("freeze_count_timeseries_headers", session_payload)
                self.assertNotIn("freeze_count_timeseries_rows", session_payload)
                self.assertEqual(
                    session_payload["freeze_count_timeseries_summary"],
                    payload["freeze_count_timeseries_summary"],
                )
                temperature_csv_text = archive.read(FREEZE_COUNT_TIMESERIES_CSV_FILENAME).decode("utf-8")
                self.assertEqual(
                    temperature_csv_text,
                    "timestamp,temperature_C,sample_A fraction frozen\n"
                    "2026-04-22 12:00:00,-12.3,0.500000\n",
                )

            (
                restored_payload,
                grayscale_table,
                freeze_table,
                temperature_table,
            ) = load_session_bundle(bundle_path)

            self.assertEqual(restored_payload, session_payload)
            self.assertEqual(grayscale_table, (grayscale_headers, grayscale_rows))
            self.assertEqual(freeze_table, (freeze_headers, freeze_rows))
            self.assertEqual(temperature_table, (temperature_headers, temperature_rows))


if __name__ == "__main__":
    unittest.main()
