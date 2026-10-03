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

from PySide6.QtWidgets import QApplication, QDialog
from Icescopy import IceScopy
from icescopy_aux import PreferencesDialog
from icescopy_paths import user_preferences_path
from icescopy_session_io import load_session_bundle


class SaveAccessIntegrationTests(unittest.TestCase):
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

    def preference_dialog(self, window):
        dialog = PreferencesDialog(window)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def preference_window(self):
        return SimpleNamespace(
            load_preferences_from_xml=lambda: IceScopy.load_preferences_from_xml(None),
            set_preferences=Mock(),
            session_active=False,
        )

    def session_window(self, current_path):
        return SimpleNamespace(
            inptk_panel=SimpleNamespace(prepare_session_save=Mock()),
            current_session_file_path=str(current_path),
            grayscale_results_headers=[],
            grayscale_results_rows=[],
            freeze_results_headers=[],
            freeze_results_rows=[],
            freeze_count_timeseries_headers=[],
            freeze_count_timeseries_rows=[],
            log=Mock(),
            saveSessionAs=Mock(return_value=False),
        )

    def test_preferences_retry_preserves_old_file_until_write_succeeds(self):
        window = self.preference_window()
        self.preference_dialog(window).save_preferences()
        destination = user_preferences_path()
        before = destination.read_bytes()
        window.set_preferences.reset_mock()
        dialog = self.preference_dialog(window)
        dialog.maximum_zoom_field.setValue(17)
        original_replace = os.replace
        attempts = []

        def fail_once(source, target):
            attempts.append(target)
            if len(attempts) == 1:
                raise PermissionError(13, "Access denied", str(target))
            return original_replace(source, target)

        def retry_after_denial(*args, **kwargs):
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual(dialog.maximum_zoom_field.value(), 17)
            window.set_preferences.assert_not_called()
            return "retry"

        with patch("icescopy_paths.os.replace", side_effect=fail_once), patch(
            "icescopy_aux.prompt_save_access", side_effect=retry_after_denial
        ) as prompt, patch("icescopy_aux.QMessageBox.critical") as critical:
            dialog.save_preferences()

        self.assertEqual(len(attempts), 2)
        prompt.assert_called_once()
        self.assertEqual(Path(prompt.call_args.args[1]), destination)
        self.assertEqual(parse(destination).findtext("MaximumZoom"), "17.0")
        self.assertEqual(dialog.result(), QDialog.Accepted)
        window.set_preferences.assert_called_once_with(preserve_session_tool_state=True)
        self.assertEqual(list(destination.parent.glob("*.tmp")), [])
        critical.assert_not_called()

    def test_preferences_cancel_preserves_file_and_edited_fields(self):
        window = self.preference_window()
        self.preference_dialog(window).save_preferences()
        destination = user_preferences_path()
        before = destination.read_bytes()
        window.set_preferences.reset_mock()
        dialog = self.preference_dialog(window)
        dialog.maximum_zoom_field.setValue(17)

        with patch(
            "icescopy_paths.os.replace", side_effect=PermissionError(13, "Access denied", str(destination))
        ) as replace, patch("icescopy_aux.prompt_save_access", return_value="cancel") as prompt, patch(
            "icescopy_aux.QMessageBox.critical"
        ) as critical:
            dialog.save_preferences()

        replace.assert_called_once()
        prompt.assert_called_once()
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(dialog.maximum_zoom_field.value(), 17)
        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(list(destination.parent.glob("*.tmp")), [])
        window.set_preferences.assert_not_called()
        critical.assert_not_called()

    def test_session_retry_updates_current_path_only_after_success(self):
        previous = self.root / "previous.icescopy"
        destination = self.root / "retry.icescopy"
        before = b"previous saved contents"
        destination.write_bytes(before)
        window = self.session_window(previous)
        payload = {"session_metadata": {"name": "Retried session"}}
        original_replace = os.replace
        attempts = []

        def fail_once(source, target):
            attempts.append(target)
            if len(attempts) == 1:
                raise PermissionError(13, "Access denied", str(target))
            return original_replace(source, target)

        def retry_after_denial(*args, **kwargs):
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual(window.current_session_file_path, str(previous))
            return "retry"

        with patch("Icescopy.build_session_payload", return_value=payload), patch(
            "icescopy_session_io.os.replace", side_effect=fail_once
        ), patch("Icescopy.prompt_save_access", side_effect=retry_after_denial) as prompt, patch(
            "Icescopy.QMessageBox.critical"
        ) as critical:
            saved = IceScopy.persist_session_to_path(window, str(destination))

        self.assertTrue(saved)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(window.current_session_file_path, str(destination))
        self.assertEqual(load_session_bundle(destination)[0], payload)
        self.assertEqual(prompt.call_args.kwargs.get("allow_save_as"), True)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        critical.assert_not_called()

    def test_session_cancel_keeps_previous_path_and_file(self):
        previous = self.root / "previous.icescopy"
        destination = self.root / "blocked.icescopy"
        before = b"previous saved contents"
        destination.write_bytes(before)
        window = self.session_window(previous)

        with patch("Icescopy.build_session_payload", return_value={}), patch(
            "icescopy_session_io.os.replace", side_effect=PermissionError(13, "Access denied", str(destination))
        ) as replace, patch("Icescopy.prompt_save_access", return_value="cancel") as prompt, patch(
            "Icescopy.QMessageBox.critical"
        ) as critical:
            saved = IceScopy.persist_session_to_path(window, str(destination))

        self.assertFalse(saved)
        replace.assert_called_once()
        prompt.assert_called_once()
        self.assertEqual(Path(prompt.call_args.args[1]), destination)
        self.assertEqual(window.current_session_file_path, str(previous))
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        window.saveSessionAs.assert_not_called()
        critical.assert_not_called()

    def test_session_save_as_recovers_to_another_file(self):
        previous = self.root / "previous.icescopy"
        destination = self.root / "blocked.icescopy"
        alternate = self.root / "allowed.icescopy"
        before = b"previous saved contents"
        destination.write_bytes(before)
        window = self.session_window(previous)
        payload = {"session_metadata": {"name": "Recovered session"}}
        original_replace = os.replace

        def deny_original_destination(source, target):
            if Path(target) == destination:
                raise PermissionError(13, "Access denied", str(target))
            return original_replace(source, target)

        window.saveSessionAs.side_effect = lambda: IceScopy.persist_session_to_path(window, str(alternate))
        with patch("Icescopy.build_session_payload", return_value=payload), patch(
            "icescopy_session_io.os.replace", side_effect=deny_original_destination
        ), patch("Icescopy.prompt_save_access", return_value="save_as") as prompt, patch(
            "Icescopy.QMessageBox.critical"
        ) as critical:
            saved = IceScopy.persist_session_to_path(window, str(destination))

        self.assertTrue(saved)
        window.saveSessionAs.assert_called_once_with()
        prompt.assert_called_once()
        self.assertEqual(window.current_session_file_path, str(alternate))
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(load_session_bundle(alternate)[0], payload)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        critical.assert_not_called()

    def test_silent_session_save_denial_does_not_open_recovery_dialog(self):
        previous = self.root / "previous.icescopy"
        destination = self.root / "blocked.icescopy"
        before = b"previous saved contents"
        destination.write_bytes(before)
        window = self.session_window(previous)

        with patch("Icescopy.build_session_payload", return_value={}), patch(
            "icescopy_session_io.os.replace", side_effect=PermissionError(13, "Access denied", str(destination))
        ) as replace, patch("Icescopy.prompt_save_access") as prompt, patch(
            "Icescopy.QMessageBox.critical"
        ) as critical:
            saved = IceScopy.persist_session_to_path(window, str(destination), show_errors=False)

        self.assertFalse(saved)
        replace.assert_called_once()
        self.assertEqual(window.current_session_file_path, str(previous))
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        prompt.assert_not_called()
        critical.assert_not_called()
        window.saveSessionAs.assert_not_called()
        window.log.assert_called()


if __name__ == "__main__":
    unittest.main()
