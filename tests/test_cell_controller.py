import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from icescopy_cell_controller import CellEditController  # noqa: E402


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


class CellEditControllerTests(unittest.TestCase):
    def test_pinned_cancel_in_add_cell_preserves_user_radius(self):
        main_window = DummyMainWindow(tool_mode="select")
        controller = CellEditController(main_window)

        controller.cancel_preview(log_message=False)

        self.assertEqual(main_window.restore_calls, [])
        self.assertEqual(main_window.tool_mode, "select")
        self.assertAlmostEqual(main_window.circle_radius, 37.5)
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


if __name__ == "__main__":
    unittest.main()
