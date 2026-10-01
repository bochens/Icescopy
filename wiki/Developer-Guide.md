# Developer Guide

Use this guide to set up a checkout, find the code for a change, and choose checks. See [Installation and Setup](Installation-and-Setup.md) for user installation, [Architecture Overview](Architecture-Overview.md) for design, and [API Reference](API-Reference.md) for declarations.

## Set up and run

[pyproject.toml](../pyproject.toml) requires Python 3.11 or newer. The conda file creates a Python 3.11 environment and installs the project in editable mode, so source edits are used without reinstalling each time:

```sh
conda env create -f environment.yml
conda activate icescopy-dev
icescopy-validate
icescopy
```

With an existing suitable environment, install from the repository root:

```sh
python -m pip install -e '.[dev,training]'
icescopy-validate
```

The `dev` extra adds PyInstaller. Runtime dependencies are declared in `pyproject.toml`; avoid maintaining a second manual dependency list. PySide6 supplies Qt's interface and PyAV supplies video decoding.

A direct source run on macOS/Linux is `PYTHONPATH=src python -m Icescopy`. The validator also checks installed-package metadata against the source, so a missing installation or version mismatch is a meaningful failure. Reinstall the editable package after changing its version or packaging metadata.

### Isolate settings

Use a separate preference directory when testing settings changes:

```sh
dev_config=$(mktemp -d)
ICESCOPY_CONFIG_DIR="$dev_config" icescopy
```

In Windows PowerShell:

```powershell
$env:ICESCOPY_CONFIG_DIR = Join-Path $env:TEMP ('icescopy-dev-' + [guid]::NewGuid())
icescopy
```

The override controls preferences, not media or session output paths. Use disposable session copies and new output locations for save/export checks. Media remain external references in a session.

## Find the change boundary

| Change | Start here | Follow through to |
| --- | --- | --- |
| Frame source or video behavior | [Frame sources](API-Module-icescopy-frame-source.md) | Preview thread, source payload, navigation, cleanup |
| Circle/grid interaction | [Cell System](Cell-System.md) | Controller, keyframes, history, measurement geometry |
| Measurement or detection | [Worker](API-Class-Image-analysis-thread.md), [freeze functions](API-Module-icescopy-freezfinder.md) | Missing values, ranges, source indexes |
| Temperature format | [Parsers](API-Module-icescopy-temperature-import.md) | Dialog, timing/count builder, errors, export metadata |
| Sample fields | [Schema](API-Module-icescopy-sample-metadata.md) | Catalog, preferences, saved schema, exports |
| Session format | [Session I/O](API-Module-icescopy-session-io.md) | Migration, rollback, old sessions, atomic save |
| Tool/view UI or plot | [Window](API-Class-IceScopy.md), [plot](API-Module-icescopy-plot.md) | Action state, keyboard/accessibility controls, native layout |
| Preferences | [Paths](API-Module-icescopy-paths.md), [dialog](API-Class-PreferencesDialog.md) | Validation, Save/Cancel, apply and save-access recovery |

Many `IceScopy` methods depend on initialized widgets and window state. Prefer independent numerical/parser functions for reusable computation. Preserve each helper's responsibility instead of moving unrelated session state into it.

## Work through a change

1. Establish a clean branch or commit checkpoint. Identify the existing user behavior and read the relevant implementation/tests.
2. Identify the state owner and dependent values. Geometry affects measurements; freeze annotations affect counts; source order affects frame mappings.
3. Use the existing mutation path. For undoable changes, capture before-state, apply the edit, then push its history command. Commands skip Qt's first `redo()` because the edit has already happened.
4. Decide what becomes stale. Refreshing a view, clearing a cache, invalidating analysis, and rerunning analysis are different operations.
5. Check changed behavior and its failure case, review the diff, and update the relevant documentation. Record what was actually checked.

