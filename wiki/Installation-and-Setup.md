# Installation and Setup

This page describes what you need to run or build Icescopy.

## What Icescopy is distributed as

For most users, Icescopy is distributed as a packaged desktop application.

The repository also contains the Python source code and PyInstaller build specification used to create the packaged app.

## End-user requirements

You need:

- a machine that can run the packaged build for your platform
- an ordered image sequence from a freezing-array experiment
- optional external temperature files if you plan to use temperature import

## Repository layout

The main project areas are:

- `src/`
  - Python application source
- `resources/`
  - icons, preferences, and bundled assets
- `tests/`
  - non-GUI unit tests
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

The repository includes a PyInstaller spec:

- `Icescopy.spec`

With the development environment active, run:

```bash
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

Build outputs appear in:

- `dist/`

## Notes on packaged builds

- the packaged app does not bundle the repository `README.md`
- icon assets used by the macOS build come from `resources/app_icons/`

## Preferences and writable data

Users should treat the installed application as read-only. The bundled `resources/preferences.xml` supplies defaults; saved preferences go to the platform's user configuration directory under `Icescopy/preferences.xml`. Developers can set `ICESCOPY_CONFIG_DIR` to use an isolated configuration directory while testing.

Session files, exports, and other user data belong in user-chosen writable folders, not inside the app bundle.
