# API Class: `SessionTimelineMarkersCommand`

Session Timeline Markers Command class.

## Source

- Module: [`icescopy_session`](API-Module-icescopy-session)
- File: `src/icescopy_session.py`
- Line: `41`

## Inheritance

- Bases: `QUndoCommand`

## Purpose

Session Timeline Markers Command class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_first_redo` | `__init__` | 47 | Stores first redo. |
| `after_state` | `__init__` | 46 | State bundle for after state. |
| `before_state` | `__init__` | 45 | State bundle for before state. |
| `main_window` | `__init__` | 44 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, text, before_state, after_state)` | 42 | Initializes the instance. |
| `undo()` | 49 | Implements undo. |
| `redo()` | 52 | Implements redo. |
