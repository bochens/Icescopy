# API Class: `SortImagesDialog`

Dialog for choosing the image sort mode and previewing ordering.

## Source

- Module: [`icescopy_aux`](API-Module-icescopy-aux)
- File: `src/icescopy_aux.py`
- Line: `1291`

## Inheritance

- Bases: `QDialog`

## Purpose

Dialog for choosing the image sort mode and previewing ordering.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `SORT_OPTIONS` | 1292 | Stores sort options. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `availability` | `__init__` | 1304 | Stores availability. |
| `info_label` | `__init__` | 1329 | Label widget for info label. |
| `main_window` | `__init__` | 1303 | Stores main window. |
| `sort_mode_combo` | `__init__` | 1315 | Combo box widget for sort mode combo. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, availability, current_mode, parent=None)` | 1301 | Initializes the instance. |
| `selected_mode()` | 1356 | Returns selected mode. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `update_info_label()` | 1345 | Updates info label. |
