import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QGraphicsScene, QGraphicsView  # noqa: E402

from icescopy_cell_items import CellCircle  # noqa: E402
from icescopy_cell_controller import CellEditController  # noqa: E402
from icescopy_aux import CustomGraphicsView  # noqa: E402


class DummyMainWindow:
    def __init__(self, tool_mode="select"):
        self.tool_mode = tool_mode
        self.circle_radius = 37.5
        self.default_circle_radius = 22.0
        self.grid_rows = 2
        self.grid_columns = 3
        self.grid_horizontal_pitch = 41.0
        self.grid_vertical_pitch = 42.0
        self.grid_rotation_degrees = 7.0
        self.default_grid_rows = 4
        self.default_grid_columns = 5
        self.default_grid_horizontal_pitch = 60.0
        self.default_grid_vertical_pitch = 61.0
        self.default_grid_rotation_degrees = 0.0
        self.grid_preview_items = []
        self.grid_preview_handle_item = None
        self.grid_preview_origin_pixels = (10.0, 20.0)
        self.grid_preview_floating = False
        self.preview_offset_x = 3.0
        self.preview_offset_y = 4.0
        self.cell_items = []
        self.restore_calls = []
        self.synced_tool_panel = 0
        self.applied_cursor = False
        self.history_actions = []
        self.logs = []
        self.finalized = False
        self.next_cell_id = 0
        self.rendered_cell_items = []
        self.tool_status_label = QLabel()
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)

    def restore_add_defaults(self, include_grid=False):
        self.restore_calls.append(include_grid)
        self.circle_radius = float(self.default_circle_radius)
        if include_grid:
            self.grid_rows = int(self.default_grid_rows)
            self.grid_columns = int(self.default_grid_columns)
            self.grid_horizontal_pitch = float(self.default_grid_horizontal_pitch)
            self.grid_vertical_pitch = float(self.default_grid_vertical_pitch)
            self.grid_rotation_degrees = float(self.default_grid_rotation_degrees)

    def sync_tool_options_panel(self):
        self.synced_tool_panel += 1

    def apply_cursor_tool_ui(self):
        self.applied_cursor = True
        self.tool_mode = "cursor"

    def reset_cell_items_edit_chosen(self):
        pass

    def set_view_cursor_shape(self, _cursor_shape):
        pass

    def restore_after_edit_mode(self):
        pass

    def capture_cell_state(self):
        return {"before": True}

    def push_cell_history(self, action, before_state):
        self.history_actions.append((action, before_state))

    def log(self, message):
        self.logs.append(message)

    def finalize_tool_mode_after_commit(self):
        self.finalized = True

    def allocate_cell_id(self):
        cell_id = self.next_cell_id
        self.next_cell_id += 1
        return cell_id

    def displayMarkedRegions(self):
        pass

    def add_cell_item_to_keyframes(self, _added_items):
        pass

    def ensure_cell_registry_matches_scene_cells(self):
        pass

    def refresh_cells_panel(self):
        pass

    def refresh_cursor_selection_info(self):
        pass

    def handle_scene_cell_selection_changed(self):
        pass

    def update_cell_items_selectable_state(self):
        if hasattr(self, "cell_controller"):
            self.cell_controller.update_scene_selectable_state()

    def sync_active_preview_coordinate_controls(self):
        pass

    def get_qcolor(self, _color_text):
        return QColor(255, 0, 0)

    def image_pixel_to_scene_coordinates(self, pixel_x, pixel_y, _image_rect=None):
        return (float(pixel_x), float(pixel_y))

    def is_grid_horizontal_pitch_modifier_active(self, modifiers):
        return bool(modifiers & Qt.AltModifier)

    def is_grid_tilt_modifier_active(self, modifiers):
        return bool(modifiers & Qt.ShiftModifier)


class DummyWheelEvent:
    def __init__(self, modifiers=Qt.NoModifier, inverted=False):
        self._modifiers = modifiers
        self._inverted = inverted
        self.accepted = False

    def modifiers(self):
        return self._modifiers

    def inverted(self):
        return self._inverted

    def accept(self):
        self.accepted = True


