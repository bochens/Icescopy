"""User-directed recovery when a save is denied or a destination is locked."""

import errno
import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox


WINDOWS_ALLOW_APP_URI = "windowsdefender://allowappthroughfolder"
WINDOWS_PERMISSION_HELP_URL = (
    "https://support.microsoft.com/en-us/windows/security/threat-malware-protection/"
    "virus-and-threat-protection-in-the-windows-security-app"
)


def is_save_access_error(error):
    return isinstance(error, PermissionError) or (
        isinstance(error, OSError)
        and (
            error.errno in {errno.EACCES, errno.EPERM, errno.EROFS}
            or getattr(error, "winerror", None) in {5, 32, 33}
        )
    )


def prompt_save_access(parent, path, error, *, allow_save_as=False):
    """Return retry/save_as/cancel; never elevate or change security settings."""
    locked = getattr(error, "winerror", None) in {32, 33}
    read_only = getattr(error, "errno", None) == errno.EROFS
    if locked:
        title = "File Is in Use"
    elif read_only:
        title = "Read-only Location"
    else:
        title = "Permission Needed to Save"
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Warning)
    dialog.setWindowTitle(title)
    dialog.setTextFormat(Qt.PlainText)
    dialog.setText(f"Icescopy could not save this file:\n{os.fspath(path)}")
    if locked:
        guidance = "Close any other program using this file, then choose Retry."
    elif read_only:
        guidance = "This location is read-only. Use a writable location or ask its owner for write access."
    else:
        guidance = (
            "Check that the file and folder are writable and the file is closed in other programs, "
            "then choose Retry."
        )
        if sys.platform == "win32":
            guidance += (
                "\n\nIf Windows Security blocked Icescopy, choose Allow App in Windows, "
                "add the application shown in Details, then Retry."
            )
    if allow_save_as:
        guidance += "\n\nChoose Save As to save your session in another location."
    guidance += "\n\nCancel keeps your unsaved work open."
    dialog.setInformativeText(guidance)
    details = f"{type(error).__name__}: {error}\nApplication: {sys.executable}"
    if sys.platform == "win32" and not locked and not read_only:
        details += (
            "\n\nAllow App in Windows opens the Controlled folder access permission screen. "
            "Windows may ask for administrator approval. If a restart is required after granting "
            "access, save any open session to another location before restarting Icescopy."
        )
    dialog.setDetailedText(details)
    dialog.setStandardButtons(QMessageBox.Retry | QMessageBox.Cancel)
    dialog.setDefaultButton(QMessageBox.Cancel)
    dialog.setEscapeButton(QMessageBox.Cancel)
    save_as_button = dialog.addButton("Save As…", QMessageBox.ActionRole) if allow_save_as else None
    help_button = (
        dialog.addButton("Allow App in Windows…", QMessageBox.ActionRole)
        if sys.platform == "win32" and not locked and not read_only else None
    )
    try:
        while True:
            dialog.exec()
            clicked = dialog.clickedButton()
            if clicked is not None and clicked == help_button:
                if not QDesktopServices.openUrl(QUrl(WINDOWS_ALLOW_APP_URI)):
                    QMessageBox.information(
                        parent, "Could Not Open Windows Security",
                        "Open Windows Security > Virus & threat protection > Ransomware protection "
                        "> Allow an app through Controlled folder access. Review the blocked app "
                        "before allowing it.\n\n" + WINDOWS_PERMISSION_HELP_URL,
                    )
                continue
            if clicked is not None and clicked == save_as_button:
                return "save_as"
            if clicked == dialog.button(QMessageBox.Retry):
                return "retry"
            return "cancel"
    finally:
        dialog.deleteLater()
