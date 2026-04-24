# API Class: `TAMUTemperatureImportDialog`

TAMUTemperature Import Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `306`

## Inheritance

- Bases: `QDialog`

## Purpose

TAMUTemperature Import Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `blank_sample_list` | `__init__` | 382 | Ordered list used for blank sample list. |
| `calibration_path_edit` | `__init__` | 363 | Stores calibration path edit. |
| `file_path_edit` | `__init__` | 346 | Stores file path edit. |
| `main_window` | `__init__` | 318 | Stores main window. |
| `reset_temperature_spinbox` | `__init__` | 394 | Spin box widget for reset temperature spinbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, initial_path, sample_names, initial_calibration_path='', initial_reset_temperature=None, initial_blank_sample_names=None, parent=None)` | 307 | Initializes the instance. |
| `accept()` | 468 | Accepts the dialog state and closes the widget. |
| `get_values()` | 494 | Returns values. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `browse_file()` | 430 | Implements browse file. |
| `browse_calibration_file()` | 449 | Implements browse calibration file. |