class DummyDelta:
    def __init__(self, y_value):
        self._y_value = y_value

    def y(self):
        return self._y_value


class DummyGraphicsWheelEvent(DummyWheelEvent):
    def __init__(self, angle_delta=120, pixel_delta=0, modifiers=Qt.NoModifier, inverted=False):
        super().__init__(modifiers=modifiers, inverted=inverted)
        self._angle_delta = angle_delta
        self._pixel_delta = pixel_delta

    def angleDelta(self):
        return DummyDelta(self._angle_delta)

    def pixelDelta(self):
        return DummyDelta(self._pixel_delta)


class CellEditControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pinned_cancel_in_add_cell_preserves_user_radius(self):
        main_window = DummyMainWindow(tool_mode="select")
        controller = CellEditController(main_window)

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.restore_calls, [])
        self.assertEqual(main_window.tool_mode, "select")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
        self.assertEqual(main_window.synced_tool_panel, 1)

    def test_add_cell_wheel_still_changes_add_radius(self):
        main_window = DummyMainWindow(tool_mode="select")
        main_window.radius_wheel_step = 2.0
        main_window.image_width = 100.0
        main_window.maximum_zoom = 10.0
        main_window.space_held = False
        main_window.temporary_event_data = {}
        main_window.update_zoom_count = 0
        main_window.update_radius_count = 0
        main_window.update_preview_count = 0
        main_window.updateZoomTextbox = lambda: setattr(
            main_window,
            "update_zoom_count",
            main_window.update_zoom_count + 1,
        )
        main_window.updateRadiusTextbox = lambda: setattr(
            main_window,
            "update_radius_count",
            main_window.update_radius_count + 1,
        )
        main_window.update_grid_preview = lambda: setattr(
            main_window,
            "update_preview_count",
            main_window.update_preview_count + 1,
        )
        main_window.is_pan_interaction_active = lambda: False
        controller = CellEditController(main_window)
        main_window.cell_controller = controller
        view = CustomGraphicsView(main_window.scene, main_window)
        event = DummyGraphicsWheelEvent(angle_delta=120)

        view.wheelEvent(event)

        self.assertTrue(event.accepted)
        self.assertAlmostEqual(main_window.circle_radius, 39.5)
        self.assertEqual(main_window.update_radius_count, 1)
        self.assertEqual(main_window.update_preview_count, 1)
        self.assertEqual(main_window.synced_tool_panel, 1)

    def test_floating_cancel_in_add_cell_preserves_user_radius_when_leaving_tool(self):
        main_window = DummyMainWindow(tool_mode="select")
        main_window.grid_preview_floating = True
        controller = CellEditController(main_window)

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.restore_calls, [])
        self.assertTrue(main_window.applied_cursor)
        self.assertEqual(main_window.tool_mode, "cursor")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)

    def test_floating_cancel_in_grid_preserves_user_grid_settings_when_leaving_tool(self):
        main_window = DummyMainWindow(tool_mode="grid")
        main_window.grid_preview_floating = True
        controller = CellEditController(main_window)

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.restore_calls, [])
        self.assertTrue(main_window.applied_cursor)
        self.assertEqual(main_window.tool_mode, "cursor")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
        self.assertEqual(main_window.grid_rows, 2)
        self.assertEqual(main_window.grid_columns, 3)
        self.assertAlmostEqual(main_window.grid_horizontal_pitch, 41.0)
        self.assertAlmostEqual(main_window.grid_vertical_pitch, 42.0)
        self.assertAlmostEqual(main_window.grid_rotation_degrees, 7.0)

    def test_single_add_commit_preserves_user_radius(self):
        main_window = DummyMainWindow(tool_mode="select")
        controller = CellEditController(main_window)
        controller.get_preview_definitions = lambda: [("scene", (10.0, 20.0))]
        recorded = {}

        def add_single_cell(scene_pos, pixel_pos, radius):
            recorded["args"] = (scene_pos, pixel_pos, radius)
            return 12

        controller.add_single_cell = add_single_cell

        controller.apply_single_add()

        self.assertEqual(recorded["args"], ("scene", (10.0, 20.0), 37.5))
        self.assertEqual(main_window.restore_calls, [])
        self.assertEqual(main_window.tool_mode, "select")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
        self.assertTrue(main_window.finalized)

    def test_single_edit_uses_target_radius_delta_without_changing_add_radius(self):
        main_window = DummyMainWindow(tool_mode="edit-new")
        main_window.edit_single_base_radius = 12.0
        main_window.edit_single_radius_delta = 3.0
        controller = CellEditController(main_window)
        controller.get_preview_definitions = lambda: [("scene", (10.0, 20.0))]
        recorded = {}

        def replace_active_edit_cell(scene_pos, pixel_pos, radius):
            recorded["args"] = (scene_pos, pixel_pos, radius)
            return 7

        controller.replace_active_edit_cell = replace_active_edit_cell

        controller.apply_single_edit()

        self.assertEqual(recorded["args"], ("scene", (10.0, 20.0), 15.0))
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
        self.assertTrue(main_window.finalized)

    def test_single_edit_wheel_changes_edit_radius_delta_not_add_radius(self):
        main_window = DummyMainWindow(tool_mode="edit-new")
        main_window.edit_single_base_radius = 12.0
        main_window.edit_single_radius_delta = 0.0
        main_window.radius_wheel_step = 2.0
        main_window.grid_pitch_wheel_step = 1.0
        main_window.grid_tilt_wheel_step = 1.0
        controller = CellEditController(main_window)
        controller.update_preview = lambda: None
        event = DummyWheelEvent()

        handled = controller.handle_wheel_adjustment(event, 120)

        self.assertTrue(handled)
        self.assertTrue(event.accepted)
        self.assertAlmostEqual(main_window.edit_single_radius_delta, 2.0)
        self.assertAlmostEqual(main_window.circle_radius, 37.5)

    def test_cancel_single_edit_restores_edit_rubber_band_selection(self):
        main_window = DummyMainWindow(tool_mode="edit-new")
        main_window.scene = QGraphicsScene()
        main_window.view = QGraphicsView(main_window.scene)
        main_window.view.setDragMode(QGraphicsView.NoDrag)
        main_window.grid_preview_origin_pixels = (10.0, 20.0)
        controller = CellEditController(main_window)
        main_window.cell_controller = controller

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.tool_mode, "edit-choose")
        self.assertEqual(main_window.view.dragMode(), QGraphicsView.RubberBandDrag)
        self.assertEqual(main_window.view.rubberBandSelectionMode(), Qt.IntersectsItemShape)

    def test_cancel_group_edit_restores_edit_rubber_band_selection(self):
        main_window = DummyMainWindow(tool_mode="edit-group")
        main_window.scene = QGraphicsScene()
        main_window.view = QGraphicsView(main_window.scene)
        main_window.view.setDragMode(QGraphicsView.NoDrag)
        main_window.grid_preview_origin_pixels = (10.0, 20.0)
        controller = CellEditController(main_window)
        controller.group_cell_ids = {1, 2}
        main_window.cell_controller = controller

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.tool_mode, "edit-choose")
        self.assertEqual(main_window.view.dragMode(), QGraphicsView.RubberBandDrag)
        self.assertEqual(main_window.view.rubberBandSelectionMode(), Qt.IntersectsItemShape)
        self.assertEqual(controller.group_cell_ids, [])

    def test_grid_add_commit_preserves_user_radius_and_grid_settings(self):
        main_window = DummyMainWindow(tool_mode="grid")
        controller = CellEditController(main_window)
        controller.get_preview_definitions = lambda: [
            ("scene-0", (10.0, 20.0)),
            ("scene-1", (30.0, 40.0)),
        ]

        with patch("icescopy_cell_controller.CellCircle", side_effect=lambda *args: object()):
            controller.apply_grid_add()

        self.assertEqual(main_window.restore_calls, [])
        self.assertEqual(main_window.tool_mode, "grid")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
        self.assertEqual(main_window.grid_rows, 2)
        self.assertEqual(main_window.grid_columns, 3)
        self.assertAlmostEqual(main_window.grid_horizontal_pitch, 41.0)
        self.assertAlmostEqual(main_window.grid_vertical_pitch, 42.0)
        self.assertAlmostEqual(main_window.grid_rotation_degrees, 7.0)
        self.assertEqual(len(main_window.cell_items), 2)
        self.assertTrue(main_window.finalized)

    def test_group_edit_starts_from_selected_geometry_not_add_grid_settings(self):
        class FakePixmapItem:
            def sceneBoundingRect(self):
                return QRectF(0.0, 0.0, 1000.0, 1000.0)

        main_window = DummyMainWindow(tool_mode="cursor")
        main_window.scene = QGraphicsScene()
        main_window.view = QGraphicsView(main_window.scene)
        main_window.tool_status_label = QLabel()
        main_window.grid_preview_outline_color = "255,0,0,255"
        main_window.grid_preview_fill_color = "255,0,0,50"
        main_window.grid_horizontal_pitch = 999.0
        main_window.grid_vertical_pitch = 777.0
        main_window.grid_rotation_degrees = 45.0
        main_window.pixmap_item = FakePixmapItem()
        controller = CellEditController(main_window)
        main_window.cell_controller = controller
        selected_items = [
            CellCircle(main_window, (100.0, 100.0), 10.0, (100.0, 100.0), 0),
            CellCircle(main_window, (157.0, 113.0), 12.0, (157.0, 113.0), 1),
            CellCircle(main_window, (184.0, 211.0), 9.0, (184.0, 211.0), 2),
        ]
        for item in selected_items:
            main_window.scene.addItem(item)
        main_window.cell_items = list(selected_items)

        controller.start_group_edit(selected_items)
        definitions = controller.get_preview_definitions()
        positions_by_cell_id = {
            cell_id: pixel_pos
            for cell_id, (_scene_pos, pixel_pos) in zip(controller.group_ordered_cell_ids, definitions)
        }

        self.assertEqual(len(definitions), 3)
        self.assertEqual(
            positions_by_cell_id,
            {
                0: (100.0, 100.0),
                1: (157.0, 113.0),
                2: (184.0, 211.0),
            },
        )
        self.assertEqual(main_window.grid_horizontal_pitch, 999.0)
        self.assertEqual(main_window.grid_vertical_pitch, 777.0)
        self.assertEqual(main_window.grid_rotation_degrees, 45.0)
        self.assertEqual(main_window.circle_radius, 37.5)

    def test_redraw_current_cells_draws_template_cells_without_images(self):
        main_window = DummyMainWindow(tool_mode="cursor")
        main_window.scene = QGraphicsScene()
        main_window.view = QGraphicsView(main_window.scene)
        controller = CellEditController(main_window)
        main_window.cell_controller = controller
        main_window.cell_items = [
            CellCircle(main_window, (100.0, 125.0), 12.0, (100.0, 125.0), 0),
            CellCircle(main_window, (220.0, 240.0), 15.0, (220.0, 240.0), 1),
        ]

        controller.redraw_current_cells(preserve_selection=False, force_scene_scan=True)

        scene_cells = [
            item for item in main_window.scene.items()
            if isinstance(item, CellCircle)
        ]
        self.assertEqual(len(scene_cells), 2)
        self.assertEqual(
            sorted(item.cell_id for item in main_window.rendered_cell_items),
            [0, 1],
        )
        self.assertEqual(
            sorted(item.cell_id for item in main_window.cell_items),
            [0, 1],
        )
        self.assertTrue(main_window.view.sceneRect().contains(100.0, 125.0))
        self.assertTrue(main_window.view.sceneRect().contains(220.0, 240.0))


if __name__ == "__main__":
    unittest.main()
