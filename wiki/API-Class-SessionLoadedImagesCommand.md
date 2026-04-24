# API Class: `SessionLoadedImagesCommand`

Session Loaded Images Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `77`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Loaded Images Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 83 | Stores first redo. |
| `after_state` | `__init__` | 82 | State bundle for after state. |
| `before_state` | `__init__` | 81 | State bundle for before state. |
| `main_window` | `__init__` | 80 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 78 | Initializes the instance. |
| `undo()` | 85 | Implements undo. |
| `redo()` | 88 | Implements redo. |
