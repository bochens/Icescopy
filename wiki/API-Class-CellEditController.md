# API Class: `CellEditController`

Edit-workflow controller that coordinates selection, preview, and redraw behavior across many cells.

## Source

- Module: [`icescopy_cell_controller`](API-Module-icescopy-cell-controller)
- File: `src/icescopy_cell_controller.py`
- Line: `42`

## Inheritance

- Bases: `object`

## Purpose

Edit-workflow controller that coordinates selection, preview, and redraw behavior across many cells.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `SINGLE_EDIT_MODES` | 50 | Stores single edit modes. |
| `GRID_PREVIEW_MODES` | 51 | Stores grid preview modes. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `group_cell_ids` | `__init__` | 55 | Stores group cell ids. |
| `group_ordered_cell_ids` | `__init__` | 56 | Stores group ordered cell ids. |
| `group_reference_cells` | `__init__` | 57 | Stores group reference cells. |
| `main_window` | `__init__` | 54 | Stores main window. |
| `updating_preview_handle` | `__init__` | 58 | Stores updating preview handle. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window)` | 53 | Initializes the instance. |
| `reset()` | 60 | Resets internal state for this object. |
| `is_single_edit_mode(tool_mode=None)` | 66 | Returns whether single edit mode. |
| `is_group_edit_mode()` | 70 | Returns whether group edit mode. |
| `is_any_edit_mode(tool_mode=None)` | 73 | Returns whether any edit mode. |
| `uses_grid_preview()` | 77 | Returns whether grid preview. |
| `uses_grid_panel()` | 80 | Returns whether grid panel. |
| `uses_circle_panel()` | 89 | Returns whether circle panel. |
| `is_single_preview_mode()` | 92 | Returns whether single preview mode. |
| `selected_scene_items()` | 95 | Returns selected scene items. |
| `selected_scene_cell_ids()` | 98 | Returns selected scene cell ids. |
| `renumber_cell_items()` | 113 | Implements renumber cell items. |
| `reset_edit_chosen()` | 118 | Resets edit chosen. |
| `mark_edit_targets(cell_ids)` | 123 | Marks edit targets. |
| `get_target_items()` | 129 | Returns target items. |
| `get_edit_chosen_items()` | 140 | Returns edit chosen items. |
| `_principal_axes(points)` | 148 | Implements principal axes. |
| `anchor_to_current_image(cell_items)` | 176 | Build fresh scene items anchored to the current image slot. |
| `_anchored_geometry(item)` | 207 | Implements anchored geometry. |
| `redraw_current_cells(preserve_selection=True, force_scene_scan=False)` | 431 | Implements redraw current cells. |
| `redraw_interpolated_cells(frame_index, preview=False)` | 444 | Implements redraw interpolated cells. |
| `rebase_edit_preview_to_current_frame()` | 466 | Keep pinned edit previews attached to the same edit targets after frame changes. |
| `add_single_cell(circle_position, circle_pixel_position, circle_size)` | 498 | Implements add single cell. |
| `replace_active_edit_cell(circle_position, circle_pixel_position, circle_size)` | 514 | Implements replace active edit cell. |
| `delete_cell_by_id(cell_id)` | 557 | Implements delete cell by ID. |
| `set_group_cells_from_items(selected_items, preserve_existing=False)` | 578 | Sets group cells from items. |
| `enter_edit_mode(restored_mode=None)` | 594 | Enter the appropriate edit sub-mode from the current scene cell set. |
| `start_edit_choose()` | 627 | Starts edit choose. |
| `start_single_edit(cell_item)` | 640 | Starts single edit. |
| `start_group_edit(selected_items, preserve_preview=False)` | 644 | Starts group edit. |
| `infer_grid_parameters_from_cells(selected_items)` | 692 | Infer a best-fit grid from the selected items. |
| `_cluster_axis(values, radii)` | 730 | Implements cluster axis. |
| `_infer_spatial_order(selected_items)` | 753 | Return cell IDs ordered by their current geometric layout. |
| `_infer_group_reference(selected_items)` | 757 | Freeze the selected group's local reference frame for one edit session. |
| `float_preview()` | 934 | Implements float preview. |
| `pin_preview_from_cell_layout(selected_items)` | 950 | Pins preview from cell layout. |
| `pin_current_preview(log_change=False)` | 965 | Pins current preview. |
| `_preview_count()` | 1014 | Implements preview count. |
| `preview_capacity()` | 1023 | Implements preview capacity. |
| `get_preview_definitions()` | 1026 | Returns preview definitions. |
| `order_grid_add_definitions_for_cell_ids(definitions)` | 1067 | Orders grid add definitions for cell ids. |
| `get_preview_radii()` | 1085 | Returns preview radii. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `remove_preview_handle()` | 793 | Removes preview handle. |
| `ensure_preview_handle()` | 804 | Ensures preview handle. |
| `move_pinned_preview_to_scene_pos(scene_pos)` | 843 | Move a pinned preview without forcing users back into floating mode. |
| `cancel_preview(log_message=True)` | 878 | Cancels preview. |
| `apply_grid_add()` | 1129 | Applies grid add. |
| `apply_single_add()` | 1159 | Applies single add. |
| `apply_single_edit()` | 1179 | Applies single edit. |
| `apply_group_edit()` | 1204 | Applies group edit. |
| `handle_grid_apply_action()` | 1319 | Handles grid apply action. |
| `handle_circle_apply_action()` | 1325 | Handles circle apply action. |
| `handle_grid_cancel_action()` | 1331 | Handles grid cancel action. |
| `handle_circle_cancel_action()` | 1334 | Handles circle cancel action. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `handle_wheel_adjustment(event, wheel_delta)` | 1337 | Handles wheel adjustment. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `update_scene_selectable_state()` | 101 | Updates scene selectable state. |
| `clear_scene_selection(clear_group=True)` | 106 | Clears scene selection. |
| `clear_group_cells()` | 143 | Clears group cells. |
| `_sync_scene_items_from_models(source_items, preserve_selected_cell_ids=None, forced_edit_cell_ids=None, force_scene_scan=False)` | 216 | Implements sync scene items from models. |
| `_fast_sync_scene_items_for_preview(source_items, forced_edit_cell_ids=None)` | 382 | Implements fast sync scene items for preview. |
| `sync_preview_handle()` | 816 | Synchronizes preview handle. |
| `clear_preview()` | 868 | Clears preview. |
| `update_preview_from_scene_pos(scene_pos, pin=False, log_change=True)` | 988 | Updates preview from scene pos. |
| `update_preview()` | 1101 | Updates preview. |
| `update_grid_panel_state()` | 1256 | Updates grid panel state. |

### State serialization

| Method | Line | Explanation |
| --- | --- | --- |
| `restore_scene_cell_ids(cell_ids, sync_tool_panel=True)` | 173 | Restores scene cell ids. |
