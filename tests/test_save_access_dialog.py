import errno
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication, QMessageBox
from icescopy_save_access import is_save_access_error, prompt_save_access, WINDOWS_ALLOW_APP_URI


class SaveAccessDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_classifies_access_errors_without_treating_disk_full_as_permission(self):
        for code in (errno.EACCES, errno.EPERM, errno.EROFS):
            self.assertTrue(is_save_access_error(OSError(code, "Test")))
        for code in (errno.ENOSPC, errno.ENOENT, errno.EIO):
            self.assertFalse(is_save_access_error(OSError(code, "Test")))
        self.assertFalse(is_save_access_error(ValueError("Bad input")))

    def test_standard_cancel_and_retry_actions(self):
        for button, expected in ((QMessageBox.Cancel, "cancel"), (QMessageBox.Retry, "retry")):
            with self.subTest(action=expected):
                def interact(dialog):
                    self.assertIn("test.icescopy", dialog.text())
                    dialog.button(button).click()
                with patch.object(QMessageBox, "exec", interact):
                    self.assertEqual(prompt_save_access(None, "test.icescopy", PermissionError("Denied")), expected)

    def test_windows_button_opens_native_allow_app_screen_then_waits_for_retry(self):
        clicks = []
        def interact(dialog):
            if not clicks:
                button = next(b for b in dialog.buttons() if b.text().startswith("Allow App in Windows"))
            else:
                button = dialog.button(QMessageBox.Retry)
            clicks.append(button.text())
            button.click()
        with patch("icescopy_save_access.sys.platform", "win32"), patch.object(
            QMessageBox, "exec", interact
        ), patch("icescopy_save_access.QDesktopServices.openUrl", return_value=True) as open_url:
            self.assertEqual(prompt_save_access(None, "prefs.xml", PermissionError("Denied")), "retry")
        self.assertEqual(open_url.call_args.args[0].toString(), WINDOWS_ALLOW_APP_URI)
        open_url.assert_called_once()
        self.assertEqual(len(clicks), 2)

    def test_native_launch_failure_keeps_retry_and_cancel_available(self):
        for button, expected in ((QMessageBox.Retry, "retry"), (QMessageBox.Cancel, "cancel")):
            with self.subTest(action=expected):
                clicks = []

                def interact(dialog):
                    if not clicks:
                        selected = next(
                            b for b in dialog.buttons() if b.text().startswith("Allow App in Windows")
                        )
                    else:
                        selected = dialog.button(button)
                    clicks.append(selected.text())
                    selected.click()

                with patch("icescopy_save_access.sys.platform", "win32"), patch.object(
                    QMessageBox, "exec", interact
                ), patch("icescopy_save_access.QDesktopServices.openUrl", return_value=False) as open_url, patch(
                    "icescopy_save_access.QMessageBox.information"
                ) as fallback:
                    self.assertEqual(
                        prompt_save_access(None, "prefs.xml", PermissionError("Denied")), expected
                    )
                open_url.assert_called_once()
                fallback.assert_called_once()
                self.assertIn("Controlled folder access", fallback.call_args.args[2])
                self.assertEqual(len(clicks), 2)

    def test_locked_file_offers_retry_without_security_permission_button(self):
        for code in (32, 33):
            with self.subTest(winerror=code):
                error = OSError("File is locked")
                error.winerror = code
                self.assertTrue(is_save_access_error(error))

                def interact(dialog):
                    # macOS ignores QMessageBox window titles; verify the
                    # recovery instruction that users see on every platform.
                    self.assertIn("Close any other program using this file", dialog.informativeText())
                    self.assertFalse(any("Allow App" in b.text() for b in dialog.buttons()))
                    dialog.button(QMessageBox.Cancel).click()

                with patch("icescopy_save_access.sys.platform", "win32"), patch.object(
                    QMessageBox, "exec", interact
                ):
                    self.assertEqual(prompt_save_access(None, "session.icescopy", error), "cancel")

    def test_read_only_location_does_not_offer_windows_security(self):
        def interact(dialog):
            self.assertIn("read-only", dialog.informativeText().lower())
            self.assertFalse(any("Allow App" in b.text() for b in dialog.buttons()))
            dialog.button(QMessageBox.Cancel).click()
        error = OSError(errno.EROFS, "Read-only filesystem")
        with patch("icescopy_save_access.sys.platform", "win32"), patch.object(
            QMessageBox, "exec", interact
        ):
            self.assertEqual(prompt_save_access(None, "session.icescopy", error), "cancel")

    def test_other_platforms_do_not_offer_windows_security(self):
        def interact(dialog):
            self.assertFalse(any("Allow App" in b.text() for b in dialog.buttons()))
            dialog.button(QMessageBox.Cancel).click()
        with patch("icescopy_save_access.sys.platform", "darwin"), patch.object(
            QMessageBox, "exec", interact
        ):
            self.assertEqual(prompt_save_access(None, "prefs.xml", PermissionError("Denied")), "cancel")

    def test_save_as_action_keeps_original_error_available(self):
        error = PermissionError(13, "Access denied", "test.icescopy")

        def interact(dialog):
            self.assertIn(str(error), dialog.detailedText())
            self.assertIn(sys.executable, dialog.detailedText())
            self.assertIn("test.icescopy", dialog.text())
            next(b for b in dialog.buttons() if b.text().startswith("Save As")).click()

        with patch.object(QMessageBox, "exec", interact):
            self.assertEqual(
                prompt_save_access(None, "test.icescopy", error, allow_save_as=True), "save_as"
            )


if __name__ == "__main__":
    unittest.main()
