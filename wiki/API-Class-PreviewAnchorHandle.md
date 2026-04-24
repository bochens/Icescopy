# API Class: `PreviewAnchorHandle`

Drag handle for pinned grid/group previews.

## Source

- Module: [`icescopy_cell_controller`](API-Module-icescopy-cell-controller)
- File: `src/icescopy_cell_controller.py`
- Line: `10`

## Inheritance

- Bases: `QGraphicsEllipseItem`

## Purpose

Drag handle for pinned grid/group previews.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `controller` | `__init__` | 20 | Stores controller. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(controller)` | 18 | Initializes the instance. |
| `itemChange(change, value)` | 32 | Qt graphics-item change callback. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_size_from_preferences()` | 27 | Synchronizes size from preferences. |
