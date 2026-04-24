# API Class: `FrameSlider`

Primary timeline slider with keyframe, flag, and platform-specific rendering behavior.

## Source

- Module: [`icescopy_frameslider`](API-Module-icescopy-frameslider)
- File: `src/icescopy_frameslider.py`
- Line: `16`

## Inheritance

- Bases: `QSlider`

## Purpose

Primary timeline slider with keyframe, flag, and platform-specific rendering behavior.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `keyframeClicked` | 17 | Stores keyframe clicked. |
| `flagframeClicked` | 18 | Stores flagframe clicked. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_handle_pixmap` | `__init__` | 35 | Stores handle pixmap. |
| `_mouse_press_impl` | `__init__` | 38 | Stores mouse press impl. |
| `_paint_impl` | `__init__` | 36 | Stores paint impl. |
| `_position_to_x_impl` | `__init__` | 37 | Stores position to x impl. |
| `custom_ticks` | `__init__` | 31 | Stores custom ticks. |
| `flaggedframes` | `__init__` | 23 | Stores flaggedframes. |
| `keyframes` | `__init__` | 22 | Stores keyframes. |
| `left_ratio` | `__init__` | 32 | Stores left ratio. |
| `main_window` | `__init__` | 25 | Stores main window. |
| `value_has_changed` | `__init__` | 34 | Stores value has changed. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(orientation=Qt.Horizontal, main_window=None, parent=None)` | 20 | Initializes the instance. |
| `_platform_initialize()` | 44 | Implements platform initialize. |
| `_current_slider_position()` | 59 | Implements current slider position. |
| `_indicator_metrics()` | 64 | Implements indicator metrics. |
| `_required_slider_height()` | 78 | Implements required slider height. |
| `_indicator_y_positions()` | 94 | Implements indicator y positions. |
| `set_custom_ticks()` | 117 | Sets custom ticks. |
| `set_left_ratio()` | 126 | Sets left ratio. |
| `_slider_style_option(position=None)` | 330 | Implements slider style option. |
| `_slider_geometry()` | 346 | Implements slider geometry. |
| `sliderPositionToX(position)` | 353 | Convert a slider position to its corresponding X coordinate. |
| `_slider_position_to_x_windows(position)` | 357 | Implements slider position to x windows. |
| `_slider_position_to_x_default(position)` | 373 | Implements slider position to x default. |
| `xToSliderPosition(x)` | 460 | Translate X-coordinate to slider position. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `toggle_flagging()` | 192 | Toggle a keyframe at the given position. |
| `_handle_rect_for_position(position)` | 342 | Implements handle rect for position. |
| `handle_value_change(value)` | 480 | Handles value change. |
| `handle_slider_release()` | 483 | Handles slider release. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `_paint_custom_handle(painter)` | 103 | Implements paint custom handle. |
| `toggle_keyframe()` | 172 | Toggle a keyframe at the given position. |
| `paintEvent(event)` | 212 | Override the paintEvent to draw keyframe indicators, flag indicators, and tickmarks. |
| `_paint_windows(painter)` | 222 | Implements paint windows. |
| `_paint_default(painter)` | 279 | Implements paint default. |
| `mousePressEvent(event)` | 386 | Qt mouse-press event handler. |
| `_mouse_press_windows(x, y, clicked_position)` | 406 | Implements mouse press windows. |
| `_mouse_press_default(x, y, clicked_position)` | 432 | Implements mouse press default. |
| `mouseReleaseEvent(event)` | 456 | Qt mouse-release event handler. |
| `keyPressEvent(event)` | 496 | Qt key-press event handler. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `sync_marker_state(keyframes, flaggedframes)` | 51 | Synchronizes marker state. |
| `clear_marker_state()` | 56 | Clears marker state. |
| `sync_timeline_geometry()` | 85 | Synchronizes timeline geometry. |
| `update_zoomed_level(zoom_value)` | 133 | Updates the zoom level of the slider based on zoom_value. |

### State serialization

| Method | Line | Explanation |
| --- | --- | --- |
| `restore_viewer_focus()` | 487 | Restores viewer focus. |
