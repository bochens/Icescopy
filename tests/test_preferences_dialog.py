import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from xml.etree.ElementTree import parse

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit
from Icescopy import IceScopy
from icescopy_aux import PreferencesDialog
from icescopy_paths import user_preferences_path
from icescopy_sample_metadata import default_sample_metadata_schema, sample_metadata_schema_from_xml


class PreferencesDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": temporary.name})
        config.start()
        self.addCleanup(config.stop)
        self.window = SimpleNamespace(
            load_preferences_from_xml=lambda: IceScopy.load_preferences_from_xml(None),
            set_preferences=Mock(),
            active_sample_metadata_schema=default_sample_metadata_schema,
            session_active=False,
        )

    def dialog(self, category=None):
        dialog = PreferencesDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        if category is not None:
            dialog.category_list.setCurrentRow(category)
            dialog.show()
            dialog.activateWindow()
            self.app.processEvents()
        return dialog

    def edit_new_sample_label(self, dialog, text):
        dialog.add_sample_metadata_field()
        table = dialog.sample_metadata_schema_table
        row = table.rowCount() - 1
        table.setCurrentCell(row, PreferencesDialog.SAMPLE_FIELD_COLUMN_LABEL)
        table.scrollToItem(table.currentItem())
        table.setFocus()
        # Test pending editor contents, not the platform's edit shortcut.
        table.editItem(table.currentItem())
        self.app.processEvents()
        editor = self.app.focusWidget()
        self.assertIsInstance(editor, QLineEdit)
        editor.selectAll()
        QTest.keyClicks(editor, text)
        self.assertEqual(table.currentItem().text(), "Custom field")
        return editor

    def test_typed_number_saves_from_focused_editor_with_mouse_or_enter(self):
        for action, value in (("mouse", "17.3"), ("enter", "19.7")):
            with self.subTest(action=action):
                dialog = self.dialog(category=2)
                field = dialog.maximum_zoom_field
                field.setFocus()
                field.selectAll()
                QTest.keyClicks(field, value)
                self.assertIs(self.app.focusWidget(), field)
                if action == "mouse":
                    save = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save)
                    QTest.mouseClick(save, Qt.LeftButton)
                else:
                    QTest.keyClick(field, Qt.Key_Return)
                self.app.processEvents()
                self.assertEqual(dialog.result(), QDialog.Accepted)
                self.assertFalse(dialog.isVisible())
                self.assertEqual(parse(user_preferences_path()).findtext("MaximumZoom"), value)
                self.assertEqual(self.dialog().maximum_zoom_field.value(), float(value))

    def test_mouse_save_commits_active_sample_table_editor(self):
        dialog = self.dialog(category=1)
        self.edit_new_sample_label(dialog, "Experiment batch")
        save = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save)
        QTest.mouseClick(save, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        saved_schema = sample_metadata_schema_from_xml(parse(user_preferences_path()).getroot())
        self.assertEqual(saved_schema[-1]["label"], "Experiment batch")

    def test_escape_table_edit_then_cancel_preserves_saved_file(self):
        self.dialog().save_preferences()
        before = user_preferences_path().read_bytes()
        self.window.set_preferences.reset_mock()
        dialog = self.dialog(category=1)
        editor = self.edit_new_sample_label(dialog, "Unsaved label")
        QTest.keyClick(editor, Qt.Key_Escape)
        self.app.processEvents()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.sample_metadata_schema_table.currentItem().text(), "Custom field")
        self.assertEqual(user_preferences_path().read_bytes(), before)
        cancel = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Cancel)
        QTest.mouseClick(cancel, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(user_preferences_path().read_bytes(), before)
        self.window.set_preferences.assert_not_called()

    def test_save_closes_and_reopening_retains_values(self):
        for zoom, prominence in ((17, 12), (19, 14)):
            with self.subTest(zoom=zoom):
                dialog = self.dialog()
                dialog.maximum_zoom_field.setValue(zoom)
                dialog.freeze_finder_prominence_field.setValue(prominence)
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
                self.assertEqual(dialog.result(), QDialog.Accepted)
                reopened = self.dialog()
                self.assertEqual(reopened.maximum_zoom_field.value(), zoom)
                self.assertEqual(reopened.freeze_finder_prominence_field.value(), prominence)
        self.window.set_preferences.assert_called_with(preserve_session_tool_state=True)

    def test_cancel_does_not_write_changed_values(self):
        self.dialog().save_preferences()
        before = user_preferences_path().read_bytes()
        dialog = self.dialog()
        dialog.maximum_zoom_field.setValue(17)
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Cancel).click()
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(user_preferences_path().read_bytes(), before)

    def test_failed_replace_preserves_previous_file_and_allows_retry(self):
        self.dialog().save_preferences()
        before = user_preferences_path().read_bytes()
        dialog = self.dialog()
        dialog.maximum_zoom_field.setValue(17)
        self.window.set_preferences.reset_mock()
        with patch("icescopy_paths.os.replace", side_effect=PermissionError("File is locked")), patch(
            "icescopy_aux.prompt_save_access", return_value="cancel"
        ) as error:
            dialog.save_preferences()
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(user_preferences_path().read_bytes(), before)
        self.assertEqual(list(user_preferences_path().parent.glob("*.tmp")), [])
        self.window.set_preferences.assert_not_called()
        self.assertEqual(error.call_args.args[1], user_preferences_path())
        dialog.save_preferences()
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_invalid_xml_text_keeps_previous_file_and_reports_error(self):
        self.dialog().save_preferences()
        before = user_preferences_path().read_bytes()
        self.window.set_preferences.reset_mock()
        dialog = self.dialog()
        dialog.sample_name_pattern_field.setText("Sample_\x0b#")
        dialog.maximum_zoom_field.setValue(17)
        with patch("icescopy_aux.QMessageBox.warning") as warning:
            dialog.save_preferences()
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(user_preferences_path().read_bytes(), before)
        self.window.set_preferences.assert_not_called()
        self.assertEqual(warning.call_args.args[1], "Invalid Preference Text")
        dialog.sample_name_pattern_field.setText("Sample_#")
        dialog.save_preferences()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(parse(user_preferences_path()).findtext("MaximumZoom"), "17.0")

    def test_malformed_xml_is_visible_without_overwriting_file(self):
        user_preferences_path().write_text("<Preferences><broken", encoding="utf-8")
        before = user_preferences_path().read_bytes()
        dialog = self.dialog()
        self.assertIn("could not be read", dialog.preferences_load_warning_label.text())
        self.assertFalse(dialog.preferences_load_warning_label.isHidden())
        self.assertEqual(user_preferences_path().read_bytes(), before)

    def test_invalid_numeric_field_warns_without_resetting_other_fields(self):
        user_preferences_path().write_text(
            "<Preferences><MaximumZoom>17</MaximumZoom><PenWidth>invalid</PenWidth></Preferences>",
            encoding="utf-8",
        )
        before = user_preferences_path().read_bytes()
        dialog = self.dialog()
        self.assertEqual(dialog.maximum_zoom_field.value(), 17)
        self.assertIn("PenWidth", dialog.preferences_load_warning_label.text())
        self.assertFalse(dialog.preferences_load_warning_label.isHidden())
        self.assertEqual(user_preferences_path().read_bytes(), before)

    def test_application_error_reports_saved_file_and_allows_retry(self):
        for stage in ("set_preferences", "apply_sample_metadata_schema"):
            with self.subTest(stage=stage):
                self.window.session_active = True
                self.window.set_preferences = Mock()
                self.window.apply_sample_metadata_schema = Mock()
                failing = getattr(self.window, stage)
                failing.side_effect = RuntimeError("Test application failure")
                dialog = self.dialog()
                dialog.maximum_zoom_field.setValue(17)
                with patch("icescopy_aux.QMessageBox.critical") as error, patch(
                    "icescopy_aux.traceback.print_exc"
                ) as diagnostic:
                    dialog.save_preferences()
                self.assertEqual(dialog.result(), QDialog.Rejected)
                self.assertEqual(parse(user_preferences_path()).findtext("MaximumZoom"), "17.0")
                self.assertEqual(error.call_args.args[1], "Apply Preferences Failed")
                self.assertIn("saved", error.call_args.args[2])
                self.assertIn("Test application failure", error.call_args.args[2])
                diagnostic.assert_called_once()
                failing.side_effect = None
                dialog.save_preferences()
                self.assertEqual(dialog.result(), QDialog.Accepted)


if __name__ == "__main__":
    unittest.main()
