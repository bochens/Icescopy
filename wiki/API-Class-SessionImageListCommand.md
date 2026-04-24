# API Class: `SessionImageListCommand`

Session Image List Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `59`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Image List Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 65 | Stores first redo. |
| `after_state` | `__init__` | 64 | State bundle for after state. |
| `before_state` | `__init__` | 63 | State bundle for before state. |
| `main_window` | `__init__` | 62 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 60 | Initializes the instance. |
| `undo()` | 67 | Implements undo. |
| `redo()` | 70 | Implements redo. |
