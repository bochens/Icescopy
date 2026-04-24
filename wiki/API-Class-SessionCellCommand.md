# API Class: `SessionCellCommand`

Session Cell Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `23`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Cell Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 29 | Stores first redo. |
| `after_state` | `__init__` | 28 | State bundle for after state. |
| `before_state` | `__init__` | 27 | State bundle for before state. |
| `main_window` | `__init__` | 26 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 24 | Initializes the instance. |
| `undo()` | 31 | Implements undo. |
| `redo()` | 34 | Implements redo. |
