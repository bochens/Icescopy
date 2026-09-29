# Installation and Setup

This page describes what you need to run or build Icescopy.

## What Icescopy is distributed as

For most users, Icescopy is distributed as a packaged desktop application.

The repository also contains the Python source code and PyInstaller build specification used to create the packaged app.

## End-user requirements

You need:

- a machine that can run the packaged build for your platform
- an ordered image sequence or video recording from a freezing-array experiment
- optional external temperature files if you plan to use temperature import

### Windows installation

Download `Icescopy-windows-installer.exe` from the [GitHub releases page](https://github.com/bochens/Icescopy/releases). The Windows installer installs for the current user and includes Python and the application dependencies. Normal use does not require administrator privileges.

The current Windows build is x64 and uses Qt 6.11, which supports Windows 10 version 1809 or later and Windows 11. See [Qt's supported Windows configurations](https://doc.qt.io/qt-6/windows.html). This build does not support Windows 7, Windows 8, or 32-bit Windows.

## Repository layout

The main project areas are:

- `src/`
  - Python application source
- `resources/`
  - icons, preferences, and bundled assets
- `tests/`
  - unit tests and Qt tests that run without displaying windows
- `wiki/`
  - GitHub wiki Markdown source

## Running from source

Icescopy requires Python 3.11 or newer. The repository root contains:

- `pyproject.toml` — runtime dependencies, development extras, and command-line entry points
- `environment.yml` — a reproducible conda development environment

Clone the repository, change into its root directory, and create the conda environment:

```bash
conda env create -f environment.yml
conda activate icescopy-dev
```

Alternatively, use any Python 3.11 virtual environment:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The editable install is intentional for development: the application continues to use the repository's `resources/` directory while source changes take effect immediately.

Run the application with:

```bash
icescopy
```

## Validating an installation

First confirm that every runtime dependency and required resource can be loaded:

```bash
icescopy-validate
icescopy --check-video-dependencies
```

Then run the full test suite from the repository root:

```bash
python run_tests.py
```

## Building the packaged app

Build on the target operating system with the development environment active.

On Windows, use the Windows spec:

```powershell
python -m PyInstaller --clean --noconfirm Icescopy.windows.spec
```

The portable output is `dist/Icescopy-windows/`. Keep its `Icescopy.exe` and `_internal/` folder together. The Windows spec expects the runtime DLLs provided by the project's conda build environment. To package this folder as the per-user Inno Setup installer, follow [the Windows installer build instructions](../packaging/windows/README.md).

On macOS, use:

```bash
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

Build outputs appear in `dist/`.

## Notes on packaged builds

- the packaged app does not bundle the repository `README.md`
- icon assets used by the macOS build come from `resources/app_icons/`

## Preferences and writable data

Users should treat the installed application as read-only. The bundled `resources/preferences.xml` supplies defaults; saved preferences go to the platform's user configuration directory under `Icescopy/preferences.xml`. Developers can set `ICESCOPY_CONFIG_DIR` to use an isolated configuration directory while testing.

Session files, exports, and other user data belong in user-chosen writable folders, not inside the app bundle.

When a save is denied or a file is locked, Icescopy keeps the unsaved work open and offers Retry or Cancel. Session saves also offer Save As. If Windows Security has blocked Icescopy through Controlled folder access, Allow App in Windows opens the native permission screen directly; the user grants access there and then retries the save. The app does not change Windows security settings itself.
