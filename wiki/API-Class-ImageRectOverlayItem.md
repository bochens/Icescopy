# API Class: `ImageRectOverlayItem`

Interactive rectangular overlay used for image-edit reference-area workflows.

## Source

- Module: [`icescopy_image_edit`](API-Module-icescopy-image-edit)
- File: `src/icescopy_image_edit.py`
- Line: `471`

## Inheritance

- Bases: `QGraphicsObject`

## Purpose

Interactive rectangular overlay used for image-edit reference-area workflows.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `areaChanged` | 472 | Stores area changed. |
| `areaChangeFinished` | 473 | Stores area change finished. |
| `HANDLE_RADIUS` | 475 | Radius value for handle radius. |
| `MIN_SIZE` | 476 | Size value for min size. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_drag_corner` | `__init__` | 483 | Stores drag corner. |
| `_drag_mode` | `__init__` | 482 | Mode value for drag mode. |
| `_image_rect` | `__init__` | 480 | Stores image rect. |
| `_interactive` | `__init__` | 486 | Stores interactive. |
| `_press_pos` | `__init__` | 484 | Stores press pos. |
| `_rect` | `__init__` | 481 | Stores rect. |
| `_start_rect` | `__init__` | 485 | Stores start rect. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None)` | 478 | Initializes the instance. |
| `set_interactive(interactive)` | 491 | Sets interactive. |
| `area_state()` | 515 | Implements area state. |
| `boundingRect()` | 523 | Implements bounding rect. |
| `_corner_at_pos(pos)` | 535 | Implements corner at pos. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `_handle_points()` | 527 | Implements handle points. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `mousePressEvent(event)` | 541 | Qt mouse-press event handler. |
| `mouseMoveEvent(event)` | 562 | Qt mouse-move event handler. |
| `mouseReleaseEvent(event)` | 623 | Qt mouse-release event handler. |
| `paint(painter, option, widget=None)` | 632 | Implements paint. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_from_rect(image_rect, rect_state)` | 497 | Synchronizes from rect. |
