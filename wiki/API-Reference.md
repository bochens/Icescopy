# API Reference

This section is the source-level reference for the Python package under `src/`.

Each module page documents:

- module-level variables
- top-level functions
- classes defined in that file

Each class page documents:

- inheritance
- class variables or dataclass fields
- instance attributes discovered from `self.` assignments
- methods with signatures and summaries

## Modules

| Module | Purpose | Classes | Functions | Page |
| --- | --- | --- | --- | --- |
| `Icescopy` | Main application module that defines the `IceScopy` window class and application-level behavior. | 3 | 0 | [Open](API-Module-Icescopy) |
| `icescopy_aux` | Auxiliary Qt widgets, dialogs, and the image-analysis worker thread. | 6 | 1 | [Open](API-Module-icescopy-aux) |
| `icescopy_cell` | Persistent cell records and cell-state bookkeeping helpers. | 2 | 0 | [Open](API-Module-icescopy-cell) |
| `icescopy_cell_controller` | Cell-edit workflow controller and preview-handle logic. | 2 | 0 | [Open](API-Module-icescopy-cell-controller) |
| `icescopy_cell_items` | Graphics-scene items and snapshots used to display cells. | 2 | 0 | [Open](API-Module-icescopy-cell-items) |
| `icescopy_dialogs` | Standalone dialogs extracted from the main app shell. | 5 | 1 | [Open](API-Module-icescopy-dialogs) |
| `icescopy_dock` | Custom dock title-bar widget. | 1 | 0 | [Open](API-Module-icescopy-dock) |
| `icescopy_frameslider` | Timeline slider widgets and custom paint/hit logic. | 2 | 0 | [Open](API-Module-icescopy-frameslider) |
| `icescopy_freezfinder` | Freeze-finding utility functions and CSV-oriented batch dialog. | 1 | 9 | [Open](API-Module-icescopy-freezfinder) |
| `icescopy_image_edit` | Image-adjustment helpers and overlay widgets for crop and histogram workflows. | 3 | 20 | [Open](API-Module-icescopy-image-edit) |
| `icescopy_plot` | Grayscale plot rendering widget. | 1 | 0 | [Open](API-Module-icescopy-plot) |
| `icescopy_session` | Undo/redo command objects and image-list model. | 9 | 0 | [Open](API-Module-icescopy-session) |
| `icescopy_session_io` | Session bundle serialization and deserialization helpers. | 0 | 14 | [Open](API-Module-icescopy-session-io) |
| `icescopy_stylesheet` | Application stylesheet assembly helpers. | 0 | 0 | [Open](API-Module-icescopy-stylesheet) |
| `icescopy_temperature_import` | Temperature import, parsing, reconciliation, and cycle-detection helpers. | 5 | 40 | [Open](API-Module-icescopy-temperature-import) |
| `icescopy_tool_options` | Reusable tool-options page widgets and layout constants. | 2 | 0 | [Open](API-Module-icescopy-tool-options) |
