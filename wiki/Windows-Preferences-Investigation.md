# Windows Preferences investigation — 2026-09-28

> Historical investigation record. For current instructions, see [Preferences and sessions](Sessions-Export-and-Preferences.md) and [Troubleshooting](Troubleshooting.md). Preserve the dated observations below when adding a new investigation.

## Environment

- Source baseline: `bf1c737009f305242842a27a04465c67794b51fd` (`origin/main`).
- OS reported by Python: `Windows-10-10.0.26200-SP0`.
- Python: Anaconda 3.11.15; PySide6 and Qt: 6.11.0.
- Executable: `C:\Users\bchen\anaconda3\envs\Icescopy\python.exe`.
- Source checkout: `C:\Users\bchen\.codex\worktrees\icescopy-bug-fixes\Icescopy`.
- Disposable configuration: `F:\Icescopy\tmp\settings-check-20260928\preferences.xml`.
- Existing work in `F:\Icescopy` and real user preferences were preserved.

## Native Windows observations

The source application was launched with the native Windows Qt platform (no offscreen override). Preferences was opened from the toolbar in an empty session. Maximum Zoom was changed from 10 to 17. Pressing Enter with that number field focused closed Preferences and wrote `MaximumZoom=17.0` to the disposable XML file. Reopening Preferences displayed 17.0. Clicking Save with the mouse also closed the dialog. A separate fresh Python process loaded 17.0 through the application's preferences reader.

These checks did not reproduce an inert Save button in the current source. They do not establish the cause of the originally reported behavior in an installed executable.

## Confirmed error-handling gap and fix

An injected exception from either `set_preferences` or `apply_sample_metadata_schema` reproduced an uncaught failure after the XML had already been saved. Previously the dialog could remain open without a visible explanation. The save handler now catches application errors, prints the traceback, and shows **Apply Preferences Failed**, explicitly explaining that the file was saved and that some settings may already have changed. The dialog remains available for retry or cancellation. This does not roll back partially applied settings or claim the underlying application error is resolved.

Regression tests cover both application stages, retry, Save/Cancel button signals, reopening with saved values, replacement of an existing settings file, and a simulated locked-file replacement error preserving the previous file and removing its temporary file. Both injected application-error cases failed before the fix and passed afterward.

Initial validation: all 131 tests passed; `git diff --check` passes. Automated widget tests use Qt offscreen and are distinct from the native observations above.

## Follow-up status

- Compare the installed/published executable against a newly packaged build containing the earlier persistence fix (`d4ceced`) and this error-reporting change.
- Native active-session/sample-schema edits, restarting the full GUI, title-bar close, and focus/task switching remain untested. Later automated tests exercise active sessions, keyboard editing/cancellation, and a real Windows file lock using disposable files.
- The later follow-up fixes malformed-value loading, metadata retry rollback, and native permission recovery. See [Windows save recovery](Windows-Save-Recovery.md) for current implementation and validation.

The temporary `README_WINDOWS_SETTINGS_CHECK.md` was retired when the macOS build was added to v2.3.7. This page and [Windows save recovery](Windows-Save-Recovery.md) retain the investigation evidence and its testing limitations.
