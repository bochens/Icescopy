import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import Icescopy as icescopy_module  # noqa: E402
from Icescopy import IceScopy  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit  # noqa: E402
from icescopy_aux import SortImagesDialog  # noqa: E402
from icescopy_temperature_import import (  # noqa: E402
    StandardTemperatureTimeseries,
    TAMULinkamTimeseries,
    TemperatureImportError,
    TIMESTAMP_STYLE_YEAR4_COMPACT,
)
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
from icescopy_session import ImageListModel, SessionAnalysisMarkerCommand, SessionFreezeAnnotationCommand  # noqa: E402


class SessionIoTests(unittest.TestCase):
    def make_action_state_window(self, *, source_kind="image", frame_count=1, video_clip_sorting=False):
        class DummyAction:
            def __init__(self):
                self.enabled = None
                self.text = None

            def setEnabled(self, enabled):
                self.enabled = bool(enabled)

            def setText(self, text):
                self.text = str(text)

        fake_window = SimpleNamespace(
            session_active=True,
            output_state=False,
            image_list_enabled=True,
            grayscale_results_headers=[],
            freeze_results_headers=[],
            freeze_count_timeseries_headers=[],
            viewer_image_count=1,
            has_frames=lambda: frame_count > 0,
            supports_image_file_operations=lambda: source_kind == "image",
            supports_video_clip_sorting=lambda: bool(video_clip_sorting),
            is_video_source=lambda: source_kind == "video",
            set_undo_status=lambda: None,
            set_redo_status=lambda: None,
            update_document_interface_state=lambda: None,
        )
        action_names = (
            "add_source_action",
            "add_images_action",
            "add_folder_action",
            "open_video_action",
            "remove_selected_action",
            "clear_images_action",
            "sort_images_action",
            "relink_images_action",
            "sample_manager_action",
            "new_session_action",
            "open_session_action",
            "save_session_action",
            "save_session_as_action",
            "edit_session_metadata_action",
            "run_analysis_action",
            "output_results_action",
            "import_csu_is_dat_action",
            "import_tamu_linkam_xlsx_action",
            "import_pku_linksys32_iml_action",
            "import_utk_csv_action",
            "import_temperature_csv_action",
            "viewer_single_action",
            "viewer_double_action",
            "viewer_triple_action",
            "viewer_orientation_toggle_action",
            "image_edit_action",
            "undo_action",
            "redo_action",
        )
        for action_name in action_names:
            setattr(fake_window, action_name, DummyAction())
        return fake_window

    def test_update_session_actions_disables_add_source_actions_for_video_source(self):
        fake_window = self.make_action_state_window(source_kind="video", frame_count=5)

        IceScopy.update_session_actions_state(fake_window)

        self.assertFalse(fake_window.add_source_action.enabled)
        self.assertFalse(fake_window.add_images_action.enabled)
        self.assertFalse(fake_window.add_folder_action.enabled)
        self.assertFalse(fake_window.open_video_action.enabled)
        self.assertTrue(fake_window.clear_images_action.enabled)

    def test_update_session_actions_keeps_add_source_actions_enabled_for_image_source(self):
        fake_window = self.make_action_state_window(source_kind="image", frame_count=5)

        IceScopy.update_session_actions_state(fake_window)

        self.assertTrue(fake_window.add_source_action.enabled)
        self.assertTrue(fake_window.add_images_action.enabled)
        self.assertTrue(fake_window.add_folder_action.enabled)
        self.assertFalse(fake_window.open_video_action.enabled)

    def test_update_session_actions_allows_open_video_only_before_source_is_loaded(self):
        fake_window = self.make_action_state_window(source_kind="image", frame_count=0)

        IceScopy.update_session_actions_state(fake_window)

        self.assertTrue(fake_window.add_source_action.enabled)
        self.assertTrue(fake_window.add_images_action.enabled)
        self.assertTrue(fake_window.add_folder_action.enabled)
        self.assertTrue(fake_window.open_video_action.enabled)

    def test_update_session_actions_renames_sort_action_for_sortable_video_clips(self):
        fake_window = self.make_action_state_window(
            source_kind="video",
            frame_count=5,
            video_clip_sorting=True,
        )

        IceScopy.update_session_actions_state(fake_window)

        self.assertTrue(fake_window.sort_images_action.enabled)
        self.assertEqual(fake_window.sort_images_action.text, "Sort Video Clips")

    def test_sort_dialog_uses_video_clip_text_when_sorting_video_source(self):
        app = QApplication.instance() or QApplication([])
        self.addCleanup(lambda: app.processEvents())

        dialog = SortImagesDialog(
            None,
            {"natural_filename": True},
            "natural_filename",
            source_kind_label="video_clips",
        )
        self.addCleanup(dialog.close)

        label_texts = [
            child.text()
            for child in dialog.findChildren(QLabel)
            if child.text()
        ]
        self.assertEqual(dialog.windowTitle(), "Sort Video Clips")
        self.assertIn(
            "Sort loaded video clips or choose the default ordering for new video clips.",
            label_texts,
        )

    def test_source_backed_image_list_model_can_filter_to_frozen_source_frames(self):
        app = QApplication.instance() or QApplication([])
        self.addCleanup(lambda: app.processEvents())

        fake_window = SimpleNamespace(
            frame_count=lambda: 8,
            frame_list_row_count=lambda: 2,
            frame_list_source_index_for_row=lambda row: [2, 5][row] if row in (0, 1) else None,
            format_frame_list_entry=lambda source_index: f"frame {source_index}",
            frame_tooltip=lambda source_index: f"tooltip {source_index}",
        )
        model = ImageListModel()
        model.main_window = fake_window

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.data(model.index(0, 0)), "frame 2")
        self.assertEqual(model.data(model.index(1, 0)), "frame 5")
        self.assertEqual(model.data(model.index(1, 0), Qt.ToolTipRole), "tooltip 5")

    def test_load_video_refuses_to_replace_existing_image_source(self):
        fake_window = SimpleNamespace(
            has_frames=lambda: True,
        )

        with patch.object(icescopy_module.QMessageBox, "information") as information:
            IceScopy.load_video(fake_window, "/tmp/example.mp4")

        information.assert_called_once()

    def test_grid_scroll_shortcut_labels_match_platform_modifier_handlers(self):
        fake_window = SimpleNamespace()

        with patch.object(icescopy_module, "IS_MACOS", True), patch.object(icescopy_module, "IS_WINDOWS", False):
            self.assertEqual(IceScopy.grid_horizontal_pitch_shortcut_label(fake_window), "Option scroll")
            self.assertEqual(IceScopy.grid_vertical_pitch_shortcut_label(fake_window), "Command scroll")
            self.assertEqual(IceScopy.grid_tilt_shortcut_label(fake_window), "Control scroll")

        with patch.object(icescopy_module, "IS_MACOS", False), patch.object(icescopy_module, "IS_WINDOWS", True):
            self.assertEqual(IceScopy.grid_horizontal_pitch_shortcut_label(fake_window), "Caps Lock scroll")
            self.assertEqual(IceScopy.grid_vertical_pitch_shortcut_label(fake_window), "Ctrl scroll")
            self.assertEqual(IceScopy.grid_tilt_shortcut_label(fake_window), "Shift scroll")

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
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
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
                has_frames=lambda: True,
                is_video_source=lambda: False,
                last_temperature_import_path="/tmp/sample.iml",
                last_temperature_reset_temperature=None,
                last_temperature_blank_sample_names=[],
                available_sample_choices=lambda: [
                    {
                        "sample_id": "1",
                        "sample_name": "Sample A",
                        "label": "Sample A",
                    }
                ],
            )

            IceScopy.import_pku_linksys32_iml(fake_window)
        finally:
            icescopy_module.PKUTemperatureImportDialog = original_dialog

        self.assertEqual(captured_kwargs["main_window"], fake_window)
        self.assertEqual(
            captured_kwargs["sample_names"],
            [{"sample_id": "1", "sample_name": "Sample A", "label": "Sample A"}],
        )
        self.assertEqual(captured_kwargs["initial_blank_sample_names"], [])
        self.assertEqual(captured_kwargs["parent"], fake_window)
        self.assertNotIn("initial_calibration_path", captured_kwargs)

    def test_update_results_tables_refreshes_selected_cursor_freeze_frame_text(self):
        self._qt_app = QApplication.instance() or QApplication([])

        class DummyWidget:
            def __init__(self):
                self.visible = None
                self.enabled = None

            def setVisible(self, visible):
                self.visible = bool(visible)

            def setEnabled(self, enabled):
                self.enabled = bool(enabled)

        record = SimpleNamespace(freeze_event_indices=[1])
        line_edit = QLineEdit()
        line_edit.setText("1")
        row_widget = DummyWidget()
        apply_button = DummyWidget()

        fake_window = SimpleNamespace(
            data_table=object(),
            freeze_table=object(),
            grayscale_results_headers=[],
            grayscale_results_rows=[],
            freeze_results_headers=["cell", "image_index", "image_name"],
            freeze_results_rows=[["cell_0", "9", "frame_009.png"]],
            cursor_freeze_lineedit=line_edit,
            cursor_freeze_row=row_widget,
            cursor_freeze_apply_button=apply_button,
            cursor_sample_combo=object(),
            cursor_edit_section_label=DummyWidget(),
            cursor_info_edit_separator=DummyWidget(),
            cursor_sample_row=DummyWidget(),
            cursor_sample_button_row=DummyWidget(),
        )
        fake_window.get_selected_cell_items = lambda: [SimpleNamespace(cell_id=0)]
        fake_window.ensure_cell_record = lambda cell_id: record
        fake_window.format_integer_list_csv = lambda values: IceScopy.format_integer_list_csv(fake_window, values)
        fake_window.sync_cell_analysis_from_results = (
            lambda: setattr(record, "freeze_event_indices", [9])
        )
        fake_window.set_table_data = lambda *_args, **_kwargs: None
        fake_window.update_results_table_visibility = lambda: None
        fake_window.refresh_freeze_flag_markers = lambda: None
        fake_window.refresh_grayscale_plot = lambda: None
        fake_window.refresh_cells_panel = lambda: None
        fake_window.update_cursor_record_edit_state = (
            lambda: IceScopy.update_cursor_record_edit_state(fake_window)
        )

        IceScopy.update_results_tables(fake_window)

        self.assertEqual(line_edit.text(), "9")
        self.assertTrue(row_widget.visible)
        self.assertTrue(line_edit.isEnabled())
        self.assertTrue(apply_button.enabled)

    def test_flag_button_toggles_current_frame_for_selected_cells(self):
        records = {
            0: SimpleNamespace(freeze_event_indices=[]),
            1: SimpleNamespace(freeze_event_indices=[2]),
        }
        selected_items = [
            SimpleNamespace(cell_id=0),
            SimpleNamespace(cell_id=1),
        ]

        fake_window = SimpleNamespace(
            image_index=2,
            grayscale_results_rows=[],
            freeze_results_headers=[],
            freeze_results_rows=[["cell_1", "2", "frame_002.png"]],
            last_freeze_output_path=None,
            changed_reason=None,
            result_updates=0,
            freeze_view_refreshes=0,
            fast_freeze_view_refreshes=0,
            cursor_refreshes=0,
            marker_refreshes=0,
            pushed_history=None,
            logged_messages=[],
        )
        fake_window.get_selected_cell_items = lambda: selected_items
        fake_window.has_frames = lambda: True
        fake_window.frame_count = lambda: 10
        fake_window.frame_name = lambda index: f"frame_{index:03d}.png"
        fake_window.ensure_cell_record = lambda cell_id: records[int(cell_id)]
        fake_window.rebuild_freeze_rows_for_cell = (
            lambda cell_id, values: IceScopy.rebuild_freeze_rows_for_cell(fake_window, cell_id, values)
        )
        fake_window.selected_cells_freeze_state_at_current_frame = (
            lambda selected_items=None: IceScopy.selected_cells_freeze_state_at_current_frame(
                fake_window,
                selected_items,
            )
        )
        fake_window.apply_manual_freeze_event_indices = (
            lambda cell_id, values, refresh_tables=True, refresh_freeze_markers=True, refresh_freeze_count_table=True:
            IceScopy.apply_manual_freeze_event_indices(
                fake_window,
                cell_id,
                values,
                refresh_tables=refresh_tables,
                refresh_freeze_markers=refresh_freeze_markers,
                refresh_freeze_count_table=refresh_freeze_count_table,
            )
        )
        fake_window.apply_manual_freeze_event_indices_batch = (
            lambda values_by_cell_id, refresh_tables=True, refresh_freeze_markers=True, refresh_freeze_count_table=True:
            IceScopy.apply_manual_freeze_event_indices_batch(
                fake_window,
                values_by_cell_id,
                refresh_tables=refresh_tables,
                refresh_freeze_markers=refresh_freeze_markers,
                refresh_freeze_count_table=refresh_freeze_count_table,
            )
        )
        fake_window.extract_cell_id_from_label = lambda label: int(str(label).split("_", 1)[1])
        fake_window.invalidate_freeze_count_timeseries_results = (
            lambda reason=None, refresh_table=True: setattr(fake_window, "changed_reason", reason)
        )
        fake_window.update_results_tables = (
            lambda: setattr(fake_window, "result_updates", fake_window.result_updates + 1)
        )
        fake_window.refresh_freeze_annotation_views = (
            lambda selected_items=None: setattr(fake_window, "freeze_view_refreshes", fake_window.freeze_view_refreshes + 1)
        )
        fake_window.refresh_freeze_annotation_views_fast = (
            lambda changed_cell_ids, **_kwargs: setattr(fake_window, "fast_freeze_view_refreshes", fake_window.fast_freeze_view_refreshes + 1)
        )
        fake_window.refresh_cursor_selection_info = (
            lambda selected_items=None: setattr(fake_window, "cursor_refreshes", fake_window.cursor_refreshes + 1)
        )
        fake_window.refresh_freeze_flag_markers = (
            lambda selected_items=None: setattr(fake_window, "marker_refreshes", fake_window.marker_refreshes + 1)
        )
        fake_window.capture_data_state = lambda: self.fail("flag toggle should not capture full data state")
        fake_window.push_data_history = (
            lambda text, before_state: self.fail("flag toggle should not push full data history")
        )
        fake_window.capture_freeze_annotation_state = lambda: {"before": True}
        fake_window.push_freeze_annotation_history = (
            lambda text, before_state: setattr(fake_window, "pushed_history", (text, before_state))
        )
        fake_window.summarize_integer_list = lambda values: IceScopy.summarize_integer_list(fake_window, values)
        fake_window.log = lambda message: fake_window.logged_messages.append(message)

        self.assertTrue(IceScopy.toggle_selected_cells_freeze_at_current_frame(fake_window))
        self.assertEqual(records[0].freeze_event_indices, [2])
        self.assertEqual(records[1].freeze_event_indices, [2])
        self.assertEqual(fake_window.freeze_results_rows, [["cell_0", "2", "frame_002.png"], ["cell_1", "2", "frame_002.png"]])
        self.assertEqual(fake_window.pushed_history[0], "Mark Freeze Frame")
        self.assertEqual(fake_window.result_updates, 0)
        self.assertEqual(fake_window.freeze_view_refreshes, 0)
        self.assertEqual(fake_window.fast_freeze_view_refreshes, 1)

        self.assertTrue(IceScopy.toggle_selected_cells_freeze_at_current_frame(fake_window))
        self.assertEqual(records[0].freeze_event_indices, [])
        self.assertEqual(records[1].freeze_event_indices, [])
        self.assertEqual(fake_window.freeze_results_rows, [])
        self.assertEqual(fake_window.pushed_history[0], "Clear Freeze Frame")
        self.assertEqual(fake_window.result_updates, 0)
        self.assertEqual(fake_window.freeze_view_refreshes, 0)
        self.assertEqual(fake_window.fast_freeze_view_refreshes, 2)

    def test_freeze_annotation_command_undo_redo_uses_restore_states(self):
        fake_window = SimpleNamespace(restored_states=[])
        fake_window.restore_freeze_annotation_state = (
            lambda state, preserve_active_tool=False:
            fake_window.restored_states.append((state, preserve_active_tool))
        )
        before_state = {"freeze": "before"}
        after_state = {"freeze": "after"}

        command = SessionFreezeAnnotationCommand(
            fake_window,
            "Toggle Freeze Frame",
            before_state,
            after_state,
        )
        command.redo()
        self.assertEqual(fake_window.restored_states, [])

        command.undo()
        command.redo()
        self.assertEqual(
            fake_window.restored_states,
            [(before_state, True), (after_state, True)],
        )

    def test_restore_freeze_annotation_state_uses_fast_row_and_marker_updates(self):
        before_payload = {
            "0": {
                "cell_id": 0,
                "sample_id": "",
                "grayscale_timeseries": [],
                "freeze_event_indices": [2],
                "freeze_rows": [["cell_0", "2", "frame_002.png"]],
            }
        }
        after_payload = {
            "0": {
                "cell_id": 0,
                "sample_id": "",
                "grayscale_timeseries": [],
                "freeze_event_indices": [],
                "freeze_rows": [],
            }
        }
        state = {
            "cell_records_by_id": after_payload,
            "freeze_results_headers": ["cell", "image_index", "image_name"],
            "freeze_results_rows": [],
            "last_freeze_output_path": None,
            "flagframe_list": [],
            "tool_mode": "cursor",
        }
        fake_window = SimpleNamespace(
            current_payload=before_payload,
            cell_records_by_id={},
            freeze_results_headers=["cell", "image_index", "image_name"],
            freeze_results_rows=[["cell_0", "2", "frame_002.png"]],
            freeze_count_timeseries_headers=["timestamp"],
            freeze_count_timeseries_rows=[["2026-01-01"]],
            freeze_count_timeseries_summary={"existing": True},
            last_temperature_import_path="/tmp/temp.csv",
            flagframe_list=[2],
            row_updates=[],
            marker_updates=[],
            cleared_freeze_count_tables=0,
            visibility_updates=0,
            cursor_refreshes=0,
            edit_state_updates=0,
            session_action_updates=0,
            undo_status_updates=0,
            redo_status_updates=0,
        )
        fake_window.serialize_cell_records = lambda: fake_window.current_payload
        fake_window.deserialize_cell_records = lambda payload: payload
        fake_window.get_active_tool_for_restore = lambda: "cursor"
        fake_window.freeze_annotation_changed_cell_ids = (
            lambda before, after: IceScopy.freeze_annotation_changed_cell_ids(fake_window, before, after)
        )
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.recompute_next_cell_id = lambda preserve_if_larger=True: None
        fake_window.ensure_sample_catalog_matches_cell_records = lambda: None
        fake_window.replace_freeze_table_rows_for_cells = lambda cell_ids: fake_window.row_updates.append(list(cell_ids))
        fake_window.set_table_data = lambda *_args, **_kwargs: self.fail("freeze restore should not rebuild the whole freeze table")
        fake_window.clear_freeze_count_timeseries_table_widget = (
            lambda: setattr(fake_window, "cleared_freeze_count_tables", fake_window.cleared_freeze_count_tables + 1)
        )
        fake_window.update_results_table_visibility = (
            lambda: setattr(fake_window, "visibility_updates", fake_window.visibility_updates + 1)
        )
        fake_window.selected_cell_freeze_frames = lambda selected_items=None: []
        fake_window.set_freeze_flag_marker_fast = (
            lambda frame_index, is_flagged: fake_window.marker_updates.append((frame_index, is_flagged))
        )
        fake_window.refresh_freeze_flag_markers = (
            lambda selected_items=None: self.fail("freeze restore should not refresh all flag markers")
        )
        fake_window.refresh_cursor_selection_info = (
            lambda selected_items=None: setattr(fake_window, "cursor_refreshes", fake_window.cursor_refreshes + 1)
        )
        fake_window.update_cursor_record_edit_state = (
            lambda selected_items=None: setattr(fake_window, "edit_state_updates", fake_window.edit_state_updates + 1)
        )
        fake_window.update_session_actions_state = (
            lambda: setattr(fake_window, "session_action_updates", fake_window.session_action_updates + 1)
        )
        fake_window.restore_tool_mode_ui = lambda *_args, **_kwargs: self.fail("preserved-tool undo should not restore the tool UI")
        fake_window.set_undo_status = (
            lambda: setattr(fake_window, "undo_status_updates", fake_window.undo_status_updates + 1)
        )
        fake_window.set_redo_status = (
            lambda: setattr(fake_window, "redo_status_updates", fake_window.redo_status_updates + 1)
        )

        IceScopy.restore_freeze_annotation_state(fake_window, state, preserve_active_tool=True)

        self.assertEqual(fake_window.row_updates, [[0]])
        self.assertEqual(fake_window.marker_updates, [(2, False)])
        self.assertEqual(fake_window.freeze_count_timeseries_headers, [])
        self.assertEqual(fake_window.freeze_count_timeseries_rows, [])
        self.assertEqual(fake_window.freeze_count_timeseries_summary, {})
        self.assertIsNone(fake_window.last_temperature_import_path)
        self.assertEqual(fake_window.cleared_freeze_count_tables, 1)

    def test_no_selection_freeze_markers_show_all_cell_freeze_frames(self):
        fake_window = SimpleNamespace(
            cell_controller=object(),
            scene=object(),
            image_index=5,
            cell_records_by_id={
                0: SimpleNamespace(freeze_event_indices=[1, 5]),
                1: SimpleNamespace(freeze_event_indices=[5, 7]),
                2: SimpleNamespace(freeze_event_indices=[7, 20, "bad"]),
            },
        )
        fake_window.get_selected_cell_items = lambda: []
        fake_window.has_frames = lambda: True
        fake_window.frame_count = lambda: 10

        self.assertEqual(IceScopy.selected_cell_freeze_frames(fake_window), [1, 5, 7])
        self.assertEqual(
            IceScopy.selected_cells_freeze_state_at_current_frame(fake_window),
            (True, False),
        )

    def test_analysis_start_marker_toggle_uses_single_marker_history(self):
        class DummySlider:
            def __init__(self):
                self.analysis_startframes = set()
                self.analysis_endframes = set()
                self.marker_updates = []

            def set_analysis_marker(self, marker_kind, frame_index, is_marked):
                self.marker_updates.append((marker_kind, frame_index, is_marked))
                marker_frames = self.analysis_startframes if marker_kind == "start" else self.analysis_endframes
                if is_marked:
                    marker_frames.add(frame_index)
                else:
                    marker_frames.discard(frame_index)

        fake_window = SimpleNamespace(
            image_index=12,
            analysis_start_frame_list=[],
            analysis_end_frame_list=[],
            image_slider=DummySlider(),
            updated_rows=[],
            start_icon_updates=0,
            end_icon_updates=0,
            session_action_updates=0,
            history_pushes=[],
            logged_messages=[],
        )
        fake_window.has_frames = lambda: True
        fake_window.frame_count = lambda: 100
        fake_window.analysis_marker_list_attr = (
            lambda marker_kind: IceScopy.analysis_marker_list_attr(fake_window, marker_kind)
        )
        fake_window.set_analysis_window_marker = (
            lambda marker_kind, frame_index, is_marked:
            IceScopy.set_analysis_window_marker(fake_window, marker_kind, frame_index, is_marked)
        )
        fake_window.update_image_list_annotations = lambda rows=None: fake_window.updated_rows.append(list(rows or []))
        fake_window.update_toggle_analysis_start_button_icon = (
            lambda: setattr(fake_window, "start_icon_updates", fake_window.start_icon_updates + 1)
        )
        fake_window.update_toggle_analysis_end_button_icon = (
            lambda: setattr(fake_window, "end_icon_updates", fake_window.end_icon_updates + 1)
        )
        fake_window.update_session_actions_state = (
            lambda: setattr(fake_window, "session_action_updates", fake_window.session_action_updates + 1)
        )
        fake_window.push_analysis_marker_history = (
            lambda *args: fake_window.history_pushes.append(args)
        )
        fake_window.push_timeline_marker_history = (
            lambda *_args: self.fail("analysis start/end markers should not use full timeline history")
        )
        fake_window.capture_timeline_marker_state = (
            lambda: self.fail("analysis start/end markers should not capture full timeline state")
        )
        fake_window.log = lambda message: fake_window.logged_messages.append(message)

        self.assertTrue(IceScopy.toggle_analysis_window_marker(fake_window, "start"))
        self.assertEqual(fake_window.analysis_start_frame_list, [12])
        self.assertEqual(fake_window.image_slider.analysis_startframes, {12})
        self.assertEqual(fake_window.updated_rows, [[12]])
        self.assertEqual(fake_window.image_slider.marker_updates, [("start", 12, True)])
        self.assertEqual(
            fake_window.history_pushes[-1],
            ("Toggle Analysis Start", "start", 12, False, True),
        )

        self.assertTrue(IceScopy.toggle_analysis_window_marker(fake_window, "start"))
        self.assertEqual(fake_window.analysis_start_frame_list, [])
        self.assertEqual(fake_window.image_slider.analysis_startframes, set())
        self.assertEqual(fake_window.image_slider.marker_updates[-1], ("start", 12, False))
        self.assertEqual(
            fake_window.history_pushes[-1],
            ("Toggle Analysis Start", "start", 12, True, False),
        )

    def test_analysis_marker_command_undo_redo_uses_single_marker_restore(self):
        fake_window = SimpleNamespace(restored_markers=[])
        fake_window.restore_analysis_marker_state = (
            lambda marker_kind, frame_index, is_marked, preserve_active_tool=False:
            fake_window.restored_markers.append((marker_kind, frame_index, is_marked, preserve_active_tool))
        )

        command = SessionAnalysisMarkerCommand(
            fake_window,
            "Toggle Analysis Start",
            "start",
            12,
            False,
            True,
        )
        command.redo()
        self.assertEqual(fake_window.restored_markers, [])

        command.undo()
        command.redo()
        self.assertEqual(
            fake_window.restored_markers,
            [("start", 12, False, True), ("start", 12, True, True)],
        )

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
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
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

        _matched_samples, blank_samples, output_samples, unmatched_blank_samples = (
            IceScopy.build_freeze_count_timeseries_blank_selection(
                fake_window,
                groups,
                blank_sample_names=["1"],
            )
        )
        self.assertEqual([sample["sample_id"] for sample in blank_samples], ["1"])
        self.assertEqual([sample["sample_id"] for sample in output_samples], ["2"])
        self.assertEqual(unmatched_blank_samples, [])

    def test_standard_import_rejects_zero_interpolated_frames(self):
        fake_window = SimpleNamespace(
            imageNames=["20260101_000000.png"],
            imagePaths=["/tmp/20260101_000000.png"],
            cell_records_by_id={},
            temperature_cycle_warmup_hysteresis_c=0.02,
        )
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
        fake_window.is_video_source = lambda: False
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.build_tamu_freeze_count_timeseries_sample_groups = (
            lambda: IceScopy.build_tamu_freeze_count_timeseries_sample_groups(fake_window)
        )
        fake_window.build_freeze_count_timeseries_sample_groups = (
            lambda grouping_mode="samples": IceScopy.build_freeze_count_timeseries_sample_groups(
                fake_window,
                grouping_mode=grouping_mode,
            )
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
        fake_window.cycle_index_for_position = (
            lambda position_value, cycle_start_positions: IceScopy.cycle_index_for_position(
                fake_window,
                position_value,
                cycle_start_positions,
            )
        )
        fake_window.build_standard_image_timing_context = (
            lambda parsed_timeseries, **kwargs: IceScopy.build_standard_image_timing_context(
                fake_window,
                parsed_timeseries,
                **kwargs,
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
        parsed_timeseries = StandardTemperatureTimeseries(
            file_path="/tmp/temperature.csv",
            timeseries_datetimes=[
                datetime(2026, 1, 2, 0, 0, 0),
                datetime(2026, 1, 2, 0, 1, 0),
            ],
            timeseries_timestamp_texts=[
                "2026-01-02 00:00:00",
                "2026-01-02 00:01:00",
            ],
            temperature_values=[-5.0, -6.0],
            timeseries_row_count=2,
        )

        with self.assertRaises(TemperatureImportError):
            IceScopy.build_standard_freeze_count_timeseries_results(
                fake_window,
                parsed_timeseries,
                image_timestamp_style=TIMESTAMP_STYLE_YEAR4_COMPACT,
            )

    def test_tamu_import_rejects_zero_interpolated_images(self):
        fake_window = SimpleNamespace(
            imageNames=["2026-01-01-00-00-00-000000.png"],
            imagePaths=["/tmp/2026-01-01-00-00-00-000000.png"],
            cell_records_by_id={},
            temperature_cycle_warmup_hysteresis_c=0.02,
            last_temperature_calibration_path="",
        )
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.build_tamu_freeze_count_timeseries_sample_groups = (
            lambda: IceScopy.build_tamu_freeze_count_timeseries_sample_groups(fake_window)
        )
        fake_window.build_freeze_count_timeseries_sample_groups = (
            lambda grouping_mode="samples": IceScopy.build_freeze_count_timeseries_sample_groups(
                fake_window,
                grouping_mode=grouping_mode,
            )
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
        fake_window.cycle_index_for_position = (
            lambda position_value, cycle_start_positions: IceScopy.cycle_index_for_position(
                fake_window,
                position_value,
                cycle_start_positions,
            )
        )
        fake_window.build_tamu_image_timing_context = (
            lambda parsed_timeseries, reset_temperature=None: IceScopy.build_tamu_image_timing_context(
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
        parsed_timeseries = TAMULinkamTimeseries(
            file_path="/tmp/tamu.xlsx",
            start_timestamp=datetime(2026, 1, 2, 0, 0, 0),
            start_timestamp_text="2026-01-02 00:00:00",
            timeseries_seconds=[0.0, 60.0],
            temperature_values=[-5.0, -6.0],
            sample_period_seconds=60.0,
            timeseries_row_count=2,
        )

        with self.assertRaises(TemperatureImportError):
            IceScopy.build_tamu_freeze_count_timeseries_results(
                fake_window,
                parsed_timeseries,
            )

    def test_freeze_count_timeseries_grouping_combines_unassigned_cells(self):
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
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)
        fake_window.sample_record_for_id = lambda sample_id: fake_window.sample_catalog[int(sample_id)]

        groups = IceScopy.build_freeze_count_timeseries_sample_groups(fake_window, grouping_mode="samples")

        self.assertEqual(sorted(groups.keys()), ["1", "__unassigned_cells__"])
        self.assertEqual(groups["1"]["sample_name"], "Sample_1")
        self.assertEqual(groups["1"]["cell_ids"], [10])
        self.assertEqual(groups["__unassigned_cells__"]["sample_id"], "")
        self.assertEqual(groups["__unassigned_cells__"]["sample_name"], "Unassigned cells")
        self.assertEqual(groups["__unassigned_cells__"]["cell_ids"], [11, 12])
        self.assertEqual(groups["__unassigned_cells__"]["total_cells"], 2)

        matched_samples, _blank_samples, output_samples, _unmatched_blank_samples = (
            IceScopy.build_freeze_count_timeseries_blank_selection(fake_window, groups)
        )
        self.assertEqual(
            [sample["sample_name"] for sample in output_samples],
            ["Sample_1", "Unassigned cells"],
        )
        self.assertEqual(
            [sample["group_key"] for sample in matched_samples],
            ["1", "__unassigned_cells__"],
        )

        metadata = IceScopy.build_freeze_count_timeseries_sample_column_metadata(
            fake_window,
            groups["__unassigned_cells__"],
        )
        self.assertEqual(metadata["sample_id"], "")
        self.assertEqual(metadata["sample_name"], "Unassigned cells")
        self.assertEqual(metadata["cell_number"], "2")

    def test_freeze_count_timeseries_grouping_treats_no_sample_as_all_cells(self):
        fake_window = SimpleNamespace(
            cell_records_by_id={
                0: SimpleNamespace(sample_id=""),
                1: SimpleNamespace(sample_id=None),
                2: SimpleNamespace(sample_id=""),
            },
            sample_catalog={},
        )
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.ensure_cell_record = lambda cell_id: fake_window.cell_records_by_id.get(cell_id)

        groups = IceScopy.build_freeze_count_timeseries_sample_groups(fake_window, grouping_mode="samples")

        self.assertEqual(list(groups.keys()), ["__unassigned_cells__"])
        self.assertEqual(groups["__unassigned_cells__"]["sample_name"], "All cells")
        self.assertEqual(groups["__unassigned_cells__"]["cell_ids"], [0, 1, 2])
        self.assertEqual(groups["__unassigned_cells__"]["total_cells"], 3)

    def test_pku_linksys32_import_outputs_unassigned_cells_as_one_group(self):
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
                "Unassigned cells number total",
                "Unassigned cells number frozen",
            ],
        )
        self.assertEqual(rows[0][5:], ["1", "0", "1", "1"])
        self.assertEqual(rows[1][5:], ["1", "1", "1", "1"])
        self.assertEqual(summary["matched_samples"], ["Sample_1", "Unassigned cells"])
        self.assertEqual(
            [metadata["sample_name"] for metadata in summary["sample_column_metadata"]],
            ["Sample_1", "Unassigned cells"],
        )
        self.assertEqual(summary["sample_column_metadata"][1]["sample_id"], "")
        self.assertEqual(summary["sample_column_metadata"][1]["cell_number"], "1")

    def test_csu_import_outputs_unassigned_cells_as_one_group(self):
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
        fake_window.frame_count = lambda: len(fake_window.imageNames)
        fake_window.frame_name = lambda index: fake_window.imageNames[int(index)]
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
                "Unassigned cells number total",
                "Unassigned cells number frozen",
            ],
        )
        self.assertEqual(rows[0][5:], ["1", "0", "1", "1"])
        self.assertEqual(rows[1][5:], ["1", "1", "1", "1"])
        self.assertEqual(summary["matched_samples"], ["Sample_1", "Unassigned cells"])
        self.assertEqual(summary["unmatched_app_samples"], [])
        self.assertEqual(
            [metadata["sample_name"] for metadata in summary["sample_column_metadata"]],
            ["Sample_1", "Unassigned cells"],
        )

    def test_missing_metadata_report_lists_session_and_sample_gaps(self):
        fake_window = SimpleNamespace(
            serialize_session_metadata=lambda: {
                "project_name": "",
                "user_name": "User",
                "institution": "",
                "date": "2026-04-22",
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
                        "well_volume_uL": "",
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
        self.assertIn(
            "- Sample 1 (Sample A): sample_long_name, sampling_site, collection_start, collection_end, well_volume_uL, dilution, air_volume_L, suspension_volume_mL, dry_mass_g",
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
                        "well_volume_uL": "50",
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
        self.assertNotIn("# well_volume_uL: 50\n", csv_text)
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
        self.assertIn("# well_volume_uL,50\n", csv_text)
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
                        "well_volume_uL": "",
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
        self.assertNotIn("# well_volume_uL: nan\n", csv_text)
        self.assertIn("# reset_temperature_C: nan\n", csv_text)
        self.assertNotIn("# exported_at:", csv_text)
        self.assertIn("# cell_number,nan\n", csv_text)
        self.assertIn("# sample_long_name,nan\n", csv_text)
        self.assertIn("# sampling_site,nan\n", csv_text)
        self.assertIn("# collection_start,nan\n", csv_text)
        self.assertIn("# collection_end,nan\n", csv_text)
        self.assertIn("# well_volume_uL,nan\n", csv_text)
        self.assertIn("# air_volume_L,nan\n", csv_text)

    def test_build_session_payload_stores_current_tool_settings(self):
        fake_window = SimpleNamespace(
            serialize_session_metadata=lambda: {},
            serialize_image_edit_state=lambda: {},
            frame_source_session_payload=lambda: {
                "kind": "image_sequence",
                "image_paths": ["/tmp/example.png"],
            },
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
            payload["frame_source"],
            {
                "kind": "image_sequence",
                "image_paths": ["/tmp/example.png"],
            },
        )
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
        self.assertEqual(
            state["frame_source"],
            {
                "kind": "image_sequence",
                "image_paths": ["/tmp/example.png"],
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
            },
            "sample_catalog": {
                "1": {
                    "sample_name": "Sample A",
                    "sample_long_name": "Long A",
                    "sampling_site": "Storm Peak Laboratory",
                    "collection_start": "2026-04-22T12:00:00",
                    "collection_end": "2026-04-22T18:00:00",
                    "sample_type": "air",
                    "well_volume_uL": "50",
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
                        "well_volume_uL": "50",
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

    def test_clear_loaded_images_keeps_cell_catalog_state(self):
        class DummyScene:
            def __init__(self):
                self.cleared = False

            def clear(self):
                self.cleared = True

        class DummyLabel:
            def clear(self):
                pass

        class DummySlider:
            def blockSignals(self, _blocked):
                pass

            def setMinimum(self, _value):
                pass

            def setMaximum(self, _value):
                pass

            def setValue(self, _value):
                pass

            def setEnabled(self, _enabled):
                pass

            def clear_marker_state(self):
                pass

        class DummyAction:
            def __init__(self):
                self.triggered = False

            def setEnabled(self, _enabled):
                pass

            def trigger(self):
                self.triggered = True

        cell_items = [
            SimpleNamespace(cell_id=0, circle_pixel_positions=(10, 20)),
            SimpleNamespace(cell_id=1, circle_pixel_positions=(30, 40)),
        ]
        serialized_records = {
            "0": {"cell_id": 0, "sample_id": "5"},
            "1": {"cell_id": 1, "sample_id": ""},
        }
        fake_window = SimpleNamespace(
            imagePaths=["a.png", "b.png"],
            imageNames=["a.png", "b.png"],
            image_index=1,
            last_committed_image_index=1,
            image_list_entry_ids=[0, 1],
            next_image_list_entry_id=2,
            cell_items=cell_items,
            rendered_cell_items=list(cell_items),
            next_cell_id=2,
            cell_records_by_id=dict(serialized_records),
            keyframe_list=[0],
            flagframe_list=[1],
            keyframe_cell_items_dict={0: [cell_items[0]]},
            image_width=100,
            scene=DummyScene(),
            image_name_label=DummyLabel(),
            image_textbox=DummyLabel(),
            image_slider=DummySlider(),
            select_tool_action=DummyAction(),
            grid_tool_action=DummyAction(),
            pan_tool_action=DummyAction(),
            deselect_tool_action=DummyAction(),
            edit_tool_action=DummyAction(),
            reset_cursor_action=DummyAction(),
            history_pushed=False,
            logged_message=None,
            no_image_redraw_fit_view=None,
        )
        fake_window.capture_image_session_state = lambda: {}
        fake_window.has_frames = lambda: bool(fake_window.imagePaths)
        fake_window.serialize_cell_records = lambda: dict(serialized_records)
        fake_window.deserialize_cell_records = lambda payload: dict(payload)
        fake_window.reset_transient_interaction_state = lambda: None
        fake_window.reset_pending_frame_navigation_state = lambda stop_timer=True: None
        fake_window.clear_image_caches = lambda: None
        fake_window.ensure_cell_registry_matches_scene_cells = lambda: None
        fake_window.recompute_next_cell_id = lambda preserve_if_larger=True: None
        fake_window.update_session_actions_state = lambda: None
        fake_window.updateButtonStates = lambda: None
        fake_window.invalidate_analysis_results = lambda reason=None: None
        fake_window.populate_image_list = lambda: None
        fake_window.redraw_no_image_cell_template_view = (
            lambda fit_view=False: setattr(fake_window, "no_image_redraw_fit_view", fit_view)
        )
        fake_window.log = lambda message: setattr(fake_window, "logged_message", message)
        fake_window.push_image_session_history = (
            lambda text, before_state: setattr(fake_window, "history_pushed", (text, before_state))
        )

        IceScopy.clear_loaded_images(fake_window, confirm=False)

        self.assertTrue(fake_window.scene.cleared)
        self.assertEqual([item.cell_id for item in fake_window.cell_items], [0, 1])
        self.assertIsNot(fake_window.cell_items[0], cell_items[0])
        self.assertEqual(fake_window.next_cell_id, 2)
        self.assertEqual(fake_window.cell_records_by_id, serialized_records)
        self.assertEqual(fake_window.keyframe_list, [])
        self.assertEqual(fake_window.flagframe_list, [])
        self.assertEqual(fake_window.keyframe_cell_items_dict, {})
        self.assertEqual(fake_window.imagePaths, [])
        self.assertEqual(fake_window.imageNames, [])
        self.assertEqual(fake_window.rendered_cell_items, [])
        self.assertIs(fake_window.no_image_redraw_fit_view, True)
        self.assertTrue(fake_window.reset_cursor_action.triggered)
        self.assertEqual(fake_window.history_pushed[0], "Clear Images")


if __name__ == "__main__":
    unittest.main()
