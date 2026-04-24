# API Class: `CustomGraphicsView`

Custom Graphics View class.

## Source

- Module: [`icescopy_aux`](API-Module-icescopy-aux)
- File: `src/icescopy_aux.py`
- Line: `180`

## Inheritance

- Bases: `QGraphicsView`

## Purpose

Custom Graphics View class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `main_window` | `__init__` | 183 | Stores main window. |
| `preview_double_click_armed` | `__init__` | 185 | Stores preview double click armed. |
| `preview_double_click_timer` | `__init__` | 186 | Timer object used for preview double click timer. |
| `selected_items` | `__init__` | 184 | Stores selected items. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(scene, main_window)` | 181 | Initializes the instance. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `wheelEvent(event)` | 203 | Qt wheel event handler. |
| `mousePressEvent(event)` | 244 | Qt mouse-press event handler. |
| `focusInEvent(event)` | 274 | Implements focus in event. |
| `mouseMoveEvent(event)` | 278 | Qt mouse-move event handler. |
| `mouseDoubleClickEvent(event)` | 286 | Qt mouse-double-click event handler. |
| `mouseReleaseEvent(event)` | 310 | Qt mouse-release event handler. |
| `keyPressEvent(event)` | 347 | Qt key-press event handler. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `_clear_preview_double_click_arm()` | 200 | Implements clear preview double click arm. |
