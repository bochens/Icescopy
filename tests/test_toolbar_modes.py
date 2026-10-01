import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QAccessibleActionInterface
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsView
from Icescopy import IceScopy


class ToolbarModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": folder.name})
        config.start()
        self.addCleanup(config.stop)
        self.window = IceScopy()
        self.addCleanup(self.window.deleteLater)
        for group in (self.window.tool_action_group, self.window.viewer_action_group):
            for action in group.actions():
                action.setEnabled(True)

    def accessible_toggle(self, action):
        button = self.window.toolbar.widgetForAction(action)
        interface = QAccessible.queryAccessibleInterface(button).actionInterface()
        interface.doAction(QAccessibleActionInterface.toggleAction())

    def assert_only_checked(self, group, selected_action):
        self.assertEqual([action for action in group.actions() if action.isChecked()], [selected_action])
        self.assertIs(group.checkedAction(), selected_action)
        for action in group.actions():
            button = self.window.toolbar.widgetForAction(action)
            self.assertEqual(button.isChecked(), action is selected_action)

    def assert_cursor(self):
        self.assertEqual(self.window.tool_mode, "cursor")
        self.assertEqual(self.window.tool_options_mode_label.text(), "Cursor")
        self.assert_only_checked(self.window.tool_action_group, self.window.reset_cursor_action)

    def test_detection_star_is_a_one_shot_toolbar_action_in_both_themes(self):
        action = self.window.droplet_tools.detect_action
        self.assertIn(action, self.window.toolbar.actions())
        self.assertFalse(action.isCheckable())
        self.assertNotIn(action, self.window.tool_action_group.actions())
        for dark in (False, True):
            with patch('Icescopy.darkdetect.isDark', return_value=dark):
                self.window.reset_toolbar_icon()
                self.assertFalse(action.icon().isNull())
                self.assertFalse(action.icon().pixmap(24, 24).isNull())
        self.assert_cursor()

    def test_accessibility_toggles_switch_tools_and_keep_active_tool_checked(self):
        self.assert_cursor()
        self.accessible_toggle(self.window.edit_tool_action)
        self.assertEqual(self.window.tool_mode, "edit-choose")
        self.assertEqual(self.window.tool_options_mode_label.text(), "Edit Cell")
        self.assert_only_checked(self.window.tool_action_group, self.window.edit_tool_action)
        self.accessible_toggle(self.window.reset_cursor_action)
        self.assert_cursor()
        self.accessible_toggle(self.window.reset_cursor_action)
        self.assert_cursor()

    def test_mouse_and_keyboard_switch_tools_without_duplicate_activation(self):
        with patch.object(self.window.cell_controller, "enter_edit_mode", wraps=self.window.cell_controller.enter_edit_mode) as enter_edit:
            button = self.window.toolbar.widgetForAction(self.window.edit_tool_action)
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertEqual(self.window.tool_mode, "edit-choose")
            enter_edit.assert_called_once()
        QTest.keyClick(self.window, Qt.Key_A)
        self.assert_cursor()
        QTest.keyClick(self.window, Qt.Key_E)
        self.assertEqual(self.window.tool_mode, "edit-choose")
        self.assert_only_checked(self.window.tool_action_group, self.window.edit_tool_action)

    def test_accessibility_changes_image_count_and_redraws_once(self):
        self.window.set_viewer_image_count(1)
        with patch.object(self.window, "has_frames", return_value=True), patch.object(self.window, "updateImage") as redraw:
            self.accessible_toggle(self.window.viewer_double_action)
            self.assertEqual(self.window.viewer_image_count, 2)
            self.assert_only_checked(self.window.viewer_action_group, self.window.viewer_double_action)
            redraw.assert_called_once_with(self.window.image_index)
            self.accessible_toggle(self.window.viewer_double_action)
            self.assertEqual(self.window.viewer_image_count, 2)
            self.assert_only_checked(self.window.viewer_action_group, self.window.viewer_double_action)
            redraw.assert_called_once()

    def test_mouse_and_keyboard_change_image_count(self):
        for action, count in ((self.window.viewer_double_action, 2), (self.window.viewer_triple_action, 3)):
            with self.subTest(count=count):
                button = self.window.toolbar.widgetForAction(action)
                if count == 2:
                    QTest.mouseClick(button, Qt.LeftButton)
                else:
                    QTest.keyClick(button, Qt.Key_Space)
                self.assertEqual(self.window.viewer_image_count, count)
                self.assert_only_checked(self.window.viewer_action_group, action)

    def test_delete_selection_keeps_cursor_mode_checked(self):
        with patch.object(self.window, "delete_selected_cells", return_value=True) as delete_cells:
            self.accessible_toggle(self.window.deselect_tool_action)
            delete_cells.assert_called_once()
        self.assert_cursor()

    def test_programmatic_highlighting_does_not_switch_tools_or_reenter_layout(self):
        self.window.enter_temporary_pan_mode()
        self.assertEqual(self.window.tool_mode, "cursor")
        self.assert_only_checked(self.window.tool_action_group, self.window.pan_tool_action)
        self.window.apply_cursor_tool_ui()
        self.assert_cursor()
        with patch.object(self.window, "has_frames", return_value=True), patch.object(self.window, "updateImage") as redraw:
            self.window.set_viewer_image_count(3)
            self.assert_only_checked(self.window.viewer_action_group, self.window.viewer_triple_action)
            redraw.assert_called_once_with(self.window.image_index)

    def test_restore_reapplies_an_already_selected_tool(self):
        self.window.panTool(True)
        self.window.view.setDragMode(QGraphicsView.NoDrag)
        with patch.object(self.window, "has_frames", return_value=True):
            self.window.restore_tool_mode_ui("pan")
        self.assertEqual(self.window.tool_mode, "pan")
        self.assertEqual(self.window.view.dragMode(), QGraphicsView.ScrollHandDrag)
        self.assert_only_checked(self.window.tool_action_group, self.window.pan_tool_action)


if __name__ == "__main__":
    unittest.main()
