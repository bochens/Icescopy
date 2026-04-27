import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import Icescopy as icescopy_module  # noqa: E402
from Icescopy import IceScopy  # noqa: E402
from icescopy_temperature_import import TemperatureImportError  # noqa: E402
from icescopy_session_io import (  # noqa: E402
    FREEZE_COUNT_TIMESERIES_CSV_FILENAME,
    FREEZE_CSV_FILENAME,
    GRAYSCALE_CSV_FILENAME,
    SESSION_STATE_FILENAME,
    build_freeze_count_timeseries_csv_text,
    build_restore_state,
    build_session_payload,
    load_session_bundle,
    save_session_bundle,
)


class SessionIoTests(unittest.TestCase):
    def bind_sample_allocator_methods(self, fake_window):
        fake_window.used_sample_ids = lambda: IceScopy.used_sample_ids(fake_window)
        fake_window.lowest_available_sample_id = lambda: IceScopy.lowest_available_sample_id(fake_window)
        fake_window.recompute_next_sample_id = (
            lambda preserve_if_larger=True: IceScopy.recompute_next_sample_id(
                fake_window,
                preserve_if_larger=preserve_if_larger,
            )
        )
        fake_window.allocate_sample_id = lambda: IceScopy.allocate_sample_id(fake_window)

    def bind_pku_temperature_methods(self, fake_window):
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: None
        fake_window.build_freeze_count_timeseries_sample_groups = (
            lambda grouping_mode="samples": IceScopy.build_freeze_count_timeseries_sample_groups(
                fake_window,
                grouping_mode=grouping_mode,
            )
        )
        fake_window.build_tamu_freeze_count_timeseries_sample_groups = (
            lambda: IceScopy.build_tamu_freeze_count_timeseries_sample_groups(fake_window)
        )
        fake_window.build_freeze_count_timeseries_blank_selection = (
            lambda sample_groups, blank_sample_names=None: IceScopy.build_freeze_count_timeseries_blank_selection(
                fake_window,
                sample_groups,
                blank_sample_names=blank_sample_names,
            )
        )
        fake_window.detect_cycle_start_indexes_from_temperatures = (
            lambda temperatures, reset_temperature: IceScopy.detect_cycle_start_indexes_from_temperatures(
                fake_window,
                temperatures,
                reset_temperature,
            )
        )
        fake_window.build_cycle_ids_from_start_indexes = (
            lambda total_count, cycle_start_indexes: IceScopy.build_cycle_ids_from_start_indexes(
                fake_window,
                total_count,
                cycle_start_indexes,
            )
        )
        fake_window.cycle_index_for_position = (
            lambda position_value, cycle_start_positions: IceScopy.cycle_index_for_position(
                fake_window,
                position_value,
                cycle_start_positions,
            )
        )
        fake_window.build_pku_linksys32_image_timing_context = (
            lambda parsed_timeseries, reset_temperature=None: IceScopy.build_pku_linksys32_image_timing_context(
                fake_window,
                parsed_timeseries,
                reset_temperature=reset_temperature,
            )
        )
        fake_window.build_tamu_cycle_reset_image_counts = (
            lambda sample_groups, image_cycle_ids: IceScopy.build_tamu_cycle_reset_image_counts(
                fake_window,
                sample_groups,
                image_cycle_ids,
            )
        )
        fake_window.normalize_temperature_reset_threshold = (
            lambda reset_temperature: IceScopy.normalize_temperature_reset_threshold(
                fake_window,
                reset_temperature,
            )
        )
        fake_window.build_pku_linksys32_freeze_count_timeseries_results = (
            lambda parsed_timeseries, **kwargs: IceScopy.build_pku_linksys32_freeze_count_timeseries_results(
                fake_window,
                parsed_timeseries,
                **kwargs,
            )
        )

    def make_pku_parsed_timeseries(self, image_count=2):
        start_timestamp = datetime(2025, 2, 17, 18, 25, 38, 395000)
        image_records = [
            SimpleNamespace(
                timestamp=start_timestamp + timedelta(seconds=0.5 + index),
                temperature_value=-10.0 - index,
            )
            for index in range(image_count)
        ]
        return SimpleNamespace(
            file_path="/tmp/sample.iml",
            version="V1.4",
            start_timestamp=start_timestamp,
            start_timestamp_text=start_timestamp.isoformat(timespec="milliseconds"),
            sample_period_seconds=1.0,
            timeseries_seconds=[0.0, 1.0, 2.0],
            timeseries_datetimes=[
                start_timestamp,
                start_timestamp + timedelta(seconds=1),
                start_timestamp + timedelta(seconds=2),
            ],
            timeseries_timestamp_texts=[
                start_timestamp.isoformat(timespec="microseconds"),
                (start_timestamp + timedelta(seconds=1)).isoformat(timespec="microseconds"),
                (start_timestamp + timedelta(seconds=2)).isoformat(timespec="microseconds"),
            ],
            temperature_values=[-1.0, -2.0, -3.0],
            timeseries_row_count=3,
            image_records=image_records,
            image_record_count=len(image_records),
        )

    def test_pku_linksys32_import_uses_iml_image_record_timestamps_and_temperatures(self):
        fake_window = SimpleNamespace(
            imageNames=["frame_001.jpg", "frame_002.jpg"],
            imagePaths=["/tmp/frame_001.jpg", "/tmp/frame_002.jpg"],
            cell_records_by_id={},
            temperature_cycle_warmup_hysteresis_c=0.02,
        )
        self.bind_pku_temperature_methods(fake_window)

        headers, rows, summary = fake_window.build_pku_linksys32_freeze_count_timeseries_results(
            self.make_pku_parsed_timeseries(),
        )

        self.assertEqual(
            headers,
            ["timestamp", "temperature_C", "cycle", "image_name", "water blank correction count"],
        )
        self.assertEqual(rows[0][:4], ["2025-02-17T18:25:38.895", "-10.000", "0", "frame_001.jpg"])
        self.assertEqual(rows[1][:4], ["2025-02-17T18:25:39.895", "-11.000", "0", "frame_002.jpg"])
        self.assertEqual(summary["source_type"], "pku_linksys32_iml")
        self.assertEqual(summary["image_record_count"], 2)
        self.assertEqual(summary["temperature_source"], "pku_linksys32_image_record")
        self.assertEqual(summary["tagged_temperature_count"], 2)

    def test_pku_linksys32_import_rejects_image_count_mismatch(self):
        fake_window = SimpleNamespace(
            imageNames=["frame_001.jpg", "frame_002.jpg"],
            imagePaths=["/tmp/frame_001.jpg", "/tmp/frame_002.jpg"],
            cell_records_by_id={},
            temperature_cycle_warmup_hysteresis_c=0.02,
        )
        self.bind_pku_temperature_methods(fake_window)

        with self.assertRaises(TemperatureImportError):
            fake_window.build_pku_linksys32_freeze_count_timeseries_results(
                self.make_pku_parsed_timeseries(image_count=1),
            )

    def test_pku_import_dialog_uses_keyword_arguments_without_calibration(self):
        captured_kwargs = {}

        class FakePKUDialog:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            def exec(self):
                return 0

        original_dialog = icescopy_module.PKUTemperatureImportDialog
        try:
            icescopy_module.PKUTemperatureImportDialog = FakePKUDialog
            fake_window = SimpleNamespace(
                imagePaths=["/tmp/frame_001.jpg"],
                last_temperature_import_path="/tmp/sample.iml",
                last_temperature_reset_temperature=None,
                last_temperature_blank_sample_names=[],
                available_sample_names=lambda: ["Sample A"],
            )

            IceScopy.import_pku_linksys32_iml(fake_window)
        finally:
            icescopy_module.PKUTemperatureImportDialog = original_dialog

        self.assertEqual(captured_kwargs["main_window"], fake_window)
        self.assertEqual(captured_kwargs["sample_names"], ["Sample A"])
        self.assertEqual(captured_kwargs["initial_blank_sample_names"], [])
        self.assertEqual(captured_kwargs["parent"], fake_window)
        self.assertNotIn("initial_calibration_path", captured_kwargs)

    def test_sample_id_allocator_reuses_lowest_deleted_catalog_id(self):
        fake_window = SimpleNamespace(
            sample_catalog={1: {"sample_name": "Sample_1"}, 2: {"sample_name": "Sample_2"}},
            cell_records_by_id={},
            next_sample_id=99,
        )
        self.bind_sample_allocator_methods(fake_window)

        sample_id = fake_window.allocate_sample_id()
        self.assertEqual(sample_id, 0)

        fake_window.sample_catalog[sample_id] = {"sample_name": "Sample_0"}
        self.assertEqual(fake_window.recompute_next_sample_id(preserve_if_larger=False), 3)

        fake_window.sample_catalog.pop(0)
        self.assertEqual(fake_window.recompute_next_sample_id(preserve_if_larger=False), 0)

    def test_sample_id_allocator_reserves_ids_assigned_to_cells(self):
        fake_window = SimpleNamespace(
            sample_catalog={1: {"sample_name": "Sample_1"}},
            cell_records_by_id={10: SimpleNamespace(sample_id="0")},
            next_sample_id=0,
        )
        self.bind_sample_allocator_methods(fake_window)

        self.assertEqual(fake_window.allocate_sample_id(), 2)

    def test_refresh_freeze_count_timeseries_metadata_preserves_rows_and_relabels_headers(self):
        fake_window = SimpleNamespace(
            freeze_count_timeseries_headers=[
                "timestamp",
                "temperature_C",
                "Sample_0 number total",
                "Sample_0 number frozen",
            ],
            freeze_count_timeseries_rows=[
                ["2026-04-22 12:00:00", "-12.3", "2", "1"]
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
                    "sampling_site": "Colorado State University",
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
            fake_window.freeze_count_timeseries_headers[2:4],
            [
                "Marine Aerosol number total",
                "Marine Aerosol number frozen",
            ],
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_rows,
            [["2026-04-22 12:00:00", "-12.3", "2", "1"]],
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_summary["sample_column_metadata"][0]["sample_long_name"],
            "MOASIC marine aerosol",
        )
        self.assertEqual(
            fake_window.freeze_count_timeseries_summary["sample_column_metadata"][0]["sampling_site"],
            "Colorado State University",
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
                "Sample_0 number total",
                "Sample_0 number frozen",
            ],
            freeze_count_timeseries_rows=[
                ["2026-04-22 12:00:00", "-12.3", "2", "1"]
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
            "Sample_0 number total",
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

        metadata = IceScopy.build_freeze_count_timeseries_sample_column_metadata(
            fake_window,
            groups["1"],
        )
        self.assertEqual(metadata["cell_number"], "1")

    def test_freeze_count_timeseries_grouping_keeps_unassigned_cells_as_single_cell_groups(self):
        fake_window = SimpleNamespace(
            cell_records_by_id={
                10: SimpleNamespace(sample_id="1"),
                11: SimpleNamespace(sample_id=""),
                12: SimpleNamespace(sample_id=None),
            },
            sample_catalog={
                1: {
                    "sample_name": "Sample_1",
                    "sample_long_name": "",
                    "sampling_site": "",
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
            },
        )
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]

        groups = IceScopy.build_freeze_count_timeseries_sample_groups(fake_window, grouping_mode="samples")

        self.assertEqual(sorted(groups.keys()), ["1", "__cell_11__", "__cell_12__"])
        self.assertEqual(groups["1"]["sample_name"], "Sample_1")
        self.assertEqual(groups["1"]["cell_ids"], [10])
        self.assertEqual(groups["__cell_11__"]["sample_id"], "")
        self.assertEqual(groups["__cell_11__"]["sample_name"], "Cell 11")
        self.assertEqual(groups["__cell_11__"]["cell_ids"], [11])
        self.assertEqual(groups["__cell_11__"]["total_cells"], 1)
        self.assertEqual(groups["__cell_12__"]["sample_name"], "Cell 12")
        self.assertEqual(groups["__cell_12__"]["cell_ids"], [12])

        matched_samples, _blank_samples, output_samples, _unmatched_blank_samples = (
            IceScopy.build_freeze_count_timeseries_blank_selection(fake_window, groups)
        )
        self.assertEqual(
            [sample["sample_name"] for sample in output_samples],
            ["Sample_1", "Cell 11", "Cell 12"],
        )
        self.assertEqual(
            [sample["group_key"] for sample in matched_samples],
            ["1", "__cell_11__", "__cell_12__"],
        )

        metadata = IceScopy.build_freeze_count_timeseries_sample_column_metadata(
            fake_window,
            groups["__cell_11__"],
        )
        self.assertEqual(metadata["sample_id"], "")
        self.assertEqual(metadata["sample_name"], "Cell 11")
        self.assertEqual(metadata["cell_number"], "1")

    def test_pku_linksys32_import_outputs_unassigned_cells_as_columns(self):
        fake_window = SimpleNamespace(
            imageNames=["frame_001.jpg", "frame_002.jpg"],
            imagePaths=["/tmp/frame_001.jpg", "/tmp/frame_002.jpg"],
            cell_records_by_id={
                0: SimpleNamespace(sample_id="1", freeze_event_indices=[1]),
                2: SimpleNamespace(sample_id="", freeze_event_indices=[0]),
            },
            sample_catalog={
                1: {
                    "sample_name": "Sample_1",
                    "sample_long_name": "",
                    "sampling_site": "",
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
            },
            temperature_cycle_warmup_hysteresis_c=0.02,
        )
        self.bind_pku_temperature_methods(fake_window)
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]
        fake_window.build_freeze_count_timeseries_sample_column_metadata = (
            lambda sample: IceScopy.build_freeze_count_timeseries_sample_column_metadata(fake_window, sample)
        )

        headers, rows, summary = fake_window.build_pku_linksys32_freeze_count_timeseries_results(
            self.make_pku_parsed_timeseries(),
        )

        self.assertEqual(
            headers,
            [
                "timestamp",
                "temperature_C",
                "cycle",
                "image_name",
                "water blank correction count",
                "Sample_1 number total",
                "Sample_1 number frozen",
                "Cell 2 number total",
                "Cell 2 number frozen",
            ],
        )
        self.assertEqual(rows[0][5:], ["1", "0", "1", "1"])
        self.assertEqual(rows[1][5:], ["1", "1", "1", "1"])
        self.assertEqual(summary["matched_samples"], ["Sample_1", "Cell 2"])
        self.assertEqual(
            [metadata["sample_name"] for metadata in summary["sample_column_metadata"]],
            ["Sample_1", "Cell 2"],
        )
        self.assertEqual(summary["sample_column_metadata"][1]["sample_id"], "")
        self.assertEqual(summary["sample_column_metadata"][1]["cell_number"], "1")

    def test_csu_import_outputs_unassigned_cells_as_app_count_columns(self):
        fake_window = SimpleNamespace(
            imageNames=["frame_001.png", "frame_002.png"],
            imagePaths=["/tmp/frame_001.png", "/tmp/frame_002.png"],
            cell_records_by_id={
                0: SimpleNamespace(sample_id="1", freeze_event_indices=[1]),
                2: SimpleNamespace(sample_id="", freeze_event_indices=[0]),
            },
            sample_catalog={
                1: {
                    "sample_name": "Sample_1",
                    "sample_long_name": "",
                    "sampling_site": "",
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
            },
            temperature_cycle_warmup_hysteresis_c=0.02,
        )
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]
        fake_window.build_freeze_count_timeseries_sample_groups = (
            lambda grouping_mode="samples": IceScopy.build_freeze_count_timeseries_sample_groups(
                fake_window,
                grouping_mode=grouping_mode,
            )
        )
        fake_window.detect_cycle_start_indexes_from_temperatures = (
            lambda temperatures, reset_temperature: IceScopy.detect_cycle_start_indexes_from_temperatures(
                fake_window,
                temperatures,
                reset_temperature,
            )
        )
        fake_window.build_cycle_ids_from_start_indexes = (
            lambda total_count, cycle_start_indexes: IceScopy.build_cycle_ids_from_start_indexes(
                fake_window,
                total_count,
                cycle_start_indexes,
            )
        )
        fake_window.build_tamu_cycle_reset_image_counts = (
            lambda sample_groups, image_cycle_ids: IceScopy.build_tamu_cycle_reset_image_counts(
                fake_window,
                sample_groups,
                image_cycle_ids,
            )
        )
        fake_window.reconcile_counts_by_cycle = (
            lambda raw_counts, anchor_counts, maximum_count, cycle_ids: IceScopy.reconcile_counts_by_cycle(
                fake_window,
                raw_counts,
                anchor_counts,
                maximum_count,
                cycle_ids,
            )
        )
        fake_window.normalize_temperature_reset_threshold = (
            lambda reset_temperature: IceScopy.normalize_temperature_reset_threshold(
                fake_window,
                reset_temperature,
            )
        )
        fake_window.build_freeze_count_timeseries_sample_column_metadata = (
            lambda sample: IceScopy.build_freeze_count_timeseries_sample_column_metadata(fake_window, sample)
        )
        parsed_data = {
            "file_path": "/tmp/sample.dat",
            "sample_columns": ["Sample_1"],
            "rows": [
                SimpleNamespace(
                    row_index=0,
                    timestamp_text="2026-04-22 12:00:00",
                    avg_temp=-5.0,
                    picture_name="frame_001.png",
                    sample_counts={"Sample_1": 0},
                ),
                SimpleNamespace(
                    row_index=1,
                    timestamp_text="2026-04-22 12:00:01",
                    avg_temp=-6.0,
                    picture_name="frame_002.png",
                    sample_counts={"Sample_1": 1},
                ),
            ],
        }

        headers, rows, summary = IceScopy.build_csu_freeze_count_timeseries_results(
            fake_window,
            parsed_data,
        )

        self.assertEqual(
            headers,
            [
                "timestamp",
                "temperature_C",
                "cycle",
                "picture",
                "water blank correction count",
                "Sample_1 number total",
                "Sample_1 number frozen",
                "Cell 2 number total",
                "Cell 2 number frozen",
            ],
        )
        self.assertEqual(rows[0][5:], ["1", "0", "1", "1"])
        self.assertEqual(rows[1][5:], ["1", "1", "1", "1"])
        self.assertEqual(summary["matched_samples"], ["Sample_1", "Cell 2"])
        self.assertEqual(summary["unmatched_app_samples"], [])
        self.assertEqual(
            [metadata["sample_name"] for metadata in summary["sample_column_metadata"]],
            ["Sample_1", "Cell 2"],
        )

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
                        "column_indices": [3, 4],
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
            "- Sample 1 (Sample A): sample_long_name, sampling_site, collection_start, collection_end, dilution, air_volume_L, suspension_volume_mL, dry_mass_g",
            report_lines,
        )

    def test_build_freeze_count_timeseries_csv_text_writes_preamble_and_metadata_rows(self):
        headers = [
            "timestamp",
            "temperature_C",
            "cycle",
            "Sample A number total",
            "Sample A number frozen",
        ]
        rows = [["2026-04-22T12:00:00.000", "-12.300", "0", "2", "1"]]
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
                        "sampling_site": "Storm Peak Laboratory",
                        "collection_start": "2026-04-22T12:00:00",
                        "collection_end": "2026-04-22T18:00:00",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                        "sample_note": "note",
                        "cell_number": "2",
                        "column_indices": [3, 4],
                    }
                ],
            },
        )

        self.assertIn("# format_name: icescopy_freeze_count_timeseries\n", csv_text)
        self.assertIn("# file_version: 1\n", csv_text)
        self.assertIn("# project_name: Proj\n", csv_text)
        self.assertIn("# analysis_date: 2026-04-22\n", csv_text)
        self.assertIn("# well_volume_uL: 50\n", csv_text)
        self.assertIn("# reset_temperature_C: 5.0\n", csv_text)
        self.assertNotIn("# date:", csv_text)
        self.assertNotIn("# exported_at:", csv_text)
        self.assertIn("# sample_id,1\n", csv_text)
        self.assertIn("# cell_number,2\n", csv_text)
        self.assertIn("# sample_name,Sample A\n", csv_text)
        self.assertIn("# sampling_site,Storm Peak Laboratory\n", csv_text)
        self.assertIn("# collection_start,2026-04-22T12:00:00\n", csv_text)
        self.assertIn("# collection_end,2026-04-22T18:00:00\n", csv_text)
        self.assertIn("# sample_type,air\n", csv_text)
        non_comment_lines = [
            line for line in csv_text.splitlines()
            if not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            non_comment_lines[0],
            "timestamp,temperature_C,cycle,Sample A number total,Sample A number frozen",
        )
        self.assertIn("2026-04-22T12:00:00.000,-12.300,0,2,1", csv_text)

    def test_build_freeze_count_timeseries_csv_text_uses_nan_for_missing_metadata_values(self):
        headers = [
            "timestamp",
            "temperature_C",
            "cycle",
            "Sample A number total",
            "Sample A number frozen",
        ]
        rows = [["2026-04-22T12:00:00.000", "-12.300", "0", "1", "0"]]
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
                        "column_indices": [3, 4],
                    }
                ],
            },
        )

        self.assertIn("# project_name: nan\n", csv_text)
        self.assertIn("# analysis_date: nan\n", csv_text)
        self.assertIn("# well_volume_uL: nan\n", csv_text)
        self.assertIn("# reset_temperature_C: nan\n", csv_text)
        self.assertNotIn("# exported_at:", csv_text)
        self.assertIn("# cell_number,nan\n", csv_text)
        self.assertIn("# sample_long_name,nan\n", csv_text)
        self.assertIn("# sampling_site,nan\n", csv_text)
        self.assertIn("# collection_start,nan\n", csv_text)
        self.assertIn("# collection_end,nan\n", csv_text)
        self.assertIn("# air_volume_L,nan\n", csv_text)

    def test_build_session_payload_stores_current_tool_settings(self):
        fake_window = SimpleNamespace(
            serialize_session_metadata=lambda: {},
            serialize_image_edit_state=lambda: {},
            image_width=100,
            imagePaths=["/tmp/example.png"],
            imageNames=["example.png"],
            image_index=0,
            image_list_entry_ids=[0],
            next_image_list_entry_id=1,
            sort_mode="natural_filename",
            cell_items=[],
            next_cell_id=0,
            serialize_cell_records=lambda: {},
            serialize_sample_catalog=lambda: {},
            next_sample_id=0,
            keyframe_list=[],
            flagframe_list=[],
            keyframe_cell_items_dict={},
            tool_mode="grid",
            circle_radius=37.5,
            grid_rows=6,
            grid_columns=7,
            grid_horizontal_pitch=41.25,
            grid_vertical_pitch=42.5,
            grid_rotation_degrees=12.0,
            default_tool_settings=lambda: {
                "circle_radius": 22.0,
                "grid_rows": 4,
                "grid_columns": 4,
                "grid_horizontal_pitch": 60.0,
                "grid_vertical_pitch": 60.0,
                "grid_rotation_degrees": 0.0,
            },
            normalize_tool_settings=lambda settings: {
                "circle_radius": float(settings["circle_radius"]),
                "grid_rows": int(settings["grid_rows"]),
                "grid_columns": int(settings["grid_columns"]),
                "grid_horizontal_pitch": float(settings["grid_horizontal_pitch"]),
                "grid_vertical_pitch": float(settings["grid_vertical_pitch"]),
                "grid_rotation_degrees": float(settings["grid_rotation_degrees"]),
            },
            last_grayscale_output_path="",
            last_freeze_output_path="",
            last_temperature_import_path="",
            last_temperature_calibration_path="",
            last_temperature_reset_temperature=None,
            last_temperature_blank_sample_names=[],
            last_standard_temperature_image_timestamp_source="filename",
            last_standard_temperature_image_timestamp_style="auto",
            last_standard_temperature_temperature_timestamp_style="auto",
            last_standard_temperature_use_image_timestamp_style=True,
            last_standard_temperature_generated_start_text="",
            last_standard_temperature_frame_interval_seconds=1.0,
            last_standard_temperature_temperature_unit="celsius",
            freeze_count_timeseries_summary={},
            terminal=SimpleNamespace(toPlainText=lambda: ""),
        )
        fake_window.serialize_tool_settings = (
            lambda: IceScopy.serialize_tool_settings(fake_window)
        )

        payload = build_session_payload(fake_window)

        self.assertEqual(
            payload["tool_settings"],
            {
                "circle_radius": 37.5,
                "grid_rows": 6,
                "grid_columns": 7,
                "grid_horizontal_pitch": 41.25,
                "grid_vertical_pitch": 42.5,
                "grid_rotation_degrees": 12.0,
            },
        )

    def minimal_restore_payload(self):
        return {
            "session_metadata": {},
            "image_edit_state": {},
            "cell_items": [],
            "next_cell_id": 0,
            "cell_records_by_id": {},
            "sample_catalog": {},
            "next_sample_id": 0,
            "keyframe_list": [],
            "flagframe_list": [],
            "keyframe_cell_items_dict": {},
            "image_width": 100,
            "image_paths": ["/tmp/example.png"],
            "image_names": ["example.png"],
            "image_index": 0,
            "image_list_entry_ids": [0],
            "next_image_list_entry_id": 1,
            "sort_mode": "natural_filename",
            "last_grayscale_output_path": "",
            "last_freeze_output_path": "",
            "last_temperature_import_path": "",
            "last_temperature_calibration_path": "",
            "last_temperature_reset_temperature": None,
            "last_temperature_blank_sample_names": [],
            "last_standard_temperature_image_timestamp_source": "filename",
            "last_standard_temperature_image_timestamp_style": "auto",
            "last_standard_temperature_temperature_timestamp_style": "auto",
            "last_standard_temperature_use_image_timestamp_style": True,
            "last_standard_temperature_generated_start_text": "",
            "last_standard_temperature_frame_interval_seconds": 1.0,
            "last_standard_temperature_temperature_unit": "celsius",
            "freeze_count_timeseries_summary": {},
            "tool_mode": "grid",
            "console_history": "",
        }

    def test_build_restore_state_uses_default_tool_settings_when_json_is_missing_them(self):
        fake_window = SimpleNamespace(
            default_tool_settings=lambda: {
                "circle_radius": 22.0,
                "grid_rows": 4,
                "grid_columns": 4,
                "grid_horizontal_pitch": 60.0,
                "grid_vertical_pitch": 60.0,
                "grid_rotation_degrees": 0.0,
            }
        )

        state = build_restore_state(
            fake_window,
            self.minimal_restore_payload(),
            ([], []),
            ([], []),
            ([], []),
        )

        self.assertEqual(
            state["tool_settings"],
            {
                "circle_radius": 22.0,
                "grid_rows": 4,
                "grid_columns": 4,
                "grid_horizontal_pitch": 60.0,
                "grid_vertical_pitch": 60.0,
                "grid_rotation_degrees": 0.0,
            },
        )

    def test_build_restore_state_keeps_saved_tool_settings(self):
        payload = self.minimal_restore_payload()
        payload["tool_settings"] = {
            "circle_radius": 31.0,
            "grid_rows": 8,
            "grid_columns": 12,
            "grid_horizontal_pitch": 41.6,
            "grid_vertical_pitch": 41.4,
            "grid_rotation_degrees": 5.0,
        }
        fake_window = SimpleNamespace(default_tool_settings=lambda: {})

        state = build_restore_state(fake_window, payload, ([], []), ([], []), ([], []))

        self.assertEqual(state["tool_settings"], payload["tool_settings"])

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
                    "sampling_site": "Storm Peak Laboratory",
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
                        "sampling_site": "Storm Peak Laboratory",
                        "collection_start": "2026-04-22T12:00:00",
                        "collection_end": "2026-04-22T18:00:00",
                        "sample_type": "air",
                        "dilution": "1",
                        "air_volume_L": "100",
                        "filter_fraction_used": "0.5",
                        "suspension_volume_mL": "2",
                        "dry_mass_g": "",
                        "sample_note": "note",
                        "cell_number": "2",
                        "column_indices": [2, 3],
                    }
                ],
            },
        }

        grayscale_headers = ["image_name", "cell_0_grayscale"]
        grayscale_rows = [["frame_0001.png", "123.4"]]
        freeze_headers = ["cell", "image_index", "image_name"]
        freeze_rows = [["cell_0", "4", "frame_0005.png"]]
        temperature_headers = ["timestamp", "temperature_C", "sample_A number total", "sample_A number frozen"]
        temperature_rows = [["2026-04-22 12:00:00", "-12.3", "2", "1"]]

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
                    "timestamp,temperature_C,sample_A number total,sample_A number frozen\n"
                    "2026-04-22 12:00:00,-12.3,2,1\n",
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
