# API Class: `SessionSnapshotCommand`

Session Snapshot Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `5`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Snapshot Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 11 | Stores first redo. |
| `after_state` | `__init__` | 10 | State bundle for after state. |
| `before_state` | `__init__` | 9 | State bundle for before state. |
| `main_window` | `__init__` | 8 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 6 | Initializes the instance. |
| `undo()` | 13 | Implements undo. |
| `redo()` | 16 | Implements redo. |
