# Icescopy Windows save recovery build

> Historical investigation record. For current user instructions, see [save recovery](Troubleshooting.md#cannot-save-a-session-preferences-or-csv) and [installation](Installation-and-Setup.md). The build and test observations below describe the investigation at that time.

This investigation originally used a portable test build based on GitHub main bf1c737 plus fixes on codex/windows-preferences-errors. That test executable displayed version 2.3.6 and was separate from the previously published release. The final fixes were committed as 1da2f75 and are included in version 2.3.7. The test-build validation below records that investigation; release-specific packaging checks are recorded separately.

## Reproduced code failures

1. A pasted XML-forbidden control character (U+000B) in Sample Name Pattern could be written successfully. The dialog closed, but the next XML read failed and showed defaults. The completed temporary XML is now parsed before replacing the existing file; invalid text produces a visible error and preserves the prior file.
2. A single malformed numeric preference could discard all saved values during loading. Infinity in an integer field could raise an uncaught OverflowError; NaN in a floating field could appear as a different value in the control. Numeric fields are now validated individually against the UI bounds and valid fields are preserved. Preferences shows a warning for rejected values or an unreadable file.
3. A post-write settings-application exception could leave Preferences open without explaining that the file was already saved. This now has a distinct application-error message.
4. Preferences loaded global sample-field defaults while Save applied them to the open session. With an imported/saved experiment, changing only Maximum Zoom could silently reset its field labels, export options, and same-for-all flags. The editor now starts from the active session's schema and explains that saving also updates defaults for future sessions. Saving unchanged fields also preserves existing undo entries.


These are reproducible code paths; they do not establish which caused the originally reported failure on an installed executable.

## Windows permissions

Settings remain under the user's configuration folder. Icescopy does not require administrator privileges for normal use. Failed access prompts offer Retry/Cancel, the target path, and the original error. Session saves additionally offer the normal Save As picker. Explicit Windows sharing violations are identified as file locks. A real replacement lock also returned WinError 5 (Access denied) in testing, so the generic message does not assume Defender is responsible.

The Allow App in Windows button opens Windows' native Allow an app through Controlled folder access screen using Microsoft's published windowsdefender://allowappthroughfolder shortcut. The user reviews and grants any permission inside Windows. The app does not change Defender settings, add antivirus exclusions, or claim that every access-denied error is caused by Defender. Windows may require an app restart after granting access, so save a session elsewhere first.

Reference: https://support.microsoft.com/en-us/windows/security/threat-malware-protection/virus-and-threat-protection-in-the-windows-security-app

An unsigned executable being blocked before launch is a separate app-reputation issue; no in-app dialog can run before Windows allows the app to start.

## Test notes

Automated tests use disposable settings/files and mocked permission dialogs; they do not alter this PC's security configuration. The Windows shortcut is verified against Microsoft's published page and tested without opening or manipulating Windows Security. A native Win32 file handle blocks replacement of a disposable settings file in the Windows-only regression test; the old contents remain intact and a retry succeeds after releasing the handle. Qt tests also exercise typed numeric input, pending table edits, cancellation, actual application of settings, and saving/reopening a session with custom sample fields. No UI automation was resumed after the user's Escape stop.

## Final validation

All 165 tests pass. See BUILD-INFO.md beside the compiled test build for its executable path and hash. A metadata rename rollback regression was also fixed: if application fails after mutating sample data, the original metadata is restored before a retry, so a swapped-name rename cannot be applied twice. The regression injects a refresh failure; it does not identify the original reported crash.
