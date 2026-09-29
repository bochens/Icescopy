import os
import sys
import tempfile
import unittest
from pathlib import Path
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
