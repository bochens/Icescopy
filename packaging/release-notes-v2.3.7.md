# Icescopy 2.3.7

This Windows installer release improves saving, settings, and recovery from errors. Download **Icescopy-windows-installer.exe** for 64-bit Windows 10 (1809 or later) or Windows 11. The installer includes Python and the application dependencies and installs for the current user.

## Changes since 2.3.6

- Save preferences in the user's configuration folder and preserve the previous preferences or session file when a save fails.
- Offer Retry and Cancel for denied or locked saves, Save As for sessions, and a direct button to Windows' native Controlled folder access permission screen.
- Preserve an open session's custom sample fields when changing unrelated preferences, and restore metadata if an update fails before retrying.
- Report invalid preference text and malformed numeric values while retaining other valid settings; distinguish write failures from failures applying saved settings.
- Recover from analysis errors and handle missing grayscale measurements without suppressing later valid freeze events or inventing transitions across gaps.
- Improve older-session loading and recovery when opening a session fails; fix a Windows runtime DLL conflict that could prevent startup.

No macOS binary was rebuilt for this release; the previous macOS download remains available on the [2.3.6 release](https://github.com/bochens/Icescopy/releases/tag/v2.3.6).

## Validation

The changes passed 165 automated tests, including Windows file-lock recovery and preference/session save workflows. The versioned Windows package passed its dependency check. A disposable installation, upgrade, and uninstall passed, including removal of obsolete runtime DLLs and preservation of unrelated user files. The installed executable matches the built application and embeds version 2.3.7.
