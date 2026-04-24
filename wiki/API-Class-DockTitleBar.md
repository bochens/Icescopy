# API Class: `DockTitleBar`

Dock Title Bar class.

## Source

- Module: [`icescopy_dock`](API-Module-icescopy-dock)
- File: `src/icescopy_dock.py`
- Line: `17`

## Inheritance

- Bases: `QWidget`

## Purpose

Dock Title Bar class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `button_row` | `__init__` | 33 | Layout row container for button row. |
| `close_button` | `__init__` | 38 | Button widget for close button. |
| `dock_widget` | `__init__` | 20 | Qt widget reference for dock widget. |
| `float_button` | `__init__` | 45 | Button widget for float button. |
| `left_edge_cover` | `__init__` | 77 | Stores left edge cover. |
| `right_edge_cover` | `__init__` | 82 | Stores right edge cover. |
| `right_spacer` | `__init__` | 62 | Stores right spacer. |
| `title_label` | `__init__` | 55 | Label widget for title label. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(dock_widget, title, parent=None)` | 18 | Initializes the instance. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `toggle_floating()` | 95 | Toggles floating. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `resizeEvent(event)` | 111 | Qt resize event handler for this widget. |
| `mousePressEvent(event)` | 140 | Qt mouse-press event handler. |
| `mouseReleaseEvent(event)` | 143 | Qt mouse-release event handler. |
| `mouseMoveEvent(event)` | 146 | Qt mouse-move event handler. |
| `mouseDoubleClickEvent(event)` | 149 | Qt mouse-double-click event handler. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `refresh_buttons(*args)` | 98 | Refreshes buttons. |
| `update_edge_covers()` | 115 | Updates edge covers. |
