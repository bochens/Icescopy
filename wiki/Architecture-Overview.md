# Architecture Overview

This page describes the main structural pieces of the Icescopy codebase.

## Main application shell

The central application object is:

- `src/Icescopy.py`

`IceScopy` is the composition root.
It still owns:

- UI construction
- session state
- scene/view wiring
- result tables
- history commands
- image caches

## Recent file split

The helper classes that used to live in `src/Icescopy.py` were split into focused modules:

- `src/icescopy_tool_options.py`
- `src/icescopy_dialogs.py`
- `src/icescopy_dock.py`

The goal was to keep `src/Icescopy.py` as the main application shell instead of a mixed shell-plus-helper-class file.

## Major subsystems

### Cell system

- `src/icescopy_cell.py`
- `src/icescopy_cell_controller.py`
- `src/icescopy_cell_items.py`

These three files separate:

- persistent cell data
- edit behavior
- scene item rendering

### Session and history

- `src/icescopy_session.py`
- `src/icescopy_session_io.py`

These files handle command objects and session bundle persistence.

### Analysis and temperature import

- `src/icescopy_aux.py`
- `src/icescopy_freezfinder.py`
- `src/icescopy_temperature_import.py`

These files handle grayscale measurement, freeze detection support, and temperature-timeseries integration.

### Display and image editing

- `src/icescopy_frameslider.py`
- `src/icescopy_image_edit.py`
- `src/icescopy_plot.py`
- `src/icescopy_stylesheet.py`

These files handle timeline behavior, image-edit overlays, grayscale plot rendering, and UI styling.

## Current result model

The app works with three main result tables:

- grayscale measurements
- freeze events
- freeze count timeseries

The current `.icescopy` session bundle stores all three as CSV members inside the zip file.

## Current caching model

The app currently uses in-memory caches, not a dedicated app-level disk cache folder, for:

- raw images
- adjusted images
- display pixmaps
- circular masks
- plot series and convolution data

## Future structural pressure points

The biggest architectural pressure points are:

- `src/Icescopy.py` still being large
- the current image-path-centered frame model
- eventual support for both image sequences and video through a shared frame-source layer
