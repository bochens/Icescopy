import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import Icescopy as icescopy_module
from Icescopy import IceScopy
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from icescopy_cell_items import CellSnapshot
from icescopy_session_io import session_content_fingerprint


class SessionChangesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": str(self.root / "config")})
        config.start()
        self.addCleanup(config.stop)
        self.window = IceScopy()
        self.addCleanup(self.dispose_window)

    def dispose_window(self):
        self.window.hide()
        self.window.stop_video_preview_decoder()
        self.window.deleteLater()
        self.app.processEvents()

    def load_images(self):
        paths = []
        for index, width in enumerate((80, 100, 120)):
            path = self.root / f"frame_{index:03d}.png"
            image = QImage(width, 60, QImage.Format_RGB32)
            image.fill(QColor(40 + index * 20, 40, 40))
            self.assertTrue(image.save(str(path)))
            paths.append(str(path))
        self.window.session_active = True
        self.window.load_aux(paths)

    def save(self, filename="saved.icescopy"):
        destination = self.root / filename
        self.assertTrue(self.window.persist_session_to_path(str(destination), show_errors=False))
        return destination

    def add_cell(self, x=20.0):
        cell = CellSnapshot((x, 20.0), 5.0, (x, 20.0), 0)
        self.window.cell_items = [cell]
        self.window.ensure_cell_record(0)
        return cell

    def prompt(self, choice, *, save_succeeds=True):
        dialog = Mock()
        buttons = {name: object() for name in ("save", "discard", "cancel")}
        dialog.addButton.side_effect = list(buttons.values())
        dialog.clickedButton.return_value = buttons[choice]
        with (
            patch.object(icescopy_module, "QMessageBox", return_value=dialog),
            patch.object(self.window, "saveSession", return_value=save_succeeds) as save,
        ):
            result = self.window.prompt_save_before_replacing_session()
        return result, save

    def test_new_empty_session_and_initial_metadata_are_clean(self):
        self.assertFalse(self.window.has_unsaved_session_changes())
        with patch.object(self.window, "prompt_new_session_metadata", return_value={"project_name": "New project"}):
            self.window.newSession()

        self.assertTrue(self.window.session_active)
        self.assertFalse(self.window.has_unsaved_session_changes())
        with patch.object(icescopy_module, "QMessageBox") as message_box:
            self.assertEqual(self.window.prompt_save_before_replacing_session(), "discard")
        message_box.assert_not_called()

        self.window.apply_session_metadata({"project_name": "Edited project"})
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_unsaved_images_prompt_and_saved_images_do_not(self):
        self.load_images()
        self.assertTrue(self.window.has_unsaved_session_changes())
        self.assertEqual(self.prompt("discard")[0], "discard")
        self.save()

        self.assertFalse(self.window.has_unsaved_session_changes())
        with patch.object(icescopy_module, "QMessageBox") as message_box:
            self.assertEqual(self.window.prompt_save_before_replacing_session(), "discard")
        message_box.assert_not_called()

    def test_navigation_and_selection_ignore_interpolated_geometry_and_image_width(self):
        self.load_images()
        first = self.add_cell(20.0)
        last = CellSnapshot((60.0, 20.0), 9.0, (60.0, 20.0), 0)
        self.window.keyframe_list = [0, 2]
        self.window.keyframe_cell_items_dict = {0: [copy.deepcopy(first)], 2: [last]}
        self.save()

        for frame in (1, 2, 0):
            self.window.updateImage(frame)
            self.window.cell_items[0].edit_chosen = True
            self.window.cell_items[0].circle_positions = (900.0, 900.0)
            self.window.circle_radius = 17.0
            self.window.log("Viewed another frame")
            self.assertFalse(self.window.has_unsaved_session_changes(), f"frame {frame}")

    def test_non_keyframe_edit_is_detected(self):
        self.load_images()
        first = self.add_cell()
        self.window.keyframe_list = [0, 2]
        self.window.keyframe_cell_items_dict = {0: [copy.deepcopy(first)], 2: [copy.deepcopy(first)]}
        self.window.updateImage(1)
        self.save()
        self.window.cell_items[0].circle_pixel_positions = (22.0, 20.0)

        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_document_fields_and_result_values_are_tracked(self):
        self.load_images()
        self.add_cell()
        self.save()
        mutations = {
            "session_project_name": "Changed project",
            "sample_catalog": {0: {"sample_name": "Changed sample"}},
            "flagframe_list": [1],
            "analysis_start_frame_list": [1],
            "image_edit_exposure": 1.0,
            "last_temperature_reset_temperature": 0.0,
            "freeze_results_headers": ["cell_id", "freeze_frame"],
            "freeze_results_rows": [[0, 2]],
            "freeze_count_timeseries_rows": [[0, -5.0, 1]],
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                original = getattr(self.window, field)
                setattr(self.window, field, value)
                self.assertNotEqual(session_content_fingerprint(self.window), self.window.saved_session_fingerprint)
                self.assertTrue(self.window.has_unsaved_session_changes())
                setattr(self.window, field, original)
                self.assertFalse(self.window.has_unsaved_session_changes())

        self.window.cell_records_by_id[0].sample_id = "0"
        self.assertTrue(self.window.has_unsaved_session_changes())
        self.window.cell_records_by_id[0].sample_id = ""
        self.window.cell_items[0].circle_sizes = 8.0
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_undo_to_saved_state_is_clean_and_redo_is_dirty(self):
        self.load_images()
        self.add_cell()
        self.save()
        before = self.window.capture_cell_state()
        self.window.cell_items[0].circle_pixel_positions = (25.0, 20.0)
        self.window.push_cell_history("Move Cell", before)
        self.assertTrue(self.window.has_unsaved_session_changes())

        self.window.undo_stack.undo()
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.window.undo_stack.redo()
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_clearing_all_content_still_counts_as_unsaved_change(self):
        self.load_images()
        self.save()
        self.window.clear_loaded_images(confirm=False)

        self.assertFalse(self.window.has_session_save_payload())
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_clear_session_undo_preserves_saved_and_unsaved_baselines(self):
        self.load_images()
        self.save()
        self.window.clear_session(confirm=False)
        self.window.undo_stack.undo()
        self.assertFalse(self.window.has_unsaved_session_changes())

        self.window.apply_session_metadata({"project_name": "Unsaved metadata"})
        self.window.clear_session(confirm=False)
        self.window.undo_stack.undo()
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_failed_save_and_cancelled_save_as_keep_dirty_state_and_path(self):
        self.load_images()
        destination = self.save()
        baseline = self.window.saved_session_fingerprint
        self.window.apply_session_metadata({"project_name": "Changed project"})
        with patch.object(icescopy_module, "save_session_bundle", side_effect=OSError("write failed")):
            self.assertFalse(self.window.persist_session_to_path(str(self.root / "failed.icescopy"), show_errors=False))
        self.assertEqual(self.window.saved_session_fingerprint, baseline)
        self.assertEqual(self.window.current_session_file_path, str(destination))

        with patch.object(icescopy_module.QFileDialog, "getSaveFileName", return_value=("", "")):
            self.assertFalse(self.window.saveSessionAs())
        self.assertTrue(self.window.has_unsaved_session_changes())
        self.assertEqual(self.window.current_session_file_path, str(destination))

        alternate = self.save("alternate.icescopy")
        self.assertEqual(self.window.current_session_file_path, str(alternate))
        self.assertFalse(self.window.has_unsaved_session_changes())

    def test_save_failure_or_cancel_blocks_replacement(self):
        self.load_images()
        result, save = self.prompt("save", save_succeeds=False)
        self.assertEqual(result, "cancel")
        save.assert_called_once_with()
        result, save = self.prompt("cancel")
        self.assertEqual(result, "cancel")
        save.assert_not_called()

    def test_successful_open_is_clean_and_failed_open_retains_prior_baseline(self):
        self.load_images()
        destination = self.save()
        self.window.apply_session_metadata({"project_name": "Unsaved metadata"})
        with patch.object(self.window, "prompt_save_before_replacing_session", return_value="discard"):
            self.assertTrue(self.window.open_session_file_path(destination))
        self.assertFalse(self.window.has_unsaved_session_changes())

        baseline = self.window.saved_session_fingerprint
        self.window.apply_session_metadata({"project_name": "New unsaved metadata"})
        original_restore = self.window.restore_session_state
        restore_calls = 0

        def fail_once(state):
            nonlocal restore_calls
            restore_calls += 1
            original_restore(state)
            if restore_calls == 1:
                raise RuntimeError("restore failed after modifying state")

        with (
            patch.object(self.window, "prompt_save_before_replacing_session", return_value="discard"),
            patch.object(self.window, "restore_session_state", side_effect=fail_once),
            patch.object(icescopy_module.QMessageBox, "critical"),
        ):
            self.assertFalse(self.window.open_session_file_path(destination))
        self.assertEqual(self.window.saved_session_fingerprint, baseline)
        self.assertEqual(self.window.session_project_name, "New unsaved metadata")
        self.assertTrue(self.window.has_unsaved_session_changes())

    def test_failed_change_check_keeps_save_prompt(self):
        self.load_images()
        self.save()
        with patch.object(icescopy_module, "session_content_fingerprint", side_effect=ValueError("invalid data")):
            self.assertTrue(self.window.has_unsaved_session_changes())

    def test_unset_crop_roundtrip_keeps_full_size_on_differently_sized_frames(self):
        self.load_images()
        destination = self.save()
        self.assertTrue(self.window.open_session_file_path(destination))
        self.assertIsNone(self.window.image_edit_crop_width)

        self.window.updateImage(2)
        self.assertEqual(self.window.current_image_edit_crop_state()["width"], 120.0)
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.window.clear_session(confirm=False)
        self.window.undo_stack.undo()
        self.assertIsNone(self.window.image_edit_crop_width)
        self.assertFalse(self.window.has_unsaved_session_changes())

    def test_crop_definition_change_invalidates_caches_even_if_current_bounds_match(self):
        self.load_images()
        explicit_crop = self.window.current_image_edit_crop_state()
        state = self.window.serialize_image_edit_state()
        state["crop"] = explicit_crop
        self.window.apply_image_edit_state(state, refresh_display=False, sync_controls=False)
        self.assertEqual(self.window.image_edit_crop_width, 80.0)

        state["crop"] = {"center_x": None, "center_y": None, "width": None, "height": None, "angle": 0.0}
        with patch.object(self.window, "clear_image_caches") as clear_caches:
            self.window.apply_image_edit_state(state, refresh_display=False, sync_controls=False)
        clear_caches.assert_called_once_with()
        self.window.updateImage(2)
        self.assertEqual(self.window.current_image_edit_crop_state()["width"], 120.0)


if __name__ == "__main__":
    unittest.main()
