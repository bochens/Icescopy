# API Class: `OutputResultsDialog`

Output Results Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `949`

## Inheritance

- Bases: `QDialog`

## Purpose

Output Results Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `freeze_checkbox` | `__init__` | 975 | Stores freeze checkbox. |
| `freeze_count_timeseries_checkbox` | `__init__` | 976 | Stores freeze count timeseries checkbox. |
| `grayscale_checkbox` | `__init__` | 974 | Stores grayscale checkbox. |
| `select_all_checkbox` | `__init__` | 971 | Stores select all checkbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None, *, include_grayscale=False, include_freeze=False, include_freeze_count_timeseries=False)` | 950 | Initializes the instance. |
| `accept()` | 997 | Accepts the dialog state and closes the widget. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `selected_exports()` | 1007 | Returns selected exports. |
| `visible_export_checkboxes()` | 1017 | Implements visible export checkboxes. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `on_select_all_toggled(checked)` | 1028 | Implements on select all toggled. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_select_all_checkbox()` | 1034 | Synchronizes select all checkbox. |
