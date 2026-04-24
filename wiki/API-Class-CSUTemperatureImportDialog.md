# API Class: `CSUTemperatureImportDialog`

CSUTemperature Import Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `163`

## Inheritance

- Bases: `QDialog`

## Purpose

CSUTemperature Import Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `blank_sample_list` | `__init__` | 214 | Ordered list used for blank sample list. |
| `file_path_edit` | `__init__` | 200 | Stores file path edit. |
| `main_window` | `__init__` | 173 | Stores main window. |
| `reset_temperature_spinbox` | `__init__` | 223 | Spin box widget for reset temperature spinbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, initial_path, sample_names, initial_reset_temperature=None, parent=None)` | 164 | Initializes the instance. |
| `accept()` | 275 | Accepts the dialog state and closes the widget. |
| `get_values()` | 293 | Returns values. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `browse_file()` | 256 | Implements browse file. |
