# API Class: `TAMUTemperatureImportDialog`

TAMUTemperature Import Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `216`

## Inheritance

- Bases: `QDialog`

## Purpose

TAMUTemperature Import Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `calibration_path_edit` | `__init__` | 269 | Stores calibration path edit. |
| `file_path_edit` | `__init__` | 252 | Stores file path edit. |
| `main_window` | `__init__` | 226 | Stores main window. |
| `reset_temperature_spinbox` | `__init__` | 283 | Spin box widget for reset temperature spinbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, initial_path, initial_calibration_path='', initial_reset_temperature=None, parent=None)` | 217 | Initializes the instance. |
| `accept()` | 355 | Accepts the dialog state and closes the widget. |
| `get_values()` | 381 | Returns values. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `browse_file()` | 317 | Implements browse file. |
| `browse_calibration_file()` | 336 | Implements browse calibration file. |
