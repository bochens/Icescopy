# API Class: `ImageCropOverlayItem`

Interactive crop overlay used to define rotated crop state.

## Source

- Module: [`icescopy_image_edit`](API-Module-icescopy-image-edit)
- File: `src/icescopy_image_edit.py`
- Line: `656`

## Inheritance

- Bases: `QGraphicsObject`

## Purpose

Interactive crop overlay used to define rotated crop state.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `cropChanged` | 657 | Stores crop changed. |
| `cropChangeFinished` | 658 | Stores crop change finished. |
| `HANDLE_RADIUS` | 660 | Radius value for handle radius. |
| `EDGE_HIT_WIDTH` | 661 | Geometry value for edge hit width. |
| `ROTATE_HANDLE_RADIUS` | 662 | Radius value for rotate handle radius. |
| `ROTATE_HANDLE_DISTANCE` | 663 | Stores rotate handle distance. |
| `MIN_SIZE` | 664 | Size value for min size. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_crop_state` | `__init__` | 669 | State bundle for crop state. |
| `_drag_corner_index` | `__init__` | 677 | Zero-based index for drag corner index. |
| `_drag_mode` | `__init__` | 676 | Mode value for drag mode. |
| `_image_rect` | `__init__` | 668 | Stores image rect. |
| `_press_pos` | `__init__` | 678 | Stores press pos. |
| `_start_state` | `__init__` | 679 | State bundle for start state. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None)` | 666 | Initializes the instance. |
| `boundingRect()` | 691 | Implements bounding rect. |
| `_crop_polygon()` | 695 | Implements crop polygon. |
| `_corner_points_for_state(state)` | 698 | Implements corner points for state. |
| `_basis_vectors()` | 701 | Implements basis vectors. |
| `_corner_points()` | 707 | Implements corner points. |
| `_edge_midpoints_for_state(state)` | 710 | Implements edge midpoints for state. |
| `_edge_segments_for_state(state)` | 719 | Implements edge segments for state. |
| `_point_to_segment_distance(point, segment_start, segment_end)` | 728 | Implements point to segment distance. |
| `_interaction_for_pos(local_pos)` | 747 | Implements interaction for pos. |
| `_set_cursor_for_interaction(interaction)` | 758 | Implements set cursor for interaction. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `_rotation_handle_point()` | 741 | Implements rotation handle point. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `hoverMoveEvent(event)` | 772 | Implements hover move event. |
| `hoverLeaveEvent(event)` | 776 | Qt hover-leave event handler. |
| `mousePressEvent(event)` | 780 | Qt mouse-press event handler. |
| `mouseMoveEvent(event)` | 799 | Qt mouse-move event handler. |
| `mouseReleaseEvent(event)` | 863 | Qt mouse-release event handler. |
| `paint(painter, option, widget)` | 871 | Implements paint. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_from_state(image_rect, crop_state)` | 684 | Synchronizes from state. |
