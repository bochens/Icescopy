# API Class: `SessionDataCommand`

Session Data Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `95`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Data Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 101 | Stores first redo. |
| `after_state` | `__init__` | 100 | State bundle for after state. |
| `before_state` | `__init__` | 99 | State bundle for before state. |
| `main_window` | `__init__` | 98 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 96 | Initializes the instance. |
| `undo()` | 103 | Implements undo. |
| `redo()` | 106 | Implements redo. |
