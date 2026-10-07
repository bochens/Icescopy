import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_csu_count_sources import CountWindow, make_data
from PySide6.QtWidgets import QApplication, QTableWidget
from Icescopy import IceScopy
from icescopy_cell import CellStateManager
from icescopy_temperature_import import (
    CSU_COUNT_SOURCE_IMAGES,
    StandardTemperatureTimeseries, TAMULinkamTimeseries,
)
from icescopy_temperature_refresh import rebuild_temperature_counts
from icescopy_session_io import save_session_bundle, load_session_bundle


class RefreshWindow(CountWindow):
    set_freeze_count_timeseries_results = IceScopy.set_freeze_count_timeseries_results
    update_temperature_table_after_edit = IceScopy.update_temperature_table_after_edit
    update_freeze_count_timeseries_table = IceScopy.update_freeze_count_timeseries_table
    refresh_temperature_counts = IceScopy.refresh_temperature_counts
    invalidate_freeze_count_timeseries_results = IceScopy.invalidate_freeze_count_timeseries_results
    set_table_data = IceScopy.set_table_data
    apply_manual_freeze_event_indices_batch = IceScopy.apply_manual_freeze_event_indices_batch
    rebuild_freeze_rows_for_cell = IceScopy.rebuild_freeze_rows_for_cell
    extract_cell_id_from_label = IceScopy.extract_cell_id_from_label

    def __init__(self, names, samples):
        super().__init__(names, samples)
        self.cell_state = CellStateManager(self)
        self.imageNames = self.names
        self.imagePaths = [f"/missing/{name}" for name in names]
        self.freeze_count_timeseries_headers = []
        self.freeze_count_timeseries_rows = []
        self.freeze_count_timeseries_summary = {}
        self.freeze_count_timeseries_table = QTableWidget()
        self.grayscale_results_rows = []
        self.freeze_results_headers = []
        self.freeze_results_rows = []
        self.results_tables_dock = None
        self.logs = []
        self.last_temperature_import_path = "/missing/source"
        self.last_temperature_calibration_path = "/missing/calibration"

    def log(self, message):
        self.logs.append(message)

    def is_video_source(self):
        return False

    def serialize_sample_metadata_schema(self):
        return []

    def update_results_table_visibility(self):
        pass

    def update_session_actions_state(self):
        pass

    def show_dock_widget(self, dock):
        pass

    def frozen_counts(self):
        column = next(i for i, h in enumerate(self.freeze_count_timeseries_headers)
                      if h.endswith(" number frozen"))
        return [row[column] for row in self.freeze_count_timeseries_rows]


class TemperatureRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self, names=None, events=None):
        window = RefreshWindow(names or ["a.png", "b.png", "c.png"],
                               [("Sample_0", [events if events is not None else [1]])])
        self.addCleanup(window.freeze_count_timeseries_table.deleteLater)
        return window

    def test_manual_edit_updates_counts_and_highlights_without_losing_temperature(self):
        window = self.window()
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "c.png"})
        window.set_freeze_count_timeseries_results(*window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_IMAGES))
        original_temperature = [row[1] for row in window.freeze_count_timeseries_rows]
        window.apply_manual_freeze_event_indices_batch({0: [2]}, refresh_tables=False,
                                                       refresh_freeze_markers=False)
        self.assertEqual(window.frozen_counts(), ["0", "0", "1"])
        self.assertEqual([row[1] for row in window.freeze_count_timeseries_rows], original_temperature)
        self.assertEqual(window.logs[-1], "Freeze Count Timeseries updated.")
        column = window.freeze_count_timeseries_headers.index("Sample_0 number frozen")
        self.assertNotEqual(window.freeze_count_timeseries_table.item(1, column).background().color().alpha(), 255)
        self.assertEqual(window.last_temperature_import_path, "/missing/source")
        window.apply_manual_freeze_event_indices_batch({0: []}, refresh_tables=False,
                                                       refresh_freeze_markers=False)
        self.assertEqual(window.frozen_counts(), ["0", "0", "0"])

    def test_import_before_analysis_has_blank_counts_until_events_are_supplied(self):
        window = self.window(events=[])
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "c.png"})
        window.set_freeze_count_timeseries_results(*window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_IMAGES))
        self.assertEqual(window.frozen_counts(), ["", "", ""])
        self.assertTrue(window.freeze_count_timeseries_summary["analysis_required"])
        window.apply_manual_freeze_event_indices_batch({0: [1]}, refresh_tables=False,
                                                       refresh_freeze_markers=False)
        self.assertEqual(window.frozen_counts(), ["0", "1", "1"])
        window.invalidate_freeze_count_timeseries_results("geometry changed", analysis_required=True)
        self.assertEqual(window.frozen_counts(), ["", "", ""])
        self.assertIn("refresh_context", window.freeze_count_timeseries_summary)

    def test_standard_uses_cached_timestamps_and_round_trips_in_session(self):
        window = self.window()
        start = datetime(2026, 1, 1)
        parsed = StandardTemperatureTimeseries("/missing.csv", [start, start + timedelta(seconds=2)],
                                              [start.isoformat(), (start + timedelta(seconds=2)).isoformat()],
                                              [-1, -3], 2)
        results = window.build_standard_freeze_count_timeseries_results(
            parsed, image_timestamp_source="generated_sequence", generated_start_text=start.isoformat(),
            frame_interval_seconds=1)
        # Store the same JSON summary field used by the real .icescopy writer.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.icescopy"
            save_session_bundle(path, {"freeze_count_timeseries_summary": results[2]},
                                [], [], [], [], results[0], results[1])
            payload, _, _, _ = load_session_bundle(path)
        context = payload["freeze_count_timeseries_summary"]["refresh_context"]
        window.cell_records_by_id[0].freeze_event_indices = [2]
        with patch.object(window, "build_standard_image_timing_context", side_effect=AssertionError("must not reread timestamps")):
            headers, rows, summary = rebuild_temperature_counts(window, context)
        self.assertEqual([row[headers.index("Sample_0 number frozen")] for row in rows], ["0", "0", "1"])
        self.assertEqual([row[1] for row in rows], ["-1.000", "-2.000", "-3.000"])

    def test_backwards_image_timestamps_warn_for_standard_tamu_and_pku(self):
        start = datetime(2026, 1, 1)
        names = [f'2026-01-01-00-00-0{i}-000000.png' for i in (0, 2, 1)]
        window = self.window(names)
        standard = StandardTemperatureTimeseries('/missing.csv', [start, start + timedelta(seconds=2)],
                                                ['2026-01-01', '2026-01-01'], [-1, -3], 2)
        tamu = TAMULinkamTimeseries('/missing.xlsx', start, '2026-01-01', [0, 2], [-1, -3], 1, 2)
        pku = SimpleNamespace(file_path='/missing.iml', start_timestamp=start,
                              timeseries_datetimes=[start, start + timedelta(seconds=2)],
                              timeseries_seconds=[0, 2], temperature_values=[-1, -3],
                              image_records=[SimpleNamespace(timestamp=start + timedelta(seconds=i),
                                                             temperature_value=-10-i) for i in (0, 2, 1)])
        for builder, parsed in ((window.build_standard_freeze_count_timeseries_results, standard),
                                (window.build_tamu_freeze_count_timeseries_results, tamu),
                                (window.build_pku_linksys32_freeze_count_timeseries_results, pku)):
            with self.subTest(builder=builder.__name__):
                headers, rows, summary = builder(parsed)
                self.assertEqual(len(rows), 3)
                self.assertEqual(len(summary['warnings']), 1)
                self.assertIn(names[2], summary['warnings'][0])

    def test_tamu_calibration_survives_json_round_trip(self):
        names = [f"2026-01-01-00-00-0{i}-000000.png" for i in range(3)]
        window = self.window(names)
        parsed = TAMULinkamTimeseries("/missing.xlsx", datetime(2026, 1, 1), "2026-01-01", [0, 2], [-1, -3], 1, 2)
        headers, rows, summary = window.build_tamu_freeze_count_timeseries_results(parsed, {0: (2, 1)})
        context = json.loads(json.dumps(summary["refresh_context"]))
        window.cell_records_by_id[0].freeze_event_indices = [2]
        new_headers, new_rows, _ = rebuild_temperature_counts(window, context)
        column = headers.index("Sample_0 corrected temperature_C")
        self.assertEqual([row[column] for row in rows], [row[column] for row in new_rows])
        self.assertEqual(new_rows[1][new_headers.index("Sample_0 number frozen")], "0")

    def test_pku_retains_image_record_temperatures(self):
        window = self.window()
        start = datetime(2026, 1, 1)
        parsed = SimpleNamespace(file_path="/missing.iml", start_timestamp=start,
                                 timeseries_datetimes=[start, start + timedelta(seconds=2)],
                                 timeseries_seconds=[0, 2], temperature_values=[-1, -3],
                                 image_records=[SimpleNamespace(timestamp=start + timedelta(seconds=i),
                                                               temperature_value=-10-i) for i in range(3)])
        _, _, summary = window.build_pku_linksys32_freeze_count_timeseries_results(parsed)
        window.cell_records_by_id[0].freeze_event_indices = [2]
        _, rows, _ = rebuild_temperature_counts(window, json.loads(json.dumps(summary["refresh_context"])))
        self.assertEqual([row[1] for row in rows], ["-10.000", "-11.000", "-12.000"])
        self.assertEqual(rows[1][-1], "0")

    def test_same_filenames_in_different_recording_do_not_reuse_cached_temperatures(self):
        window = self.window()
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "c.png"})
        window.set_freeze_count_timeseries_results(*window.build_csu_freeze_count_timeseries_results(
            data, count_source=CSU_COUNT_SOURCE_IMAGES))
        window.frame_key = lambda index: f"different-recording/{window.frame_name(index)}"
        self.assertFalse(window.refresh_temperature_counts())
        self.assertFalse(window.freeze_count_timeseries_headers)
        self.assertIn("paths", window.logs[-1])

    def test_failed_refresh_cannot_export_stale_counts_and_can_recover(self):
        window = self.window()
        data = make_data([-1, -2, -3], {0: "a.png", 1: "b.png", 2: "c.png"}, {"Sample_0": [0, 1, 1]})
        window.set_freeze_count_timeseries_results(*window.build_csu_freeze_count_timeseries_results(data))
        window.names.reverse()
        self.assertFalse(window.refresh_temperature_counts())
        self.assertFalse(window.freeze_count_timeseries_headers)
        self.assertIn("refresh_context", window.freeze_count_timeseries_summary)
        self.assertIn("could not update", window.logs[-1])
        window.names.reverse()
        self.assertTrue(window.refresh_temperature_counts())
        self.assertEqual(window.frozen_counts(), ["0", "1", "1"])


if __name__ == "__main__":
    unittest.main()
