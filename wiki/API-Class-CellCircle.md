# API Class: `CellCircle`

QGraphics ellipse item used to render and interact with one annotated cell in the scene.

## Source

- Module: [`icescopy_cell_items`](API-Module-icescopy-cell-items)
- File: `src/icescopy_cell_items.py`
- Line: `20`

## Inheritance

- Bases: `QGraphicsEllipseItem`

## Purpose

QGraphics ellipse item used to render and interact with one annotated cell in the scene.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `LABEL_FONT` | 21 | Stores label font. |
| `LABEL_OFFSET_X` | 23 | Geometry value for label offset x. |
| `LABEL_OFFSET_Y` | 24 | Geometry value for label offset y. |
| `Z_VALUE` | 25 | Stores z value. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_label_text` | `__init__` | 37 | Stores label text. |
| `cell_id` | `__init__` | 36 | Stores cell ID. |
| `circle_pixel_positions` | `__init__` | 35 | Stores circle pixel positions. |
| `circle_positions` | `__init__` | 33 | Stores circle positions. |
| `circle_sizes` | `__init__` | 34 | Collection of size values for circle sizes. |
| `edit_chosen` | `__init__` | 46 | Stores edit chosen. |
| `hover` | `__init__` | 44 | Stores hover. |
| `main_window` | `__init__` | 29 | Stores main window. |
| `pressed` | `__init__` | 45 | Stores pressed. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, circle_positions, circle_sizes, circle_pixel_positions, cell_id)` | 28 | Initializes the instance. |
| `__deepcopy__(memo)` | 171 | Implements deepcopy. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `paint(painter, option, widget)` | 84 | Implements paint. |
| `hoverEnterEvent(event)` | 120 | Qt hover-enter event handler. |
| `hoverLeaveEvent(event)` | 126 | Qt hover-leave event handler. |
| `mousePressEvent(event)` | 132 | Qt mouse-press event handler. |
| `mouseReleaseEvent(event)` | 148 | Qt mouse-release event handler. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_from_data(circle_positions, circle_sizes, circle_pixel_positions, cell_id, *, edit_chosen=None, hover=False, pressed=False)` | 48 | Synchronizes from data. |
| `update_selectable_state()` | 163 | Updates selectable state. |
