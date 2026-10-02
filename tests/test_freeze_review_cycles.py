import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from Icescopy import IceScopy
from icescopy_frame_source import ImageSequenceFrameSource
from icescopy_freeze_cycles import (
    capture_cycle_metadata,
    cycle_ids_for_window,
    cycle_metadata_from_legacy_results,
    normalize_cycle_metadata,
    restore_cycle_metadata,
    set_cycle_metadata,
)
from icescopy_session_io import (
    build_restore_state,
    build_session_payload,
    load_session_bundle,
    save_session_bundle,
)


class CycleMetadataTests(unittest.TestCase):
    def make_window(self, names=("a.png", "b.png", "c.png")):
        source = ImageSequenceFrameSource([f"/frames/{name}" for name in names])
        window = SimpleNamespace(frame_source=source)
        window.active_frame_source = lambda: window.frame_source
        window.frame_count = lambda: window.frame_source.frame_count()
        window.frame_key = lambda index: window.frame_source.frame_key(index)
        window.frame_name = lambda index: window.frame_source.frame_name(index)
        return window

    def test_disabled_or_nonfinite_detection_is_not_cycle_metadata(self):
        window = self.make_window()
        for threshold in (None, "", float("nan"), float("inf"), True):
            with self.subTest(threshold=threshold):
                self.assertEqual(capture_cycle_metadata(window, [0, 0, 0], threshold), {})
        self.assertEqual(capture_cycle_metadata(window, [0, None, 1], 0)["cycle_ids"], [0, None, 1])

    def test_invalid_ids_and_lengths_are_rejected(self):
        window = self.make_window()
        for cycles in ([0, 1], [0, -1, 1], [0, 1.5, 1], [True, 0, 1], [None] * 3):
            with self.subTest(cycles=cycles):
                self.assertEqual(capture_cycle_metadata(window, cycles, 0), {})
        self.assertEqual(normalize_cycle_metadata({"frame_keys": ["a"], "cycle_ids": [0]}), {})

    def test_source_identity_order_and_metadata_replacement_control_cache(self):
        window = self.make_window()
        metadata = capture_cycle_metadata(window, [0, None, 1], 0)
        set_cycle_metadata(window, metadata)
        metadata["cycle_ids"][0] = 9
        with patch.object(window, "frame_key", wraps=window.frame_key) as key:
            self.assertEqual(cycle_ids_for_window(window), (0, None, 1))
            self.assertEqual(cycle_ids_for_window(window), (0, None, 1))
            self.assertEqual(key.call_count, 3)
            window.frame_source = ImageSequenceFrameSource(["/frames/c.png", "/frames/b.png", "/frames/a.png"])
            self.assertEqual(cycle_ids_for_window(window), ())
            self.assertEqual(cycle_ids_for_window(window), ())
            self.assertEqual(key.call_count, 6)
            window.frame_source = ImageSequenceFrameSource(["/frames/a.png", "/frames/b.png", "/frames/c.png"])
            self.assertEqual(cycle_ids_for_window(window), (0, None, 1))
            set_cycle_metadata(window, capture_cycle_metadata(window, [1, 1, 2], 0))
            self.assertEqual(cycle_ids_for_window(window), (1, 1, 2))

    def test_csu_duplicate_picture_names_remain_unknown(self):
        window = self.make_window(("a.png", "a.png", "c.png"))
        metadata = capture_cycle_metadata(window, [0, 1, 2], 0, require_unique_names=True)
        self.assertEqual(metadata["cycle_ids"], [None, None, 2])

    def test_legacy_frame_rows_require_detection_and_exact_order(self):
        window = self.make_window()
        headers = ["cycle", "image_name"]
        rows = [["0", "a.png"], ["", "b.png"], ["1", "c.png"]]
        result = cycle_metadata_from_legacy_results(window, headers, rows, {"reset_temperature": 0})
        self.assertEqual(result["cycle_ids"], [0, None, 1])
        self.assertEqual(cycle_metadata_from_legacy_results(window, headers, rows, {}), {})
        self.assertEqual(cycle_metadata_from_legacy_results(window, headers, rows[::-1], {"reset_temperature": 0}), {})

    def test_legacy_csu_rows_preserve_gaps_and_reject_conflicting_matches(self):
        window = self.make_window()
        headers = ["picture", "cycle"]
        rows = [["a.png", "0"], ["", "1"], ["c.png", "2"]]
        result = cycle_metadata_from_legacy_results(window, headers, rows, {"reset_temperature": 0})
        self.assertEqual(result["cycle_ids"], [0, None, 2])
        self.assertEqual(cycle_metadata_from_legacy_results(window, headers, rows + [["a.png", "1"]], {"reset_temperature": 0}), {})
        self.assertEqual(cycle_metadata_from_legacy_results(self.make_window(("a.png", "a.png")), headers, rows, {"reset_temperature": 0}), {})

    def test_explicit_empty_metadata_never_reactivates_old_cycle_rows(self):
        window = self.make_window()
        restore_cycle_metadata(window, {
            "freeze_review_cycle_metadata": {},
            "freeze_count_timeseries_headers": ["cycle", "image_name"],
            "freeze_count_timeseries_rows": [["0", "a.png"], ["0", "b.png"], ["1", "c.png"]],
            "freeze_count_timeseries_summary": {"reset_temperature": 0},
        })
        self.assertEqual(cycle_ids_for_window(window), ())


class CycleMetadataLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": str(self.root / "config")})
        config.start()
        self.addCleanup(config.stop)
        self.start = datetime(2025, 1, 1, 12)
        self.times = [self.start + timedelta(seconds=index) for index in range(4)]
        self.temperatures = [-1.0, -2.0, 0.5, -2.0]
        self.paths = []
        for timestamp in self.times:
            path = self.root / (timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f") + ".png")
            image = QImage(32, 32, QImage.Format_RGB32)
            image.fill(QColor(100, 100, 100))
            self.assertTrue(image.save(str(path)))
            self.paths.append(path)
        self.window = IceScopy()
        self.addCleanup(self.dispose_window)
        self.window.session_active = True
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.window.populate_image_list()
        self.window.updateImage(0)
        self.cell_id = self.window.cell_controller.add_single_cell((15, 15), (15, 15), 3)
        self.window.ensure_cell_record(self.cell_id).freeze_event_indices = [1, 3]
        self.window.apply_cursor_tool_ui()

    def dispose_window(self):
        self.window.hide()
        self.window.stop_video_preview_decoder()
        self.window.deleteLater()
        self.app.processEvents()

    def install_metadata(self, cycles=(0, 0, 1, 1)):
        set_cycle_metadata(self.window, capture_cycle_metadata(self.window, cycles, 0))

    def parsed_temperature(self):
        return SimpleNamespace(
            file_path="temperature.csv", start_timestamp=self.start,
            start_timestamp_text=self.start.isoformat(), timeseries_datetimes=self.times,
            timeseries_timestamp_texts=[value.isoformat() for value in self.times],
            timeseries_seconds=[0, 1, 2, 3], temperature_values=self.temperatures,
            sample_period_seconds=1, timeseries_row_count=4,
            image_records=[SimpleNamespace(timestamp=t, temperature_value=v) for t, v in zip(self.times, self.temperatures)],
        )

    def test_all_four_import_builders_capture_actual_cycle_assignments(self):
        parsed = self.parsed_temperature()
        csu = {
            "file_path": "temperature.dat", "sample_columns": [],
            "rows": [SimpleNamespace(row_index=index, timestamp_text=t.isoformat(), avg_temp=value,
                                     picture_name=self.paths[index].name, sample_counts={})
                     for index, (t, value) in enumerate(zip(self.times, self.temperatures))],
        }
        builders = (
            lambda threshold: self.window.build_standard_freeze_count_timeseries_results(parsed, reset_temperature=threshold),
            lambda threshold: self.window.build_tamu_freeze_count_timeseries_results(parsed, reset_temperature=threshold),
            lambda threshold: self.window.build_pku_linksys32_freeze_count_timeseries_results(parsed, reset_temperature=threshold),
            lambda threshold: self.window.build_csu_freeze_count_timeseries_results(csu, reset_temperature=threshold),
        )
        for index, builder in enumerate(builders):
            with self.subTest(builder=index):
                headers, rows, summary = builder(0)
                self.window.set_freeze_count_timeseries_results(headers, rows, summary)
                self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
                headers, rows, summary = builder(None)
                self.window.set_freeze_count_timeseries_results(headers, rows, summary)
                self.assertEqual(self.window.freeze_review_cycle_ids(), ())

    def test_flag_edits_undo_redo_and_saved_session_refresh_counts(self):
        headers, rows, summary = self.window.build_standard_freeze_count_timeseries_results(
            self.parsed_temperature(), reset_temperature=0,
        )
        self.window.set_freeze_count_timeseries_results(headers, rows, summary)
        column = headers.index("Unassigned cells number frozen")
        def counts():
            return [row[column] for row in self.window.freeze_count_timeseries_rows]
        self.assertEqual(counts(), ["0", "1", "0", "1"])
        self.window.updateImage(1)
        for item in self.window.scene.items():
            if getattr(item, "cell_id", None) == self.cell_id:
                item.setSelected(True)
        self.assertTrue(self.window.toggle_selected_cells_freeze_at_current_frame())
        self.assertEqual(counts(), ["0", "0", "0", "1"])
        self.window.undo_stack.undo()
        self.assertEqual(counts(), ["0", "1", "0", "1"])
        self.window.undo_stack.redo()
        self.assertEqual(counts(), ["0", "0", "0", "1"])
        self.assertIn("Freeze Count Timeseries updated.", self.window.terminal.toPlainText())
        path = self.root / "refresh.icescopy"
        save_session_bundle(path, build_session_payload(self.window),
                            self.window.grayscale_results_headers, self.window.grayscale_results_rows,
                            self.window.freeze_results_headers, self.window.freeze_results_rows,
                            self.window.freeze_count_timeseries_headers, self.window.freeze_count_timeseries_rows)
        payload, grayscale, freeze, temperatures = load_session_bundle(path)
        self.window.restore_session_state(build_restore_state(self.window, payload, grayscale, freeze, temperatures))
        self.window.apply_manual_freeze_event_indices(self.cell_id, [0, 2])
        self.assertEqual(counts(), ["1", "1", "1", "1"])

    def test_undo_first_manual_event_restores_analysis_required_status(self):
        self.window.ensure_cell_record(self.cell_id).freeze_event_indices = []
        self.window.freeze_results_headers = []
        self.window.freeze_results_rows = []
        self.window.set_freeze_count_timeseries_results(
            *self.window.build_standard_freeze_count_timeseries_results(self.parsed_temperature()))
        self.assertTrue(self.window.freeze_count_timeseries_summary["analysis_required"])
        for item in self.window.scene.items():
            if getattr(item, "cell_id", None) == self.cell_id:
                item.setSelected(True)
        self.assertTrue(self.window.toggle_selected_cells_freeze_at_current_frame())
        self.assertFalse(self.window.freeze_count_timeseries_summary["analysis_required"])
        self.window.undo_stack.undo()
        self.assertTrue(self.window.freeze_count_timeseries_summary["analysis_required"])
        column = self.window.freeze_count_timeseries_headers.index("Unassigned cells number frozen")
        self.assertEqual([row[column] for row in self.window.freeze_count_timeseries_rows], [""] * 4)

    def test_completed_analysis_refreshes_from_new_events_not_previous_records(self):
        self.window.set_freeze_count_timeseries_results(
            *self.window.build_standard_freeze_count_timeseries_results(self.parsed_temperature()))
        self.window.pending_analysis_before_state = None
        self.window.worker = SimpleNamespace(
            freeze_result_headers=["cell", "image_index", "image_name"],
            freeze_result_rows=[[f"cell_{self.cell_id}", "2", self.window.frame_name(2)]],
            grayscale_result_headers=[], grayscale_result_rows=[], deleteLater=lambda: None,
        )
        self.window.onThreadFinished()
        column = self.window.freeze_count_timeseries_headers.index("Unassigned cells number frozen")
        self.assertEqual([row[column] for row in self.window.freeze_count_timeseries_rows], ["0", "0", "1", "1"])
        self.assertIn("Freeze Count Timeseries updated.", self.window.terminal.toPlainText())

    def test_count_invalidation_annotation_undo_and_data_restore_keep_correct_metadata(self):
        self.install_metadata()
        data_state = self.window.capture_data_state()
        annotation_state = self.window.capture_freeze_annotation_state()
        self.window.ensure_cell_record(self.cell_id).freeze_event_indices = [0, 3]
        self.window.invalidate_freeze_count_timeseries_results("freeze frame annotations changed")
        self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
        self.window.restore_freeze_annotation_state(annotation_state)
        self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
        self.install_metadata((0, 1, 2, 3))
        self.window.restore_data_state(data_state)
        self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))

    def test_source_and_order_history_never_reuse_wrong_frame_cycles(self):
        self.install_metadata()
        for capture, restore in ((self.window.capture_image_session_state, self.window.restore_image_session_state),
                                 (self.window.capture_loaded_images_state, self.window.restore_loaded_images_state)):
            before = capture()
            self.window.set_frame_source(ImageSequenceFrameSource(self.paths[::-1]))
            self.assertEqual(self.window.freeze_review_cycle_ids(), ())
            after = capture()
            restore(before)
            self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
            restore(after)
            self.assertEqual(self.window.freeze_review_cycle_ids(), ())
            restore(before)
        self.window.imagePaths = list(map(str, self.paths[::-1]))
        self.window.rebuild_image_sequence_frame_source()
        self.assertEqual(self.window.freeze_review_cycle_ids(), ())

    def test_session_bundle_roundtrip_survives_cleared_count_results(self):
        self.install_metadata()
        self.window.invalidate_freeze_count_timeseries_results("sample assignments changed")
        path = self.root / "cycle_metadata.icescopy"
        save_session_bundle(path, build_session_payload(self.window), [], [], [], [], [], [])
        payload, grayscale, freeze, counts = load_session_bundle(path)
        set_cycle_metadata(self.window, None)
        state = build_restore_state(self.window, payload, grayscale, freeze, counts)
        self.window.restore_session_state(state)
        self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
        self.assertEqual(self.window.freeze_count_timeseries_rows, [])
        self.window.initData()
        self.assertEqual(self.window.freeze_review_cycle_ids(), ())

    def test_legacy_session_recovers_only_explicit_frame_matched_cycle_rows(self):
        payload = build_session_payload(self.window)
        payload.pop("freeze_review_cycle_metadata")
        payload["freeze_count_timeseries_summary"] = {"reset_temperature": 0}
        headers = ["image_name", "cycle"]
        rows = [[path.name, str(index // 2)] for index, path in enumerate(self.paths)]
        state = build_restore_state(self.window, payload, ([], []), ([], []), (headers, rows))
        self.window.restore_session_state(state)
        self.assertEqual(self.window.freeze_review_cycle_ids(), (0, 0, 1, 1))
        payload["freeze_count_timeseries_summary"] = {}
        state = build_restore_state(self.window, payload, ([], []), ([], []), (headers, rows))
        self.window.restore_session_state(state)
        self.assertEqual(self.window.freeze_review_cycle_ids(), ())


if __name__ == "__main__":
    unittest.main()
