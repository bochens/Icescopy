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
- `manual/`
  - LaTeX source for the user manual
- `wiki/`
  - GitHub wiki Markdown source

## Running from source

The application is developed against the `Icescopy` conda environment.

Typical local run command:

```zsh
conda activate Icescopy
python /Users/C832577250/Project/Icescopy/src/Icescopy.py
```

If the environment is not active, use the interpreter directly:

```zsh
/Users/C832577250/miniforge3/envs/Icescopy/bin/python /Users/C832577250/Project/Icescopy/src/Icescopy.py
```

## Running tests

Run the repository test entry point:

```zsh
/Users/C832577250/miniforge3/envs/Icescopy/bin/python /Users/C832577250/Project/Icescopy/run_tests.py
```

## Building the packaged app

The repository includes a PyInstaller spec:

- `Icescopy.spec`

Typical build command:

```zsh
/Users/C832577250/miniforge3/envs/Icescopy/bin/python -m PyInstaller --clean --noconfirm /Users/C832577250/Project/Icescopy/Icescopy.spec
```

Build outputs appear in:

- `dist/`

## Notes on packaged builds

- the packaged app does not bundle the repository `README.md`
- the packaged app does not bundle the PDF manual from the repo root
- icon assets used by the macOS build come from `resources/app_icons/`

## Preferences and writable data

Users should treat the installed application as read-only.
Session files, exports, and other user data belong in user-chosen writable folders, not inside the app bundle.
