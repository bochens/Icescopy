# API Class: `SessionImageEditCommand`

Session Image Edit Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `113`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Image Edit Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 119 | Stores first redo. |
| `after_state` | `__init__` | 118 | State bundle for after state. |
| `before_state` | `__init__` | 117 | State bundle for before state. |
| `main_window` | `__init__` | 116 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 114 | Initializes the instance. |
| `undo()` | 121 | Implements undo. |
| `redo()` | 124 | Implements redo. |
