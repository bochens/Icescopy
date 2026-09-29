# Icescopy 2.3.7

This release improves saving, settings, and recovery from errors. Download **Icescopy-windows-installer.exe** for 64-bit Windows 10 (1809 or later) or Windows 11. The installer includes Python and the application dependencies and installs for the current user.

For Apple Silicon Macs, download **Icescopy-macos-arm64.zip**, extract it, and copy Icescopy.app to Applications. This build contains the same v2.3.7 application source as the Windows release. It has an ad-hoc signature and has not been notarized by Apple, so macOS may require explicit approval to open it. No Intel Mac binary is included.

## Changes since 2.3.6

- Save preferences in the user's configuration folder and preserve the previous preferences or session file when a save fails.
- Offer Retry and Cancel for denied or locked saves, Save As for sessions, and a direct button to Windows' native Controlled folder access permission screen.
- Preserve an open session's custom sample fields when changing unrelated preferences, and restore metadata if an update fails before retrying.
- Report invalid preference text and malformed numeric values while retaining other valid settings; distinguish write failures from failures applying saved settings.
- Recover from analysis errors and handle missing grayscale measurements without suppressing later valid freeze events or inventing transitions across gaps.
- Improve older-session loading and recovery when opening a session fails; fix a Windows runtime DLL conflict that could prevent startup.

**Checksums:** `SHA256SUMS.txt` covers the Windows installer; `Icescopy-macos-arm64.zip.sha256` covers the macOS archive.

## Validation

The changes passed 165 automated tests, including Windows file-lock recovery and preference/session save workflows. The versioned Windows package passed its dependency check. A disposable installation, upgrade, and uninstall passed, including removal of obsolete runtime DLLs and preservation of unrelated user files. The installed executable matches the built application and embeds version 2.3.7.

On macOS, 164 tests passed and the Windows-only file-lock test was skipped, after correcting two platform assumptions in the tests (message-box titles and the table-edit shortcut). Application code was unchanged. The arm64 app reports version 2.3.7, passes its PyAV dependency check, and its extracted archive passes signature verification. Native startup and closing Preferences with Save and Cancel were observed; packaged-app changed-value persistence, restart, and full video analysis were not established by that GUI check. The dependency check emits duplicate AVFoundation receiver warnings from the bundled OpenCV/PyAV libraries; those warnings remain.
