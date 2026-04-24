# API Class: `ImageListModel`

List model backing the images dock.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `149`

## Inheritance

- Bases: `QAbstractListModel`

## Purpose

List model backing the images dock.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_entries` | `__init__` | 152 | Stores entries. |
| `_tooltips` | `__init__` | 153 | Stores tooltips. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None)` | 150 | Initializes the instance. |
| `rowCount(parent=QModelIndex())` | 155 | Qt model row-count provider. |
| `data(index, role=Qt.DisplayRole)` | 160 | Qt model data provider. |
| `set_items(entries, tooltips)` | 174 | Sets items. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `append_items(entries, tooltips)` | 180 | Implements append items. |
| `remove_rows(rows)` | 190 | Removes rows. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `update_items(row_data)` | 213 | Updates items. |
