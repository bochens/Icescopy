import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QApplication, QDialog
from Icescopy import IceScopy
from icescopy_aux import PreferencesDialog


class PreferencesApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": folder.name})
        config.start()
        self.addCleanup(config.stop)
        self.window = IceScopy()
        self.addCleanup(self.window.deleteLater)

    def dialog(self):
        dialog = PreferencesDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def save(self, dialog):
        with patch("icescopy_aux.QMessageBox.critical") as errors:
            dialog.save_preferences()
        errors.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_unchanged_metadata_save_does_not_evict_real_history(self):
        self.window.session_active = True
        self.window.undo_stack.setUndoLimit(1)
        existing = QUndoCommand("Existing real edit")
        self.window.undo_stack.push(existing)
        dialog = self.dialog()
        dialog.maximum_zoom_field.setValue(18)
        self.save(dialog)
        self.assertEqual(self.window.undo_stack.count(), 1)
        self.assertIs(self.window.undo_stack.command(0), existing)
        self.assertEqual(self.window.undo_stack.undoText(), "Existing real edit")

    def test_ml_choice_persists_across_windows_without_changing_research_session(self):
        self.window.session_active = True
        self.window.mark_session_clean()
        path = (self.folder / "selected.icescopy-model").resolve()
        dialog = self.dialog()
        dialog.droplet_model_field.addItem(path.name, str(path))
        dialog.droplet_model_field.setCurrentIndex(1)
        config = SimpleNamespace(name="Selected detector", version="3.0.0")
        with patch("icescopy_neural_detection.load_model", return_value=config):
            self.save(dialog)
        self.assertEqual(self.window.droplet_model_path, str(path))
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.assertEqual(self.window.undo_stack.count(), 0)
        reopened = IceScopy()
        self.addCleanup(reopened.deleteLater)
        self.assertEqual(reopened.droplet_model_path, str(path))

    def test_metadata_change_creates_working_undo_and_redo(self):
        self.window.session_active = True
        before = self.window.active_sample_metadata_schema()
        dialog = self.dialog()
        table = dialog.sample_metadata_schema_table
        row = next(row for row in range(table.rowCount()) if
                   table.item(row, dialog.SAMPLE_FIELD_COLUMN_KEY).text() == "well_volume_uL")
        table.item(row, dialog.SAMPLE_FIELD_COLUMN_LABEL).setText("Experiment aliquot")
        self.save(dialog)
        after = self.window.active_sample_metadata_schema()
        self.assertNotEqual(after, before)
        self.assertEqual(self.window.undo_stack.count(), 1)
        self.assertEqual(self.window.undo_stack.undoText(), "Update Sample Metadata Fields")
        self.window.undo_stack.undo()
        self.assertEqual(self.window.active_sample_metadata_schema(), before)
        self.window.undo_stack.redo()
        self.assertEqual(self.window.active_sample_metadata_schema(), after)

    def test_inp_plot_style_persists_without_changing_the_session(self):
        self.window.session_active = True
        self.window.mark_session_clean()
        dialog = self.dialog()
        styles = {'InptkSampleLineWidth': 3.5, 'InptkCombinedLineWidth': 5.0,
                  'InptkMarkerSize': 0.0, 'InptkOutsideOpacity': 45.0}
        for key, value in styles.items(): dialog.inptk_style_fields[key].setValue(value)
        self.save(dialog)
        reopened = IceScopy()
        self.addCleanup(reopened.deleteLater)
        self.assertEqual((reopened.inptk_sample_line_width, reopened.inptk_combined_line_width,
                          reopened.inptk_marker_size, reopened.inptk_outside_opacity), (3.5, 5.0, 0.0, 45.0))
        self.assertFalse(self.window.has_unsaved_session_changes())

    def test_unrelated_save_preserves_opened_session_metadata_schema(self):
        self.window.session_active = True
        field = next(field for field in self.window.sample_metadata_schema if field["key"] == "well_volume_uL")
        field.update(label="Experiment aliquot", export=False, same_for_all=False)
        self.window.sample_catalog = {0: self.window.default_sample_record(0)}
        self.window.sample_catalog[0]["well_volume_uL"] = "5"
        path = self.folder / "experiment.icescopy"
        self.assertTrue(self.window.persist_session_to_path(str(path)))
        with patch.object(self.window, "prompt_save_before_replacing_session", return_value="discard"):
            self.assertTrue(self.window.open_session_file_path(str(path)))
        expected = self.window.active_sample_metadata_schema()
        dialog = self.dialog()
        self.assertEqual(dialog.collect_sample_metadata_schema()[0], expected)
        dialog.maximum_zoom_field.setValue(18)
        with patch("icescopy_aux.QMessageBox.question") as question:
            self.save(dialog)
        question.assert_not_called()
        self.assertEqual(self.window.active_sample_metadata_schema(), expected)
        self.assertEqual(self.window.sample_catalog[0]["well_volume_uL"], "5")
        self.assertEqual(self.window.load_preferences_from_xml()["SampleMetadataSchema"], expected)


if __name__ == "__main__":
    unittest.main()
