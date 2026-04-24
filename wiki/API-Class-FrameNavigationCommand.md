# API Class: `FrameNavigationCommand`

Frame Navigation Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `131`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Frame Navigation Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 137 | Stores first redo. |
| `after_index` | `__init__` | 136 | Zero-based index for after index. |
| `before_index` | `__init__` | 135 | Zero-based index for before index. |
| `main_window` | `__init__` | 134 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_index, after_index)` | 132 | Initializes the instance. |
| `undo()` | 139 | Implements undo. |
| `redo()` | 142 | Implements redo. |