For source replacement or shutdown, inspect both preview and analysis lifetimes. Preview owns a separate decoder; analysis uses the active source. Do not destroy running Qt threads or change GUI widgets from worker methods. The current app blocks closing during analysis and has no general cancellation API. [Architecture](Architecture-Overview.md#workers-caches-and-cleanup) identifies reset paths requiring extra care.

## Choose focused checks

Tests use Python's `unittest`. Run from the repository root in the project environment. For a focused noninteractive Qt check on macOS/Linux:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p test_frame_source.py -v
```

In PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` first and run the `python -m unittest ...` command without the shell assignment. Remove that variable before checking the native GUI.

| Area | Useful tests |
| --- | --- |
| Sources, clip mapping, timing/ranges | [test_frame_source.py](../tests/test_frame_source.py) |
| Circular measurement and worker failure | [test_roi_mean.py](../tests/test_roi_mean.py) |
| Freeze-search signal handling | [test_freeze_finder_padding.py](../tests/test_freeze_finder_padding.py) |
| Temperature/count logic | [test_freeze_count_timeseries_logic.py](../tests/test_freeze_count_timeseries_logic.py), [test_session_io.py](../tests/test_session_io.py) |
| Cell interaction/timeline | [test_cell_controller.py](../tests/test_cell_controller.py), [test_frame_slider.py](../tests/test_frame_slider.py) |
| Plot and tool/view synchronization | [test_grayscale_plot_widget.py](../tests/test_grayscale_plot_widget.py), [test_toolbar_modes.py](../tests/test_toolbar_modes.py) |
| Sample schema/catalog | [test_sample_metadata.py](../tests/test_sample_metadata.py) |
| Save/restore/recovery | [test_session_io.py](../tests/test_session_io.py), [test_save_access_integration.py](../tests/test_save_access_integration.py) |
| Preferences | [test_preferences_loading.py](../tests/test_preferences_loading.py), [test_preferences_dialog.py](../tests/test_preferences_dialog.py), [test_preferences_application.py](../tests/test_preferences_application.py), [test_paths.py](../tests/test_paths.py) |

Broaden to the full suite for changes across these boundaries or release preparation:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
python -m Icescopy --check-video-dependencies
```

The dependency check confirms PyAV can import; it does not exercise seeking, timing, or full analysis. Offscreen tests do not prove native menus, accessibility controls, file dialogs, packaged startup, or visual alignment. Check the relevant native interaction and report its scope separately. Software tests do not establish scientific validation.

## Maintain the documentation

API explanations and selected entry points are curated in [tools/api_reference.json](../tools/api_reference.json). The updater reads Python syntax for current declarations and source locations without importing Qt or inventing descriptions from attribute names.

```sh
python tools/update_api_reference.py
python tools/update_api_reference.py --check
python tools/wiki_docs.py check
```

`--check` fails for stale generated pages, missing module/class inventory, or selected callables that no longer exist. Retain an old class page with an explicit replacement note when its implementation disappears. Architecture and workflow pages are maintained by hand. See [Documentation Guide](Documentation-Guide.md) for publishing to GitHub Wiki.

## Build a release artifact

Build the intended commit in a separate source snapshot or checkout to preserve older `build/` and `dist/` outputs. [icescopy_version.py](../src/icescopy_version.py) supplies the Python package and macOS bundle version. The Windows installer receives its version separately and must use the intended matching value.

| Platform | Build inputs | Instructions |
| --- | --- | --- |
| macOS Apple Silicon | [Icescopy.spec](../Icescopy.spec) | [macOS packaging](../packaging/macos/README.md) |
| Windows x64 | [Icescopy.windows.spec](../Icescopy.windows.spec), [Inno Setup script](../packaging/windows/Icescopy.iss) | [Windows packaging](../packaging/windows/README.md) |

Inside that isolated checkout/environment:

```sh
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

Use `Icescopy.windows.spec` on Windows. The macOS specification patches its default `build/` and `dist/` locations after PyInstaller's signing step; follow final signing and verification in the packaging guide. A successful build is not evidence of notarization or support for another processor architecture.

Before publication, verify version, architecture, dependency import, archive integrity, checksum, and relevant native workflows. Keep source-test and packaged-app checks distinct. Packaging pages contain historical release examples: substitute the intended release version, and preserve other platform assets when publishing a platform-specific update.
