# API Class: `OutputResultsDialog`

Output Results Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `392`

## Inheritance

- Bases: `QDialog`

## Purpose

Output Results Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `freeze_checkbox` | `__init__` | 418 | Stores freeze checkbox. |
| `grayscale_checkbox` | `__init__` | 417 | Stores grayscale checkbox. |
| `select_all_checkbox` | `__init__` | 414 | Stores select all checkbox. |
| `temperature_checkbox` | `__init__` | 419 | Stores temperature checkbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None, *, include_grayscale=False, include_freeze=False, include_temperature=False)` | 393 | Initializes the instance. |
| `accept()` | 440 | Accepts the dialog state and closes the widget. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `selected_exports()` | 450 | Returns selected exports. |
| `visible_export_checkboxes()` | 460 | Implements visible export checkboxes. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `on_select_all_toggled(checked)` | 471 | Implements on select all toggled. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_select_all_checkbox()` | 477 | Synchronizes select all checkbox. |
