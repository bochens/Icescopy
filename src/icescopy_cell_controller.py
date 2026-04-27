import numpy as np
import shiboken6
from PySide6.QtCore import QPointF, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsView

from icescopy_cell_items import CellCircle


class PreviewAnchorHandle(QGraphicsEllipseItem):
    """Drag handle for pinned grid/group previews.

    Floating previews follow the mouse directly, but once the preview is pinned
    we expose a small handle so users can reposition the whole pattern without
    having to re-enter floating mode.
    """

    def __init__(self, controller):
        super().__init__(-6, -6, 12, 12)
        self.controller = controller
        self.setZValue(10_000)
        self.setCursor(Qt.OpenHandCursor)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)

    def sync_size_from_preferences(self):
        size = max(2.0, float(getattr(self.controller.main_window, "preview_handle_size", 12.0)))
        half = size / 2.0
        self.setRect(-half, -half, size, size)

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.ItemPositionChange
            and not self.controller.updating_preview_handle
            and isinstance(value, QPointF)
        ):
            self.controller.move_pinned_preview_to_scene_pos(value)
        return super().itemChange(change, value)


class CellEditController:
    """Coordinate ROI add/edit/group-edit behavior across the view and tool panel.

    The main window still owns the underlying session data, but this controller
    centralizes the cell-edit intent so we do not keep re-implementing the
    same branching rules in the view, scene items, and tool-options panel.
    """

    SINGLE_EDIT_MODES = {"edit-choose", "edit-new"}
    GRID_PREVIEW_MODES = {"select", "edit-new", "grid", "edit-group"}

    def __init__(self, main_window):
        self.main_window = main_window
        self.group_cell_ids = []
        self.group_ordered_cell_ids = []
        self.group_reference_cells = {}
        self.updating_preview_handle = False

    def reset(self):
        self.group_cell_ids = []
        self.group_ordered_cell_ids = []
        self.group_reference_cells = {}
        self.updating_preview_handle = False

    def is_single_edit_mode(self, tool_mode=None):
        tool_mode = tool_mode or self.main_window.tool_mode
        return tool_mode in self.SINGLE_EDIT_MODES

    def is_group_edit_mode(self):
        return self.main_window.tool_mode == "edit-group"

    def is_any_edit_mode(self, tool_mode=None):
        tool_mode = tool_mode or self.main_window.tool_mode
        return self.is_single_edit_mode(tool_mode) or tool_mode == "edit-group"

    def uses_grid_preview(self):
        return self.main_window.tool_mode in self.GRID_PREVIEW_MODES

    def uses_grid_panel(self):
        if self.main_window.tool_mode == "grid":
            return True
        if self.main_window.tool_mode == "edit-group":
            return True
        if self.main_window.tool_mode == "edit-choose" and len(self.selected_scene_items()) > 1:
            return True
        return False

    def uses_circle_panel(self):
        return self.main_window.tool_mode in {"select", "edit-new"}

    def is_single_preview_mode(self):
        return self.main_window.tool_mode in {"select", "edit-new"}

    def selected_scene_items(self):
        return [item for item in self.main_window.scene.selectedItems() if isinstance(item, CellCircle)]

    def selected_scene_cell_ids(self):
        return sorted(item.cell_id for item in self.selected_scene_items())

    def update_scene_selectable_state(self):
        for item in self.main_window.scene.items():
            if isinstance(item, CellCircle):
                item.update_selectable_state()

    def clear_scene_selection(self, clear_group=True):
        if clear_group:
            self.clear_group_cells()
        for item in self.main_window.scene.items():
            if isinstance(item, CellCircle):
                item.setSelected(False)

    def reset_edit_chosen(self):
        for item in self.main_window.cell_items:
            item.edit_chosen = False
            item.update()

    def mark_edit_targets(self, cell_ids):
        number_set = set(cell_ids)
        for item in self.main_window.cell_items:
            item.edit_chosen = item.cell_id in number_set
            item.update()

    def get_target_items(self):
        if self.group_cell_ids:
            number_set = set(self.group_cell_ids)
            return [item for item in self.main_window.cell_items if item.cell_id in number_set]

        selected_items = self.selected_scene_items()
        if selected_items:
            return selected_items

        return [item for item in self.main_window.cell_items if item.edit_chosen]

    def get_edit_chosen_items(self):
        return [item for item in self.main_window.cell_items if item.edit_chosen]

    def clear_group_cells(self):
        self.group_cell_ids = []
        self.group_ordered_cell_ids = []
        self.group_reference_cells = {}

    def _principal_axes(self, points):
        centered = points - points.mean(axis=0)
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        primary_axis = np.array(vh[0], dtype=float)
        secondary_axis = np.array(vh[1], dtype=float)

        # SVD axes are sign-ambiguous. Canonicalize them in image coordinates so
        # left-to-right / top-to-bottom ordering stays stable instead of
        # occasionally flipping the inferred grid orientation.
        if abs(primary_axis[0]) >= abs(primary_axis[1]):
            if primary_axis[0] < 0:
                primary_axis *= -1
                secondary_axis *= -1
        elif primary_axis[1] < 0:
            primary_axis *= -1
            secondary_axis *= -1

        if abs(secondary_axis[1]) >= abs(secondary_axis[0]):
            if secondary_axis[1] < 0:
                secondary_axis *= -1
        elif secondary_axis[0] < 0:
            secondary_axis *= -1

        return centered, primary_axis, secondary_axis

    def restore_scene_cell_ids(self, cell_ids, sync_tool_panel=True):
        self.main_window.reselect_cell_ids(cell_ids, sync_tool_panel=sync_tool_panel)

    def anchor_to_current_image(self, cell_items):
        """Build fresh scene items anchored to the current image slot.

        The persistent ROI data lives in image-pixel coordinates. Scene items are
        disposable view objects that must be rebuilt whenever the current image
        slot moves or the current frame changes.
        """
        if not hasattr(self.main_window, "pixmap_item"):
            return cell_items

        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        anchored_items = []
        for item in cell_items:
            anchored_position = self.main_window.image_pixel_to_scene_coordinates(
                item.circle_pixel_positions[0],
                item.circle_pixel_positions[1],
                image_rect,
            )
            anchored_item = CellCircle(
                self.main_window,
                anchored_position,
                item.circle_sizes,
                item.circle_pixel_positions,
                item.cell_id,
            )
            anchored_item.edit_chosen = item.edit_chosen
            anchored_item.hover = item.hover
            anchored_item.pressed = item.pressed
            anchored_items.append(anchored_item)
        return anchored_items

    def _anchored_geometry(self, item):
        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        anchored_position = self.main_window.image_pixel_to_scene_coordinates(
            item.circle_pixel_positions[0],
            item.circle_pixel_positions[1],
            image_rect,
        )
        return anchored_position, item.circle_sizes, item.circle_pixel_positions, item.cell_id

    def _sync_scene_items_from_models(
        self,
        source_items,
        preserve_selected_cell_ids=None,
        forced_edit_cell_ids=None,
        force_scene_scan=False,
    ):
        if not hasattr(self.main_window, "pixmap_item"):
            self.main_window.cell_items = list(source_items)
            self.main_window.rendered_cell_items = []
            return

        preserve_selected_set = set(preserve_selected_cell_ids or [])
        forced_edit_set = set(forced_edit_cell_ids) if forced_edit_cell_ids is not None else None
        tracked_scene_items = [
            item
            for item in getattr(self.main_window, "rendered_cell_items", [])
            if isinstance(item, CellCircle) and item.scene() is self.main_window.scene
        ]
        requires_recovery_scan = bool(force_scene_scan)
        existing_scene_items = list(tracked_scene_items)
        if requires_recovery_scan:
            scene_cell_items = [
                item
                for item in self.main_window.scene.items()
                if isinstance(item, CellCircle)
            ]
            if existing_scene_items:
                seen_ids = {id(item) for item in existing_scene_items}
                for item in scene_cell_items:
                    if id(item) not in seen_ids:
                        existing_scene_items.append(item)
            else:
                existing_scene_items = scene_cell_items

        # Guard against accidental duplicate IDs in model input. Keep the first
        # instance per stable cell_id so scene sync cannot render duplicates.
        unique_source_items = []
        seen_source_cell_ids = set()
        duplicate_source_ids = []
        for source_item in source_items:
            try:
                source_key = int(source_item.cell_id)
            except (TypeError, ValueError):
                source_key = ("raw", source_item.cell_id)
            if source_key in seen_source_cell_ids:
                duplicate_source_ids.append(source_item.cell_id)
                continue
            seen_source_cell_ids.add(source_key)
            unique_source_items.append(source_item)
        source_items = unique_source_items
        if duplicate_source_ids:
            self.main_window.log(
                "Warning: duplicate cell IDs found during scene sync: "
                + ", ".join(str(cell_id) for cell_id in duplicate_source_ids)
            )

        existing_by_cell_id = {}
        for item in existing_scene_items:
            try:
                existing_by_cell_id[int(item.cell_id)] = item
            except (TypeError, ValueError):
                continue
        previous_selected_set = {
            item.cell_id
            for item in existing_scene_items
            if item.isSelected()
        }
        selection_changed = previous_selected_set != preserve_selected_set
        updated_items = []
        used_scene_items = set()
        source_cell_id_set = set()
        for source_item in source_items:
            try:
                source_cell_id_set.add(int(source_item.cell_id))
            except (TypeError, ValueError):
                continue
        reusable_scene_items = []
        for item in existing_scene_items:
            try:
                item_cell_id = int(item.cell_id)
            except (TypeError, ValueError):
                reusable_scene_items.append(item)
                continue
            if item_cell_id not in source_cell_id_set:
                reusable_scene_items.append(item)

        scene_blocker = QSignalBlocker(self.main_window.scene)
        try:
            for source_item in source_items:
                anchored_position, circle_size, pixel_position, cell_id = self._anchored_geometry(source_item)
                edit_chosen = source_item.edit_chosen
                if forced_edit_set is not None:
                    edit_chosen = cell_id in forced_edit_set
                try:
                    cell_key = int(cell_id)
                except (TypeError, ValueError):
                    cell_key = cell_id
                target_item = existing_by_cell_id.pop(cell_key, None)
                if target_item is not None:
                    target_item.sync_from_data(
                        anchored_position,
                        circle_size,
                        pixel_position,
                        cell_id,
                        edit_chosen=edit_chosen,
                        hover=False,
                        pressed=False,
                    )
                elif reusable_scene_items:
                    target_item = reusable_scene_items.pop(0)
                    target_item.sync_from_data(
                        anchored_position,
                        circle_size,
                        pixel_position,
                        cell_id,
                        edit_chosen=edit_chosen,
                        hover=False,
                        pressed=False,
                    )
                else:
                    target_item = CellCircle(
                        self.main_window,
                        anchored_position,
                        circle_size,
                        pixel_position,
                        cell_id,
                    )
                    target_item.edit_chosen = bool(edit_chosen)
                    target_item.hover = False
                    target_item.pressed = False
                    self.main_window.scene.addItem(target_item)
                # Selection state must be explicit after model<->scene remap.
                # Otherwise, re-used scene items can keep stale selected=True and
                # appear as "ghost" selections after deletes/reindexing.
                should_select = cell_id in preserve_selected_set
                if target_item.isSelected() != should_select:
                    target_item.setSelected(should_select)
                updated_items.append(target_item)
                used_scene_items.add(target_item)

            for stale_item in existing_scene_items:
                if stale_item in used_scene_items:
                    continue
                self.main_window.scene.removeItem(stale_item)
        finally:
            del scene_blocker

        self.main_window.rendered_cell_items = list(updated_items)
        self.main_window.cell_items = updated_items
        if (
            (not getattr(self.main_window, "preview_frame_update_in_progress", False))
            and getattr(self.main_window, "tool_mode", "") == "cursor"
        ):
            self.main_window.refresh_cursor_selection_info()
        if selection_changed:
            self.main_window.handle_scene_cell_selection_changed()

    def _fast_sync_scene_items_for_preview(self, source_items, forced_edit_cell_ids=None):
        if not hasattr(self.main_window, "pixmap_item"):
            return False

        tracked_scene_items = [
            item
            for item in getattr(self.main_window, "rendered_cell_items", [])
            if isinstance(item, CellCircle) and item.scene() is self.main_window.scene
        ]
        if len(tracked_scene_items) != len(source_items):
            return False

        try:
            for target_item, source_item in zip(tracked_scene_items, source_items):
                if int(target_item.cell_id) != int(source_item.cell_id):
                    return False
        except (TypeError, ValueError):
            return False

        forced_edit_set = set(forced_edit_cell_ids) if forced_edit_cell_ids is not None else None
        image_rect = self.main_window.pixmap_item.sceneBoundingRect()

        self.main_window.view.setUpdatesEnabled(False)
        try:
            for target_item, source_item in zip(tracked_scene_items, source_items):
                anchored_position = self.main_window.image_pixel_to_scene_coordinates(
                    source_item.circle_pixel_positions[0],
                    source_item.circle_pixel_positions[1],
                    image_rect,
                )
                edit_chosen = source_item.edit_chosen
                if forced_edit_set is not None:
                    edit_chosen = source_item.cell_id in forced_edit_set
                target_item.sync_from_data(
                    anchored_position,
                    source_item.circle_sizes,
                    source_item.circle_pixel_positions,
                    source_item.cell_id,
                    edit_chosen=edit_chosen,
                    hover=False,
                    pressed=False,
                )
        finally:
            self.main_window.view.setUpdatesEnabled(True)

        self.main_window.rendered_cell_items = list(tracked_scene_items)
        self.main_window.cell_items = list(tracked_scene_items)
        return True

    def redraw_current_cells(self, preserve_selection=True, force_scene_scan=False):
        selected_cell_ids = self.selected_scene_cell_ids() if preserve_selection else []
        self.main_window.view.setUpdatesEnabled(False)
        try:
            source_items = list(self.main_window.cell_items)
            self._sync_scene_items_from_models(
                source_items,
                selected_cell_ids,
                force_scene_scan=force_scene_scan,
            )
        finally:
            self.main_window.view.setUpdatesEnabled(True)

    def redraw_interpolated_cells(self, frame_index, preview=False):
        selected_cell_ids = [] if preview else self.selected_scene_cell_ids()
        edit_target_numbers = [item.cell_id for item in self.main_window.cell_items if item.edit_chosen]
        if self.group_cell_ids:
            edit_target_numbers = list(self.group_cell_ids)
        forced_edit_ids = set(edit_target_numbers) if edit_target_numbers else None
        interpolated_items = self.main_window.keyframe_interpolation(frame_index)
        if preview and self._fast_sync_scene_items_for_preview(
            interpolated_items,
            forced_edit_cell_ids=forced_edit_ids,
        ):
            return
        self.main_window.view.setUpdatesEnabled(False)
        try:
            self._sync_scene_items_from_models(
                interpolated_items,
                selected_cell_ids,
                forced_edit_cell_ids=forced_edit_ids,
            )
        finally:
            self.main_window.view.setUpdatesEnabled(True)

    def rebase_edit_preview_to_current_frame(self):
        """Keep pinned edit previews attached to the same edit targets after frame changes."""
        if self.main_window.grid_preview_origin_pixels is None:
            return
        if self.main_window.grid_preview_floating:
            return

        if self.main_window.tool_mode == "edit-new":
            target_items = self.get_edit_chosen_items()
            if not target_items:
                return
            target_item = target_items[0]
            self.main_window.grid_preview_origin_pixels = (
                float(target_item.circle_pixel_positions[0]),
                float(target_item.circle_pixel_positions[1]),
            )
            self.update_preview()
            return

        if self.is_group_edit_mode():
            target_items = self.get_target_items()
            if not target_items:
                return
            ordered_numbers = self.group_ordered_cell_ids or self._infer_spatial_order(target_items)
            number_to_item = {item.cell_id: item for item in target_items}
            origin_item = number_to_item.get(ordered_numbers[0], target_items[0])
            self.main_window.grid_preview_origin_pixels = (
                float(origin_item.circle_pixel_positions[0]),
                float(origin_item.circle_pixel_positions[1]),
            )
            self.update_preview()

    def add_single_cell(self, circle_position, circle_pixel_position, circle_size):
        cell_id = self.main_window.allocate_cell_id()
        new_item = CellCircle(
            self.main_window,
            circle_position,
            circle_size,
            circle_pixel_position,
            cell_id,
        )
        self.main_window.cell_items.append(new_item)
        self.redraw_current_cells()
        self.main_window.add_cell_item_to_keyframes([new_item])
        self.main_window.ensure_cell_registry_matches_scene_cells()
        self.main_window.refresh_cells_panel()
        return cell_id

    def replace_active_edit_cell(self, circle_position, circle_pixel_position, circle_size):
        cell_id = None
        for item in self.main_window.cell_items:
            if item.edit_chosen:
                cell_id = item.cell_id
                break

        if cell_id is None:
            selected_items = self.selected_scene_items()
            if selected_items:
                cell_id = selected_items[0].cell_id

        if cell_id is None:
            return None

        for item in self.main_window.cell_items:
            item.edit_chosen = False

        cell_index = next(
            (
                index
                for index, item in enumerate(self.main_window.cell_items)
                if item.cell_id == cell_id
            ),
            None,
        )
        if cell_index is None:
            return None

        target_item = self.main_window.cell_items[cell_index]
        target_item.sync_from_data(
            circle_position,
            circle_size,
            circle_pixel_position,
            cell_id,
            edit_chosen=False,
            hover=False,
            pressed=False,
        )
        self.redraw_current_cells(force_scene_scan=True)
        self.main_window.edit_current_keyframe_cell_item()
        return cell_id

    def delete_cell_by_id(self, cell_id):
        cell_index = next(
            (
                index
                for index, item in enumerate(self.main_window.cell_items)
                if item.cell_id == cell_id
            ),
            None,
        )
        if cell_index is None:
            return None

        removed_item = self.main_window.cell_items.pop(cell_index)
        self.redraw_current_cells(preserve_selection=False)
        self.main_window.delete_cell_item_to_keyframes(cell_id)
        self.main_window.prune_analysis_results_for_deleted_cells([cell_id])
        self.main_window.ensure_cell_registry_matches_scene_cells()
        self.main_window.recompute_next_cell_id(preserve_if_larger=False)
        self.main_window.refresh_cells_panel()
        return removed_item

    def set_group_cells_from_items(self, selected_items, preserve_existing=False):
        selected_items = list(selected_items)
        cell_ids = sorted(item.cell_id for item in selected_items)
        if (
            preserve_existing
            and cell_ids == self.group_cell_ids
            and self.group_ordered_cell_ids
            and self.group_reference_cells
        ):
            return

        ordered_numbers, reference_cells = self._infer_group_reference(selected_items)
        self.group_cell_ids = cell_ids
        self.group_ordered_cell_ids = ordered_numbers
        self.group_reference_cells = dict(reference_cells)

    def enter_edit_mode(self, restored_mode=None):
        """Enter the appropriate edit sub-mode from the current scene cell set."""
        selected_items = self.selected_scene_items()
        self.main_window.view.setDragMode(QGraphicsView.NoDrag)

        if restored_mode == "edit-new" and any(item.edit_chosen for item in self.main_window.cell_items):
            self.main_window.tool_mode = "edit-new"
            self.main_window.set_view_cursor_shape(Qt.CrossCursor)
            self.main_window.tool_status_label.setText("Edit Cell")
            self.main_window.sync_tool_options_panel()
            return

        if restored_mode == "edit-group":
            if self.group_cell_ids:
                stored_items = [
                    item for item in self.main_window.cell_items
                    if item.cell_id in set(self.group_cell_ids)
                ]
                if stored_items:
                    self.start_group_edit(stored_items, preserve_preview=True)
                    return
            chosen_items = self.get_edit_chosen_items()
            if chosen_items:
                self.start_group_edit(chosen_items, preserve_preview=True)
                return

        if len(selected_items) > 1:
            self.start_group_edit(selected_items)
        elif len(selected_items) == 1:
            self.start_single_edit(selected_items[0])
        else:
            self.start_edit_choose()

    def start_edit_choose(self):
        self.clear_group_cells()
        self.main_window.tool_mode = "edit-choose"
        # Before anything is selected, Edit should behave like Cursor cell picking.
        # so users can rubber-band a group and immediately transition into edit.
        # Use pointing hand to match Delete-style "pick an existing circle".
        self.main_window.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.main_window.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.main_window.set_view_cursor_shape(Qt.PointingHandCursor)
        self.main_window.tool_status_label.setText("Edit Cell")
        self.main_window.update_cell_items_selectable_state()
        self.main_window.sync_tool_options_panel()

    def start_single_edit(self, cell_item):
        self.clear_group_cells()
        self.main_window.activate_edit_cell_item(cell_item)

    def start_group_edit(self, selected_items, preserve_preview=False):
        # Multi-cell edit uses a grid-like placement preview, but the edit
        # controls are relative deltas. Positions follow the inferred pattern
        # while per-circle radii stay tied to each selected item's own base
        # size, so resizing a mixed group does not flatten everything.
        if preserve_preview:
            radius_delta = float(getattr(self.main_window, "edit_group_radius_delta", 0.0))
            hpitch_delta = float(getattr(self.main_window, "edit_group_horizontal_pitch_delta", 0.0))
            vpitch_delta = float(getattr(self.main_window, "edit_group_vertical_pitch_delta", 0.0))
            rotation_delta = float(getattr(self.main_window, "edit_group_rotation_delta", 0.0))
        else:
            radius_delta = 0.0
            hpitch_delta = 0.0
            vpitch_delta = 0.0
            rotation_delta = 0.0

        self.set_group_cells_from_items(selected_items, preserve_existing=preserve_preview)
        self.mark_edit_targets(self.group_cell_ids)
        self.infer_grid_parameters_from_cells(selected_items)
        self.main_window.edit_group_base_radii_by_number = {
            item.cell_id: float(item.circle_sizes)
            for item in selected_items
        }
        self.main_window.edit_group_base_radius = float(self.main_window.circle_radius)
        self.main_window.edit_group_radius_delta = radius_delta
        self.main_window.edit_group_base_horizontal_pitch = float(self.main_window.grid_horizontal_pitch)
        self.main_window.edit_group_base_vertical_pitch = float(self.main_window.grid_vertical_pitch)
        self.main_window.edit_group_base_rotation_degrees = float(self.main_window.grid_rotation_degrees)
        self.main_window.edit_group_horizontal_pitch_delta = hpitch_delta
        self.main_window.edit_group_vertical_pitch_delta = vpitch_delta
        self.main_window.edit_group_rotation_delta = rotation_delta
        self.main_window.circle_radius = max(1.0, self.main_window.edit_group_base_radius + self.main_window.edit_group_radius_delta)
        self.main_window.grid_horizontal_pitch = max(0.1, self.main_window.edit_group_base_horizontal_pitch + self.main_window.edit_group_horizontal_pitch_delta)
        self.main_window.grid_vertical_pitch = max(0.1, self.main_window.edit_group_base_vertical_pitch + self.main_window.edit_group_vertical_pitch_delta)
        self.main_window.grid_rotation_degrees = max(
            -180.0,
            min(180.0, self.main_window.edit_group_base_rotation_degrees + self.main_window.edit_group_rotation_delta),
        )
        self.main_window.tool_mode = "edit-group"
        self.main_window.set_view_cursor_shape(Qt.CrossCursor)
        self.main_window.tool_status_label.setText("Edit Cell Group")
        if not preserve_preview or self.main_window.grid_preview_origin_pixels is None:
            self.pin_preview_from_cell_layout(selected_items)
        # Group edit tracks its targets through edit_chosen/group ids rather than
        # live Qt scene selection, so the visual language matches single-edit mode.
        self.clear_scene_selection(clear_group=False)
        self.main_window.sync_tool_options_panel()

    def infer_grid_parameters_from_cells(self, selected_items):
        """Infer a best-fit grid from the selected items.

        This keeps group-edit aligned with the currently selected pattern rather
        than forcing users to rebuild the spacing from scratch every time.
        """
        selected_items = list(selected_items)
        if not selected_items:
            return

        points = np.array([item.circle_pixel_positions for item in selected_items], dtype=float)
        radii = np.array([item.circle_sizes for item in selected_items], dtype=float)

        if len(points) == 1:
            radius = float(radii[0])
            self.main_window.grid_rows = 1
            self.main_window.grid_columns = 1
            self.main_window.grid_horizontal_pitch = max(radius * 2.0, 1.0)
            self.main_window.grid_vertical_pitch = max(radius * 2.0, 1.0)
            self.main_window.grid_rotation_degrees = 0.0
            self.main_window.circle_radius = radius
            return

        centered, primary_axis, secondary_axis = self._principal_axes(points)
        projected_x = centered @ primary_axis
        projected_y = centered @ secondary_axis

        x_centers, h_pitch = self._cluster_axis(projected_x, radii)
        y_centers, v_pitch = self._cluster_axis(projected_y, radii)
        rotation = float(np.degrees(np.arctan2(primary_axis[1], primary_axis[0])))

        self.main_window.grid_columns = max(1, len(x_centers))
        self.main_window.grid_rows = max(1, len(y_centers))
        self.main_window.grid_horizontal_pitch = max(h_pitch, 1.0)
        self.main_window.grid_vertical_pitch = max(v_pitch, 1.0)
        self.main_window.grid_rotation_degrees = rotation
        self.main_window.circle_radius = float(np.mean(radii))

    def _cluster_axis(self, values, radii):
        sorted_values = np.sort(values)
        if len(sorted_values) <= 1:
            return [float(sorted_values[0])], 0.0

        diffs = np.diff(sorted_values)
        positive_diffs = diffs[np.abs(diffs) > 1e-6]
        if len(positive_diffs) == 0:
            return [float(np.mean(sorted_values))], 0.0

        base_pitch = float(np.median(np.abs(positive_diffs)))
        tolerance = max(base_pitch * 0.35, float(np.mean(radii)) * 0.75, 2.0)
        clusters = [[float(sorted_values[0])]]
        for value in sorted_values[1:]:
            if abs(value - clusters[-1][-1]) <= tolerance:
                clusters[-1].append(float(value))
            else:
                clusters.append([float(value)])

        centers = [float(np.mean(cluster)) for cluster in clusters]
        pitch = float(np.median(np.diff(centers))) if len(centers) > 1 else base_pitch
        return sorted(centers), abs(pitch)

    def _infer_spatial_order(self, selected_items):
        """Return cell IDs ordered by their current geometric layout."""
        return self._infer_group_reference(selected_items)[0]

    def _infer_group_reference(self, selected_items):
        """Freeze the selected group's local reference frame for one edit session.

        Group edit should preserve the same logical circle identity even if the
        user rotates or reshapes the preview. We therefore compute a single
        row/column reference once when edit starts and keep using that mapping
        until the edit session ends.
        """
        if not selected_items:
            return [], {}
        if len(selected_items) == 1:
            cell_id = selected_items[0].cell_id
            return [cell_id], {cell_id: (0, 0)}

        points = np.array([item.circle_pixel_positions for item in selected_items], dtype=float)
        radii = np.array([item.circle_sizes for item in selected_items], dtype=float)
        centered, primary_axis, secondary_axis = self._principal_axes(points)
        projected_x = centered @ primary_axis
        projected_y = centered @ secondary_axis
        x_centers, _ = self._cluster_axis(projected_x, radii)
        y_centers, _ = self._cluster_axis(projected_y, radii)

        assignments = []
        for item, proj_x, proj_y in zip(selected_items, projected_x, projected_y):
            row_index = min(range(len(y_centers)), key=lambda idx: abs(proj_y - y_centers[idx]))
            col_index = min(range(len(x_centers)), key=lambda idx: abs(proj_x - x_centers[idx]))
            assignments.append((row_index, col_index, float(proj_y), float(proj_x), item.cell_id))

        ordered_assignments = sorted(assignments)
        ordered_numbers = [cell_id for _, _, _, _, cell_id in ordered_assignments]
        reference_cells = {
            cell_id: (row_index, col_index)
            for row_index, col_index, _, _, cell_id in ordered_assignments
        }
        return ordered_numbers, reference_cells

    def remove_preview_handle(self):
        handle = getattr(self.main_window, "grid_preview_handle_item", None)
        if handle is None:
            return
        try:
            if shiboken6.isValid(handle) and handle.scene() is self.main_window.scene:
                self.main_window.scene.removeItem(handle)
        except RuntimeError:
            pass
        self.main_window.grid_preview_handle_item = None

    def ensure_preview_handle(self):
        handle = getattr(self.main_window, "grid_preview_handle_item", None)
        if handle is None:
            handle = PreviewAnchorHandle(self)
            outline_color = self.main_window.get_qcolor(self.main_window.grid_preview_outline_color)
            handle.setPen(QPen(outline_color, 1.5))
            handle.setBrush(QBrush(outline_color))
            self.main_window.scene.addItem(handle)
            self.main_window.grid_preview_handle_item = handle
        handle.sync_size_from_preferences()
        return handle

    def sync_preview_handle(self):
        if (
            not self.uses_grid_preview()
            or self.main_window.grid_preview_floating
            or self.main_window.grid_preview_origin_pixels is None
            or not hasattr(self.main_window, "pixmap_item")
        ):
            self.remove_preview_handle()
            return

        handle = self.ensure_preview_handle()
        outline_color = self.main_window.get_qcolor(self.main_window.grid_preview_outline_color)
        handle.setPen(QPen(outline_color, 1.5))
        handle.setBrush(QBrush(outline_color))
        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        offset_x = float(getattr(self.main_window, "preview_offset_x", 0.0))
        offset_y = float(getattr(self.main_window, "preview_offset_y", 0.0))
        anchor_x, anchor_y = self.main_window.image_pixel_to_scene_coordinates(
            self.main_window.grid_preview_origin_pixels[0] + offset_x,
            self.main_window.grid_preview_origin_pixels[1] + offset_y,
            image_rect,
        )
        anchor_scene_pos = QPointF(anchor_x, anchor_y)
        self.updating_preview_handle = True
        handle.setPos(anchor_scene_pos)
        self.updating_preview_handle = False

    def move_pinned_preview_to_scene_pos(self, scene_pos):
        """Move a pinned preview without forcing users back into floating mode.

        The handle represents the effective preview location after X/Y offset
        is applied, so dragging it should preserve the current offset values
        and move the underlying origin accordingly.
        """
        if not hasattr(self.main_window, "pixmap_item"):
            return

        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        offset_x = float(getattr(self.main_window, "preview_offset_x", 0.0))
        offset_y = float(getattr(self.main_window, "preview_offset_y", 0.0))
        origin_scene_pos = QPointF(
            scene_pos.x() - offset_x,
            scene_pos.y() - offset_y,
        )
        # Keep the origin inside the current image bounds while preserving the
        # user-entered offset as a separate translation control.
        clamped_scene_pos = QPointF(
            min(max(origin_scene_pos.x(), image_rect.left()), image_rect.right()),
            min(max(origin_scene_pos.y(), image_rect.top()), image_rect.bottom()),
        )
        self.update_preview_from_scene_pos(clamped_scene_pos, pin=True, log_change=False)

    def clear_preview(self):
        for item in list(self.main_window.grid_preview_items):
            try:
                if shiboken6.isValid(item) and item.scene() is self.main_window.scene:
                    self.main_window.scene.removeItem(item)
            except RuntimeError:
                pass
        self.main_window.grid_preview_items = []
        self.update_grid_panel_state()

    def cancel_preview(self, log_message=True):
        current_tool_mode = self.main_window.tool_mode
        was_floating = bool(self.main_window.grid_preview_floating)
        had_preview = bool(self.main_window.grid_preview_items) or (self.main_window.grid_preview_origin_pixels is not None)
        self.main_window.grid_preview_origin_pixels = None
        self.main_window.grid_preview_floating = True
        self.main_window.preview_offset_x = 0.0
        self.main_window.preview_offset_y = 0.0
        self.clear_preview()
        self.remove_preview_handle()

        if self.is_group_edit_mode():
            # Cancelling group edit returns to plain edit mode but keeps the app
            # in the broader edit workflow instead of kicking all the way back
            # to Cursor.
            self.main_window.reset_cell_items_edit_chosen()
            self.main_window.tool_mode = "edit-choose"
            self.main_window.set_view_cursor_shape(Qt.PointingHandCursor)
            self.main_window.tool_status_label.setText("Edit Cell")
            self.clear_group_cells()
            self.main_window.sync_tool_options_panel()
            if had_preview and log_message:
                self.main_window.log("Cancel group edit preview")
            return

        if self.main_window.tool_mode == "edit-new":
            self.main_window.reset_cell_items_edit_chosen()
            self.main_window.tool_mode = "edit-choose"
            self.main_window.set_view_cursor_shape(Qt.PointingHandCursor)
            self.main_window.tool_status_label.setText("Edit Cell")
            self.main_window.restore_after_edit_mode()
            self.main_window.sync_tool_options_panel()
            if had_preview and log_message:
                self.main_window.log("Cancel Edit")
            return

        if current_tool_mode == "select":
            if was_floating:
                self.main_window.apply_cursor_tool_ui()
            else:
                self.main_window.sync_tool_options_panel()
            if log_message and (had_preview or was_floating):
                self.main_window.log("Cancel Cell Placement")
            return

        if current_tool_mode == "grid":
            if was_floating:
                self.main_window.apply_cursor_tool_ui()
            else:
                self.main_window.sync_tool_options_panel()
            if log_message and (had_preview or was_floating):
                self.main_window.log("Cancel Grid")
            return

    def float_preview(self):
        self.main_window.grid_preview_floating = True
        self.main_window.preview_offset_x = 0.0
        self.main_window.preview_offset_y = 0.0
        self.remove_preview_handle()
        self.main_window.sync_tool_options_panel()
        self.update_grid_panel_state()
        if self.is_group_edit_mode():
            self.main_window.log("Group preview floating")
        elif self.main_window.tool_mode == "edit-new":
            self.main_window.log("Edit preview floating")
        elif self.main_window.tool_mode == "select":
            self.main_window.log("Cell preview floating")
        else:
            self.main_window.log("Grid floating")

    def pin_preview_from_cell_layout(self, selected_items):
        selected_items = list(selected_items)
        if not selected_items or not hasattr(self.main_window, "pixmap_item"):
            return

        ordered_numbers = self.group_ordered_cell_ids or self._infer_spatial_order(selected_items)
        number_to_item = {item.cell_id: item for item in selected_items}
        origin_item = number_to_item.get(ordered_numbers[0], selected_items[0])
        origin_x = float(origin_item.circle_pixel_positions[0])
        origin_y = float(origin_item.circle_pixel_positions[1])
        self.main_window.grid_preview_origin_pixels = (origin_x, origin_y)
        self.main_window.grid_preview_floating = False
        self.update_preview()
        self.main_window.sync_active_preview_coordinate_controls()

    def pin_current_preview(self, log_change=False):
        if not self.main_window.grid_preview_items or self.main_window.grid_preview_origin_pixels is None:
            return False
        if not self.main_window.grid_preview_floating:
            return True

        self.main_window.grid_preview_floating = False
        self.update_preview()
        self.main_window.sync_active_preview_coordinate_controls()

        if log_change:
            x_pixel, y_pixel = self.main_window.grid_preview_origin_pixels
            if self.is_group_edit_mode():
                action = "Pin group preview"
            elif self.main_window.tool_mode == "edit-new":
                action = "Pin edit preview"
            elif self.main_window.tool_mode == "select":
                action = "Pin cell preview"
            else:
                action = "Pin grid"
            self.main_window.log(f"{action} at ({int(x_pixel)}, {int(y_pixel)})")
        return True

    def update_preview_from_scene_pos(self, scene_pos, pin=False, log_change=True):
        if not self.uses_grid_preview() or not hasattr(self.main_window, "pixmap_item"):
            return
        if self.main_window.is_pan_interaction_active():
            return
        if (not pin) and (not self.main_window.grid_preview_floating):
            return

        current_image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        if not current_image_rect.contains(scene_pos):
            if self.main_window.grid_preview_floating:
                self.main_window.grid_preview_origin_pixels = None
                self.clear_preview()
                self.main_window.sync_active_preview_coordinate_controls()
            return

        x_pixel, y_pixel = self.main_window.scene_to_image_pixel_coordinates(scene_pos, current_image_rect)
        self.main_window.grid_preview_origin_pixels = (x_pixel, y_pixel)
        if pin:
            self.main_window.grid_preview_floating = False
        self.update_preview()
        self.main_window.sync_active_preview_coordinate_controls()
        if pin and log_change:
            action = "Pin group preview" if self.is_group_edit_mode() else "Pin grid"
            self.main_window.log(f"{action} at ({int(x_pixel)}, {int(y_pixel)})")

    def _preview_count(self):
        if self.main_window.tool_mode in {"select", "edit-new"}:
            return 1
        if self.main_window.tool_mode == "grid":
            return self.main_window.grid_rows * self.main_window.grid_columns
        if self.is_group_edit_mode():
            return len(self.group_ordered_cell_ids)
        return 0

    def preview_capacity(self):
        return self.main_window.grid_rows * self.main_window.grid_columns

    def get_preview_definitions(self):
        if self.main_window.grid_preview_origin_pixels is None or not hasattr(self.main_window, "pixmap_item"):
            return []

        offset_x = float(getattr(self.main_window, "preview_offset_x", 0.0))
        offset_y = float(getattr(self.main_window, "preview_offset_y", 0.0))
        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        theta = np.deg2rad(self.main_window.grid_rotation_degrees)
        cos_theta = float(np.cos(theta))
        sin_theta = float(np.sin(theta))
        definitions = []

        if self.is_group_edit_mode():
            for cell_id in self.group_ordered_cell_ids:
                row, col = self.group_reference_cells.get(cell_id, (0, 0))
                dx = float(col) * self.main_window.grid_horizontal_pitch
                dy = float(row) * self.main_window.grid_vertical_pitch
                x_pixel = self.main_window.grid_preview_origin_pixels[0] + offset_x + dx * cos_theta - dy * sin_theta
                y_pixel = self.main_window.grid_preview_origin_pixels[1] + offset_y + dx * sin_theta + dy * cos_theta
                scene_pos = self.main_window.image_pixel_to_scene_coordinates(x_pixel, y_pixel, image_rect)
                definitions.append((scene_pos, (x_pixel, y_pixel)))
            return definitions

        preview_count = self._preview_count()
        if preview_count <= 0:
            return []

        position_index = 0
        for row in range(self.main_window.grid_rows):
            for col in range(self.main_window.grid_columns):
                if position_index >= preview_count:
                    break
                dx = col * self.main_window.grid_horizontal_pitch
                dy = row * self.main_window.grid_vertical_pitch
                x_pixel = self.main_window.grid_preview_origin_pixels[0] + offset_x + dx * cos_theta - dy * sin_theta
                y_pixel = self.main_window.grid_preview_origin_pixels[1] + offset_y + dx * sin_theta + dy * cos_theta
                scene_pos = self.main_window.image_pixel_to_scene_coordinates(x_pixel, y_pixel, image_rect)
                definitions.append((scene_pos, (x_pixel, y_pixel)))
                position_index += 1
        return definitions

    def order_grid_add_definitions_for_cell_ids(self, definitions):
        ordered_definitions = list(definitions)
        if getattr(self.main_window, "grid_cell_id_direction", "left_to_right") != "top_to_bottom":
            return ordered_definitions

        row_count = int(getattr(self.main_window, "grid_rows", 0))
        column_count = int(getattr(self.main_window, "grid_columns", 0))
        if row_count <= 0 or column_count <= 0:
            return ordered_definitions

        reordered = []
        for col in range(column_count):
            for row in range(row_count):
                index = row * column_count + col
                if 0 <= index < len(ordered_definitions):
                    reordered.append(ordered_definitions[index])
        return reordered if reordered else ordered_definitions

    def get_preview_radii(self):
        preview_count = self._preview_count()
        if preview_count <= 0:
            return []

        if not self.is_group_edit_mode():
            return [float(self.main_window.circle_radius)] * preview_count

        radius_delta = float(getattr(self.main_window, "edit_group_radius_delta", 0.0))
        base_radii = getattr(self.main_window, "edit_group_base_radii_by_number", {}) or {}
        radii = []
        for cell_id in self.group_ordered_cell_ids[:preview_count]:
            base_radius = float(base_radii.get(cell_id, self.main_window.edit_group_base_radius or self.main_window.circle_radius))
            radii.append(max(1.0, base_radius + radius_delta))
        return radii

    def update_preview(self):
        self.clear_preview()
        if not self.uses_grid_preview():
            self.remove_preview_handle()
            return

        preview_radii = self.get_preview_radii()
        for index, (scene_pos, _pixel_pos) in enumerate(self.get_preview_definitions()):
            outline_color = self.main_window.get_qcolor(self.main_window.grid_preview_outline_color)
            fill_color = self.main_window.get_qcolor(self.main_window.grid_preview_fill_color)
            preview_radius = (
                preview_radii[index]
                if index < len(preview_radii)
                else float(self.main_window.circle_radius)
            )
            preview_item = self.main_window.scene.addEllipse(
                scene_pos[0] - preview_radius,
                scene_pos[1] - preview_radius,
                2 * preview_radius,
                2 * preview_radius,
                QPen(outline_color, 1, Qt.DashLine),
                QBrush(fill_color),
            )
            self.main_window.grid_preview_items.append(preview_item)

        self.sync_preview_handle()
        self.update_grid_panel_state()

    def apply_grid_add(self):
        definitions = self.get_preview_definitions()
        if not definitions:
            self.main_window.log("Move over the current image before applying the grid")
            return

        before_state = self.main_window.capture_cell_state()
        added_items = []
        ordered_definitions = self.order_grid_add_definitions_for_cell_ids(definitions)
        for scene_pos, pixel_pos in ordered_definitions:
            cell_id = self.main_window.allocate_cell_id()
            new_item = CellCircle(
                self.main_window,
                scene_pos,
                self.main_window.circle_radius,
                pixel_pos,
                cell_id,
            )
            self.main_window.cell_items.append(new_item)
            added_items.append(new_item)

        self.main_window.displayMarkedRegions()
        self.main_window.add_cell_item_to_keyframes(added_items)
        self.main_window.ensure_cell_registry_matches_scene_cells()
        self.main_window.refresh_cells_panel()
        self.main_window.push_cell_history("Add Grid", before_state)
        self.main_window.log(f"Add {len(definitions)} grid cells")
        self.cancel_preview(log_message=False)
        self.main_window.finalize_tool_mode_after_commit()

    def apply_single_add(self):
        definitions = self.get_preview_definitions()
        if not definitions:
            self.main_window.log("Move over the current image before applying the cell preview")
            return

        before_state = self.main_window.capture_cell_state()
        scene_pos, pixel_pos = definitions[0]
        cell_id = self.add_single_cell(
            scene_pos,
            pixel_pos,
            self.main_window.circle_radius,
        )
        self.main_window.push_cell_history("Add Cell", before_state)
        self.main_window.log(
            f"Add cell {cell_id} at ({int(pixel_pos[0])}, {int(pixel_pos[1])}); Circle size: {self.main_window.circle_radius:g}"
        )
        self.cancel_preview(log_message=False)
        self.main_window.finalize_tool_mode_after_commit()

    def apply_single_edit(self):
        definitions = self.get_preview_definitions()
        if not definitions:
            self.main_window.log("Pin the edited circle on the current image before applying")
            return

        before_state = self.main_window.capture_cell_state()
        scene_pos, pixel_pos = definitions[0]
        cell_id = self.replace_active_edit_cell(
            scene_pos,
            pixel_pos,
            self.main_window.circle_radius,
        )
        if cell_id is None:
            return

        self.main_window.push_cell_history("Edit Cell", before_state)
        self.main_window.log(
            f"Updated cell {cell_id} to ({int(pixel_pos[0])}, {int(pixel_pos[1])}); Circle size: {self.main_window.circle_radius:g}"
        )
        self.main_window.reset_cell_items_edit_chosen()
        self.main_window.restore_after_edit_mode()
        self.cancel_preview(log_message=False)
        self.main_window.finalize_tool_mode_after_commit()

    def apply_group_edit(self):
        if not self.group_ordered_cell_ids:
            self.main_window.log("Select circles before applying group edit")
            return

        definitions = self.get_preview_definitions()
        if len(definitions) < len(self.group_ordered_cell_ids):
            self.main_window.log("Pin the group preview on the current image before applying")
            return

        before_state = self.main_window.capture_cell_state()
        image_rect = self.main_window.pixmap_item.sceneBoundingRect()
        # Re-map the selected circles by spatial order, not cell_id
        # order, so the lifted pattern redraws in the same geometric sequence
        # the user selected on screen.
        number_to_position = {
            cell_id: pixel_pos
            for cell_id, (_scene_pos, pixel_pos) in zip(self.group_ordered_cell_ids, definitions)
        }
        radius_delta = float(getattr(self.main_window, "edit_group_radius_delta", 0.0))
        base_radii = getattr(self.main_window, "edit_group_base_radii_by_number", {}) or {}

        for item in self.main_window.cell_items:
            if item.cell_id in number_to_position:
                pixel_pos = number_to_position[item.cell_id]
                updated_radius = max(1.0, float(base_radii.get(item.cell_id, item.circle_sizes)) + radius_delta)
                anchored_position = self.main_window.image_pixel_to_scene_coordinates(
                    pixel_pos[0],
                    pixel_pos[1],
                    image_rect,
                )
                item.sync_from_data(
                    anchored_position,
                    updated_radius,
                    pixel_pos,
                    item.cell_id,
                    edit_chosen=True,
                    hover=False,
                    pressed=False,
                )

        selected_cell_ids = list(self.group_cell_ids)
        self.redraw_current_cells(force_scene_scan=True)
        self.main_window.edit_current_keyframe_cell_item()
        self.main_window.reset_cell_items_edit_chosen()
        self.main_window.reselect_cell_ids(selected_cell_ids)
        self.main_window.push_cell_history("Edit Cell Group", before_state)
        self.main_window.log("Redraw selected group from current grid settings")
        self.clear_group_cells()
        self.cancel_preview(log_message=False)
        self.main_window.finalize_tool_mode_after_commit()

    def update_grid_panel_state(self):
        if not hasattr(self.main_window, "tool_options_stack"):
            return

        is_group_edit = self.is_group_edit_mode()
        has_preview = bool(self.main_window.grid_preview_items)
        is_pinned = not self.main_window.grid_preview_floating

        if self.is_single_preview_mode():
            controls = self.main_window.current_circle_controls()
            if self.main_window.tool_mode == "edit-new":
                if is_pinned:
                    hint = "Pinned edit preview. Drag the handle or adjust Radius, X Offset, and Y Offset, then click Apply or press Enter. Float returns to mouse placement."
                else:
                    hint = "Move the lifted circle over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
            else:
                if is_pinned:
                    hint = "Pinned circle preview. Drag the handle or adjust Radius, X, and Y, then click Apply or press Enter. Float returns to mouse placement."
                else:
                    hint = "Move the preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
            controls["hint"].setText(hint)
            controls["apply"].setEnabled(has_preview and is_pinned)
            controls["float"].setEnabled(has_preview and is_pinned)
            controls["cancel"].setEnabled(has_preview or self.main_window.tool_mode == "edit-new")
            return

        controls = self.main_window.current_grid_controls()
        if controls.get("rows") is not None:
            controls["rows"].setEnabled(True)
        if controls.get("cols") is not None:
            controls["cols"].setEnabled(True)
        controls["hpitch"].setEnabled(True)
        controls["vpitch"].setEnabled(True)
        controls["rotation"].setEnabled(True)
        controls["radius"].setEnabled(True)

        controls["apply"].setText("Apply")
        controls["float"].show()
        controls["cancel"].setText("Cancel")

        if is_group_edit:
            if is_pinned:
                hint = "Pinned group preview. Drag the handle or adjust radius delta, pitch delta, tilt delta, X Offset, and Y Offset, then click Apply or press Enter. Float returns to mouse placement."
            else:
                hint = "Move the group preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
            controls["hint"].setText(hint)
            controls["apply"].setEnabled(has_preview and is_pinned)
            controls["float"].setEnabled(has_preview and is_pinned)
            controls["cancel"].setEnabled(True)
            return

        if is_pinned:
            controls["hint"].setText(
                "Pinned grid preview. Drag the handle or adjust rows, cols, radius, pitch, tilt, X, and Y, then click Apply or press Enter. Float returns to mouse placement."
            )
        else:
            controls["hint"].setText(
                "Move the grid preview over the current image. Single click pins it. Double-click or Enter pins and applies immediately."
            )
        controls["apply"].setEnabled(has_preview and is_pinned)
        controls["float"].setEnabled(self.main_window.tool_mode == "grid" and is_pinned)
        controls["cancel"].setEnabled(has_preview or self.main_window.tool_mode == "grid")

    def handle_grid_apply_action(self):
        if self.is_group_edit_mode():
            self.apply_group_edit()
        else:
            self.apply_grid_add()

    def handle_circle_apply_action(self):
        if self.main_window.tool_mode == "edit-new":
            self.apply_single_edit()
        else:
            self.apply_single_add()

    def handle_grid_cancel_action(self):
        self.cancel_preview()

    def handle_circle_cancel_action(self):
        self.cancel_preview()

    def handle_wheel_adjustment(self, event, wheel_delta):
        if wheel_delta == 0:
            event.accept()
            return True

        direction = 1 if wheel_delta > 0 else -1
        if event.inverted():
            direction *= -1

        radius_step = float(getattr(self.main_window, "radius_wheel_step", 1.0))
        pitch_step = float(getattr(self.main_window, "grid_pitch_wheel_step", 1.0))
        tilt_step = float(getattr(self.main_window, "grid_tilt_wheel_step", 1.0))

        modifiers = event.modifiers()

        if self.main_window.is_grid_horizontal_pitch_modifier_active(modifiers):
            if self.is_group_edit_mode():
                self.main_window.edit_group_horizontal_pitch_delta += direction * pitch_step
                base_pitch = float(self.main_window.edit_group_base_horizontal_pitch or self.main_window.grid_horizontal_pitch)
                self.main_window.grid_horizontal_pitch = max(0.1, base_pitch + self.main_window.edit_group_horizontal_pitch_delta)
            else:
                self.main_window.grid_horizontal_pitch = max(0.1, self.main_window.grid_horizontal_pitch + direction * pitch_step)
        elif modifiers & Qt.ControlModifier:
            if self.is_group_edit_mode():
                self.main_window.edit_group_vertical_pitch_delta += direction * pitch_step
                base_pitch = float(self.main_window.edit_group_base_vertical_pitch or self.main_window.grid_vertical_pitch)
                self.main_window.grid_vertical_pitch = max(0.1, base_pitch + self.main_window.edit_group_vertical_pitch_delta)
            else:
                self.main_window.grid_vertical_pitch = max(0.1, self.main_window.grid_vertical_pitch + direction * pitch_step)
        elif self.main_window.is_grid_tilt_modifier_active(modifiers):
            if self.is_group_edit_mode():
                self.main_window.edit_group_rotation_delta += direction * tilt_step
                base_rotation = float(self.main_window.edit_group_base_rotation_degrees or self.main_window.grid_rotation_degrees)
                self.main_window.grid_rotation_degrees = max(-180, min(180, base_rotation + self.main_window.edit_group_rotation_delta))
            else:
                self.main_window.grid_rotation_degrees = max(-180, min(180, self.main_window.grid_rotation_degrees + direction * tilt_step))
        else:
            if self.main_window.tool_mode == "edit-new":
                self.main_window.edit_single_radius_delta += direction * radius_step
                base_radius = float(self.main_window.edit_single_base_radius or self.main_window.circle_radius)
                self.main_window.circle_radius = max(1.0, base_radius + self.main_window.edit_single_radius_delta)
            elif self.is_group_edit_mode():
                self.main_window.edit_group_radius_delta += direction * radius_step
                base_radius = float(self.main_window.edit_group_base_radius or self.main_window.circle_radius)
                self.main_window.circle_radius = max(1.0, base_radius + self.main_window.edit_group_radius_delta)
            else:
                self.main_window.circle_radius = max(0.1, self.main_window.circle_radius + direction * radius_step)

        self.main_window.sync_tool_options_panel()
        self.update_preview()
        event.accept()
        return True
