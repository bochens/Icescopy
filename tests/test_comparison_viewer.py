import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem

from Icescopy import IceScopy
from icescopy_cell_items import CellCircle, CellSnapshot
from icescopy_frame_source import ImageSequenceFrameSource


class ComparisonViewerTests(unittest.TestCase):
    """Exercise comparison through the same window and edit paths as one-image view."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        config = patch.dict(os.environ, {"ICESCOPY_CONFIG_DIR": str(self.root / "config")})
        config.start()
        self.addCleanup(config.stop)
        self.paths = []
        self.brightness = [40, 60, 80, 100, 120]
        for index, level in enumerate(self.brightness):
            path = self.root / f"frame_{index:03d}.png"
            image = QImage(800, 600, QImage.Format_RGB32)
            image.fill(QColor(level, level, level))
            self.assertTrue(image.save(str(path)))
            self.paths.append(path)
        self.window = IceScopy()
        self.addCleanup(self.dispose_window)
        self.window.resize(1500, 950)
        self.window.session_active = True
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.window.populate_image_list()
        self.window.updateImage(2)
        self.window.set_viewer_image_count(3)
        self.window.update_session_actions_state()
        self.window.show()
        self.process_events()
        self.viewer = self.window.comparison_viewer

    def dispose_window(self):
        self.window.hide()
        self.window.stop_video_preview_decoder()
        self.window.deleteLater()
        self.app.processEvents()

    def process_events(self):
        # Resize and layout changes arrive through the Qt event queue.
        self.app.processEvents()
        self.app.processEvents()

    def panels(self):
        return [self.viewer.previous, self.viewer.current, self.viewer.next]

    def visible_panels(self):
        return [panel for panel in self.panels() if panel.isVisible()]

    def center(self, view):
        return view.mapToScene(QPoint(view.viewport().width() // 2, view.viewport().height() // 2))

    def assert_linked(self, expected_scale=None, expected_center=None):
        views = [panel.view for panel in self.visible_panels()]
        scale = views[0].transform().m11() if expected_scale is None else expected_scale
        center = self.center(views[0]) if expected_center is None else expected_center
        # Scroll bars round device coordinates; at most two device pixels may differ.
        tolerance = 2.1 / max(scale, 0.03)
        for view in views:
            self.assertAlmostEqual(view.transform().m11(), scale, places=8)
            actual = self.center(view)
            self.assertAlmostEqual(actual.x(), center.x(), delta=tolerance)
            self.assertAlmostEqual(actual.y(), center.y(), delta=tolerance)

    def set_camera(self, scale=1.5, center=QPointF(350, 270)):
        self.window.zoom_textbox.setText(str(scale * 100))
        self.window.updateZoomLevel()
        self.window.view.centerOn(center)
        self.process_events()

    def panel_pixmap_item(self, panel):
        return self.window.pixmap_item if panel is self.viewer.current else panel.pixmap_item

    def panel_pixel(self, panel):
        image = self.panel_pixmap_item(panel).pixmap().toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2).red()

    def assert_panel_images(self, expected_indices):
        self.assertEqual([panel.frame_index for panel in self.visible_panels()], expected_indices)
        for panel, index in zip(self.visible_panels(), expected_indices):
            if index is not None:
                self.assertEqual(self.panel_pixmap_item(panel).pos(), QPointF(0, 0))
                self.assertEqual(self.panel_pixel(panel), self.brightness[index])

    def enter_image_edit(self):
        self.window.imageEditTool(True)
        self.process_events()

    def install_moving_cell(self, first=0, last=4):
        cell_id = self.window.cell_controller.add_single_cell((100, 120), (100, 120), 10)
        self.window.keyframe_list = [first, last]
        self.window.keyframe_cell_items_dict = {
            first: [CellSnapshot((100, 120), 10, (100, 120), cell_id)],
            last: [CellSnapshot((300, 200), 30, (300, 200), cell_id)],
        }
        self.window.image_slider.keyframes = {first, last}
        self.window.updateImage(2)
        return cell_id

    def assert_cell_geometry(self, items, expected):
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual((*item.circle_pixel_positions, item.circle_sizes), expected)
        return item

    def install_selection_cells(self):
        self.window.apply_cursor_tool_ui()
        return [
            self.window.cell_controller.add_single_cell(position, position, radius)
            for position, radius in (((250, 220), 10), ((400, 300), 50), ((350, 190), 8))
        ]

    def show_cells_list(self):
        self.window.cells_dock.show()
        self.window.cells_dock.raise_()
        self.window.cells_panel_force_refresh = True
        self.window.refresh_cells_panel()
        self.process_events()
        return self.window.cells_tree_widget

    def selected_cell_ids(self):
        return {item.cell_id for item in self.window.get_selected_cell_items()}

    def set_freeze_frames(self, cell_ids, events):
        for cell_id, frames in zip(cell_ids, events):
            self.window.ensure_cell_record(cell_id).freeze_event_indices = list(frames)

    def click_checkbox(self, checkbox):
        QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(10, checkbox.height() // 2))
        self.process_events()

    def install_freeze_review_cycles(self, cycle_ids=(0, 0, 1, 1, 2)):
        self.window.freeze_review_cycle_metadata = {
            "frame_keys": [self.window.frame_key(index) for index in range(self.window.frame_count())],
            "cycle_ids": list(cycle_ids),
            "reset_temperature": 0.0,
        }

    def choose_freeze_event(self, label):
        combo = self.window.cells_freeze_event_selector.combo
        index = combo.findText(label)
        self.assertGreaterEqual(index, 0, label)
        combo.showPopup()
        self.process_events()
        view = combo.view()
        position = view.visualRect(combo.model().index(index, 0)).center()
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=position)
        self.process_events()

    def test_event_selector_orders_valid_events_and_navigates_with_arrows_and_dropdown(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([4, 0, 2, 2, -1, 5], [], []))
        self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        selector = self.window.cells_freeze_event_selector
        selector.refresh()
        self.assertEqual([selector.combo.itemText(index) for index in range(selector.combo.count())], [
            "Event 1 · Frame 0", "Event 2 · Frame 2", "Event 3 · Frame 4",
        ])
        self.assertFalse(self.window.cells_show_first_freeze_checkbox.isChecked())
        self.assertFalse(selector.previous_button.isEnabled())
        self.assertTrue(selector.next_button.isEnabled())
        self.assertEqual(self.window.image_index, 2)
        for expected in (2, 4):
            QTest.mouseClick(selector.next_button, Qt.LeftButton)
            self.assertEqual(self.window.image_index, expected)
            self.assertEqual(selector.selected_frame(), expected)
        self.assertFalse(selector.next_button.isEnabled())
        QTest.mouseClick(selector.previous_button, Qt.LeftButton)
        self.assertEqual(self.window.image_index, 2)
        self.choose_freeze_event("Event 1 · Frame 0")
        self.assertEqual(self.window.image_index, 0)
        self.assertFalse(selector.previous_button.isEnabled())
        history_count = self.window.undo_stack.count()
        self.window.undo_stack.undo()
        self.assertEqual(self.window.image_index, 2)
        self.window.undo_stack.redo()
        self.assertEqual(self.window.image_index, 0)
        self.assertEqual(self.window.undo_stack.count(), history_count)

    def test_explicit_event_navigation_centers_destination_geometry_only_when_enabled(self):
        cell_id = self.install_moving_cell()
        self.window.apply_cursor_tool_ui()
        self.set_freeze_frames([cell_id], ([1, 3],))
        crop = {"center_x": 280.0, "center_y": 240.0, "width": 400.0, "height": 300.0, "angle": 15.0}
        self.window.apply_image_edit_state(self.window.compose_image_edit_state(crop=crop))
        self.show_cells_list()
        self.window.reselect_cell_ids([cell_id])
        self.set_camera(scale=1.5, center=QPointF(320, 260))
        original_center = self.center(self.window.view)
        selector = self.window.cells_freeze_event_selector
        selector.refresh()
        QTest.mouseClick(selector.next_button, Qt.LeftButton)
        self.assertEqual(self.window.image_index, 3)
        self.assert_linked(expected_scale=1.5, expected_center=original_center)
        self.window.cells_auto_center_checkbox.setChecked(True)
        QTest.mouseClick(selector.previous_button, Qt.LeftButton)
        self.assertEqual(self.window.image_index, 1)
        self.assertEqual(self.selected_cell_ids(), {cell_id})
        self.assertEqual(self.window.get_selected_cell_items()[0].circle_pixel_positions, (150, 140))
        expected = QPointF(*self.window.image_pixel_to_scene_coordinates(150, 140, index=1))
        self.assert_linked(expected_scale=1.5, expected_center=expected)
        self.assertFalse(self.window.cells_show_first_freeze_checkbox.isChecked())

    def test_cycle_choice_survives_cell_changes_and_missing_cycle_does_not_seek(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 3, 4], [0, 4], [1, 2, 4]))
        self.install_freeze_review_cycles()
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        selector = self.window.cells_freeze_event_selector
        selector.refresh()
        self.choose_freeze_event("Cycle 2 · Frame 3")
        self.assertEqual(self.window.image_index, 3)

        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=tree.visualItemRect(tree.topLevelItem(1)).center())
        self.assertEqual(self.window.image_index, 3)
        self.assertEqual(selector.combo.currentText(), "Cycle 2 · No freeze event")
        self.assertIsNone(selector.selected_frame())
        self.assertGreaterEqual(selector.combo.findText("Cycle 1 · Frame 0"), 0)
        self.assertGreaterEqual(selector.combo.findText("Cycle 3 · Frame 4"), 0)
        self.assertTrue(selector.previous_button.isEnabled())
        self.assertTrue(selector.next_button.isEnabled())

        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=tree.visualItemRect(tree.topLevelItem(2)).center())
        self.assertEqual(self.window.image_index, 2)
        self.assertEqual(selector.combo.currentText(), "Cycle 2 · Frame 2")
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=tree.visualItemRect(tree.topLevelItem(1)).center())
        self.assertEqual(self.window.image_index, 2)
        QTest.mouseClick(selector.next_button, Qt.LeftButton)
        self.assertEqual(self.window.image_index, 4)
        self.assertEqual(selector.combo.currentText(), "Cycle 3 · Frame 4")

    def test_same_cell_retains_exact_event_within_a_cycle_after_manual_frame_navigation(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 1, 3, 4], [], []))
        self.install_freeze_review_cycles()
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.choose_freeze_event("Cycle 1 · Frame 1")
        self.window.navigate_to_image(4)
        self.assertEqual(self.window.cells_freeze_event_selector.selected_frame(), 1)
        point = tree.visualItemRect(tree.topLevelItem(0)).center()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.window.image_index, 1)
        self.assertEqual(self.window.cells_freeze_event_selector.combo.currentText(), "Cycle 1 · Frame 1")

    def test_event_selector_is_disabled_without_one_cell_with_valid_events(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 4], [], [-1, 5, 100]))
        self.show_cells_list()
        selector = self.window.cells_freeze_event_selector
        for selected in ([], cell_ids[:2], [cell_ids[1]], [cell_ids[2]]):
            with self.subTest(selected=selected):
                self.window.reselect_cell_ids(selected)
                selector.refresh()
                self.assertIsNone(selector.selected_frame())
                self.assertFalse(selector.combo.isEnabled())
                self.assertFalse(selector.previous_button.isEnabled())
                self.assertFalse(selector.next_button.isEnabled())
                selector.activate_event(0)
                selector.step_event(1)
                self.assertEqual(self.window.image_index, 2)

    def test_canvas_selection_and_programmatic_event_refresh_do_not_navigate(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 4], [1, 3], []))
        self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        original_center = self.center(self.window.view)
        view = self.window.view
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(QPointF(250, 220)))
        selector = self.window.cells_freeze_event_selector
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        self.assertTrue(selector.combo.isEnabled())
        selector.combo.setCurrentIndex(1)
        selector.refresh()
        self.window.reselect_cell_ids([cell_ids[1]])
        selector.refresh()
        self.assertEqual(self.window.image_index, 2)
        self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_event_choice_clears_after_metadata_or_frame_source_changes_without_seeking(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 3, 4], [], []))
        self.install_freeze_review_cycles()
        self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        selector = self.window.cells_freeze_event_selector
        self.choose_freeze_event("Cycle 2 · Frame 3")
        self.install_freeze_review_cycles((0, 0, 0, 1, 1))
        selector.refresh()
        self.assertEqual(self.window.image_index, 3)
        self.assertEqual(selector.selected_frame(), 0)
        self.choose_freeze_event("Cycle 2 · Frame 3")
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.window.updateImage(2)
        self.window.reselect_cell_ids([cell_ids[0]])
        selector.refresh()
        self.assertEqual(self.window.image_index, 2)
        self.assertEqual(selector.selected_frame(), 0)

    def test_event_actions_recheck_space_edit_and_analysis_guards_and_allow_normal_pan(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 4], [], []))
        self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        selector = self.window.cells_freeze_event_selector
        selector.refresh()
        QTest.keyPress(self.window, Qt.Key_Space)
        selector.activate_event(1)
        selector.step_event(1)
        self.assertEqual(self.window.image_index, 2)
        QTest.keyRelease(self.window, Qt.Key_Space)
        self.window.imageEditTool(True)
        selector.activate_event(1)
        self.assertEqual(self.window.image_index, 2)
        self.window.reset_cursor_tool(True)
        self.window.reselect_cell_ids([cell_ids[0]])
        with patch.object(self.window, "output_state", True):
            selector.activate_event(1)
            selector.step_event(1)
            self.assertEqual(self.window.image_index, 2)
        self.window.panTool(True)
        selector.refresh()
        QTest.mouseClick(selector.next_button, Qt.LeftButton)
        self.assertEqual(self.window.image_index, 4)
        self.assertEqual(self.window.tool_mode, "pan")

    def test_event_arrow_release_does_not_navigate_after_its_context_changes(self):
        cell_ids = self.install_selection_cells()
        self.show_cells_list()
        selector = self.window.cells_freeze_event_selector
        self.window.cells_auto_center_checkbox.setChecked(True)
        interruptions = (
            ("frame", lambda: self.window.navigate_to_image(3), 3),
            ("selection", lambda: self.window.reselect_cell_ids([cell_ids[1]]), 2),
            ("events", lambda: self.set_freeze_frames(cell_ids[:1], ([0, 3],)), 2),
            ("cycles", self.install_freeze_review_cycles, 2),
            ("source", lambda: self.window.set_frame_source(ImageSequenceFrameSource(self.paths)), 2),
        )
        for name, interrupt, expected_frame in interruptions:
            with self.subTest(interruption=name):
                self.window.freeze_review_cycle_metadata = {}
                self.set_freeze_frames(cell_ids, ([0, 4], [1, 3], []))
                self.window.reselect_cell_ids([cell_ids[0]])
                self.window.navigate_to_image(2)
                self.set_camera(scale=1.0, center=QPointF(500, 420))
                original_center = self.center(self.window.view)
                selector.refresh()
                self.assertTrue(selector.next_button.isEnabled())
                with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
                    QTest.mousePress(selector.next_button, Qt.LeftButton)
                    interrupt()
                    selector.refresh()
                    QTest.mouseRelease(selector.next_button, Qt.LeftButton)
                    self.assertEqual(center.call_count, 0)
                self.assertEqual(self.window.image_index, expected_frame)
                self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_rejected_event_popup_action_restores_the_displayed_retained_event(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 4], [], []))
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        selector = self.window.cells_freeze_event_selector
        selector.combo.showPopup()
        self.process_events()
        self.window.navigate_to_image(3)
        view = selector.combo.view()
        position = view.visualRect(selector.combo.model().index(1, 0)).center()
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=position)
        self.process_events()
        self.assertEqual(self.window.image_index, 3)
        self.assertEqual(selector.selected_frame(), 0)
        self.assertEqual(selector.combo.currentText(), "Event 1 · Frame 0")
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=tree.visualItemRect(tree.topLevelItem(0)).center())
        self.assertEqual(self.window.image_index, 0)

    def test_event_combo_wheel_uses_a_fresh_context_after_popup_navigation(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0, 4], [], []))
        self.show_cells_list()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.choose_freeze_event("Event 2 · Frame 4")
        selector = self.window.cells_freeze_event_selector
        combo = selector.combo
        combo.setFocus()
        point = combo.rect().center()
        for delta, expected_frame in ((120, 0), (-120, 4)):
            with self.subTest(delta=delta):
                wheel = QWheelEvent(
                    QPointF(point), QPointF(combo.mapToGlobal(point)), QPoint(), QPoint(0, delta),
                    Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False,
                )
                self.app.sendEvent(combo, wheel)
                self.process_events()
                self.assertEqual(self.window.image_index, expected_frame)
                self.assertEqual(selector.selected_frame(), expected_frame)
                self.assertTrue(combo.currentText().endswith(f"Frame {expected_frame}"))

    def test_first_freeze_and_auto_center_are_independent_and_wait_for_list_release(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([4, 0, 3], [1], [4]))
        tree = self.show_cells_list()
        self.assertFalse(self.window.cells_show_first_freeze_checkbox.isChecked())
        self.assertFalse(self.window.cells_auto_center_checkbox.isChecked())
        for auto_center, show_freeze in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(auto_center=auto_center, show_freeze=show_freeze):
                self.window.navigate_to_image(2)
                self.window.reselect_cell_ids([cell_ids[0]])
                self.set_camera(scale=1.1, center=QPointF(350, 270))
                original_center = self.center(self.window.view)
                self.window.cells_auto_center_checkbox.setChecked(auto_center)
                self.window.cells_show_first_freeze_checkbox.setChecked(show_freeze)
                self.process_events()
                self.assertEqual(self.window.image_index, 2)
                self.assert_linked(expected_scale=1.1, expected_center=original_center)
                self.window.reselect_cell_ids([])
                position = tree.visualItemRect(tree.topLevelItem(0)).center()
                QTest.mousePress(tree.viewport(), Qt.LeftButton, pos=position)
                self.assertEqual(self.window.image_index, 2)
                self.assert_linked(expected_scale=1.1, expected_center=original_center)
                QTest.mouseRelease(tree.viewport(), Qt.LeftButton, pos=position)
                self.process_events()
                self.assertEqual(self.window.image_index, 0 if show_freeze else 2)
                self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
                expected_center = QPointF(250, 220) if auto_center else original_center
                self.assert_linked(expected_scale=1.1, expected_center=expected_center)

    def test_enabling_either_checkbox_applies_all_enabled_options_and_unchecking_does_not_move(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        self.show_cells_list()
        auto = self.window.cells_auto_center_checkbox
        freeze = self.window.cells_show_first_freeze_checkbox
        for target, other_enabled in ((auto, False), (freeze, False), (auto, True), (freeze, True)):
            with self.subTest(target=target.text(), other_enabled=other_enabled):
                auto.setChecked(False)
                freeze.setChecked(False)
                other = freeze if target is auto else auto
                other.setChecked(other_enabled)
                self.window.navigate_to_image(2)
                self.window.reselect_cell_ids([cell_ids[0]])
                self.set_camera(scale=1.25, center=QPointF(500, 420))
                original_center = self.center(self.window.view)
                self.click_checkbox(target)
                self.assertTrue(target.isChecked())
                self.assertEqual(self.window.image_index, 0 if freeze.isChecked() else 2)
                expected = QPointF(250, 220) if auto.isChecked() else original_center
                self.assert_linked(expected_scale=1.25, expected_center=expected)

                self.window.navigate_to_image(2)
                self.set_camera(scale=1.25, center=QPointF(500, 420))
                original_center = self.center(self.window.view)
                self.click_checkbox(target)
                self.assertFalse(target.isChecked())
                self.assertEqual(self.window.image_index, 2)
                self.assert_linked(expected_scale=1.25, expected_center=original_center)

    def test_checkbox_keyboard_activation_handles_groups_and_empty_selection(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        self.show_cells_list()
        self.window.reselect_cell_ids(cell_ids[:2])
        self.set_camera(scale=1.0, center=QPointF(500, 420))
        original_center = self.center(self.window.view)
        # Restoring checkbox state programmatically does not execute navigation.
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.assert_linked(expected_scale=1.0, expected_center=original_center)
        self.assertEqual(self.window.image_index, 2)
        self.window.cells_auto_center_checkbox.setChecked(False)
        self.window.cells_auto_center_checkbox.setFocus()
        QTest.keyClick(self.window.cells_auto_center_checkbox, Qt.Key_Space)
        self.assertTrue(self.window.cells_auto_center_checkbox.isChecked())
        self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
        self.assertEqual(self.window.image_index, 2)
        self.assertEqual(self.window.tool_mode, "cursor")
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(345, 280))

        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(500, 420))
        original_center = self.center(self.window.view)
        for checkbox in (self.window.cells_auto_center_checkbox, self.window.cells_show_first_freeze_checkbox):
            checkbox.setChecked(False)
            self.click_checkbox(checkbox)
            self.assertTrue(checkbox.isChecked())
            self.assertEqual(self.window.image_index, 2)
            self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_same_cell_row_click_reapplies_enabled_options_after_manual_navigation(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        tree = self.show_cells_list()
        tree.setCurrentItem(tree.topLevelItem(0))
        self.window.reselect_cell_ids([cell_ids[0]])
        for auto_center, show_freeze in ((False, False), (True, False), (False, True), (True, True)):
            for scale in (1.4, 0.9):
                with self.subTest(auto_center=auto_center, show_freeze=show_freeze, scale=scale):
                    self.window.cells_auto_center_checkbox.setChecked(auto_center)
                    self.window.cells_show_first_freeze_checkbox.setChecked(show_freeze)
                    self.window.navigate_to_image(2)
                    self.set_camera(scale=scale, center=QPointF(500, 420))
                    original_center = self.center(self.window.view)
                    self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
                    position = tree.visualItemRect(tree.topLevelItem(0)).center()
                    QTest.mousePress(tree.viewport(), Qt.LeftButton, pos=position)
                    self.assertEqual(self.window.image_index, 2)
                    self.assert_linked(expected_scale=scale, expected_center=original_center)
                    QTest.mouseRelease(tree.viewport(), Qt.LeftButton, pos=position)
                    self.assertEqual(self.window.image_index, 0 if show_freeze else 2)
                    self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
                    expected = QPointF(250, 220) if auto_center else original_center
                    self.assert_linked(expected_scale=scale, expected_center=expected)

    def test_expanders_details_blank_space_and_right_clicks_do_not_reapply_cell_navigation(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        tree = self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.window.reselect_cell_ids([cell_ids[0]])
        self.set_camera(scale=1.0, center=QPointF(500, 420))
        original_center = self.center(self.window.view)
        first = tree.topLevelItem(0)
        rect = tree.visualItemRect(first)
        arrow = QPoint(rect.left() - tree.indentation() // 2, rect.center().y())
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=arrow)
            self.assertTrue(first.isExpanded())
            self.assertEqual(center.call_count, 0)
            self.assertEqual(self.window.image_index, 2)
            detail = tree.visualItemRect(first.child(0)).center()
            blank = QPoint(tree.viewport().width() // 2, tree.viewport().height() - 5)
            self.assertIsNone(tree.itemAt(blank))
            second = tree.visualItemRect(tree.topLevelItem(1)).center()
            for button, position in ((Qt.LeftButton, detail), (Qt.LeftButton, blank), (Qt.RightButton, second)):
                with self.subTest(button=button, position=position):
                    self.window.reselect_cell_ids([cell_ids[0]])
                    QTest.mouseClick(tree.viewport(), button, pos=position)
                    self.assertEqual(center.call_count, 0)
                    self.assertEqual(self.window.image_index, 2)
                    self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_same_cell_row_click_after_pan_and_wheel_zoom_preserves_pan_mode_and_zoom(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        tree = self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        point = tree.visualItemRect(tree.topLevelItem(0)).center()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.window.image_index, 0)
        self.window.panTool(True)
        self.window.navigate_to_image(2)
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        view = self.window.view
        start = view.viewport().rect().center()
        wheel = QWheelEvent(
            QPointF(start), QPointF(view.viewport().mapToGlobal(start)),
            QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False,
        )
        self.app.sendEvent(view.viewport(), wheel)
        before_drag = self.center(view)
        QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(view.viewport(), start + QPoint(35, 24), delay=10)
        QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=start + QPoint(35, 24))
        scale = view.transform().m11()
        self.assertGreater(scale, 1.0)
        self.assertGreater((self.center(view) - before_drag).manhattanLength(), 5)
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        before_click = self.center(view)
        point = tree.visualItemRect(tree.topLevelItem(0)).center()
        QTest.mousePress(tree.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.window.image_index, 2)
        self.assert_linked(expected_scale=scale, expected_center=before_click)
        QTest.mouseRelease(tree.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.window.tool_mode, "pan")
        self.assertEqual(self.window.image_index, 0)
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        self.assert_linked(expected_scale=scale, expected_center=QPointF(250, 220))

    def test_checkbox_and_list_click_do_not_navigate_while_pan_suspends_drawing_or_editing(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        tree = self.show_cells_list()
        for workflow in ("draw", "single edit", "group edit"):
            with self.subTest(workflow=workflow):
                self.window.reset_cursor_tool(True)
                self.window.cells_auto_center_checkbox.setChecked(False)
                self.window.cells_show_first_freeze_checkbox.setChecked(False)
                if workflow == "draw":
                    self.window.selectTool(True)
                    self.window.update_grid_preview_from_scene_pos(QPointF(320, 350), pin=True)
                else:
                    self.window.reselect_cell_ids(cell_ids[:1] if workflow == "single edit" else cell_ids[:2])
                    self.window.editTool(True)
                preview_origin = self.window.grid_preview_origin_pixels
                self.assertIsNotNone(preview_origin)
                self.window.panTool(True)
                self.set_camera(scale=1.0, center=QPointF(500, 420))
                original_center = self.center(self.window.view)
                with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
                    self.click_checkbox(self.window.cells_auto_center_checkbox)
                    self.click_checkbox(self.window.cells_show_first_freeze_checkbox)
                    point = tree.visualItemRect(tree.topLevelItem(2)).center()
                    QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
                    self.window.cells_freeze_event_selector.activate_event(0)
                    self.window.cells_freeze_event_selector.step_event(1)
                    self.assertEqual(center.call_count, 0)
                self.assertEqual(self.window.image_index, 2)
                self.assertEqual(self.window.tool_mode, "pan")
                self.assertEqual(self.window.grid_preview_origin_pixels, preview_origin)
                self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_cells_list_up_down_skips_expanded_details_and_preserves_focus_after_freeze_seek(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([4, 0, 3], [3, 1], [4]))
        tree = self.show_cells_list()
        for row in range(tree.topLevelItemCount()):
            tree.topLevelItem(row).setExpanded(True)
        tree.setCurrentItem(tree.topLevelItem(0))
        self.window.reselect_cell_ids([cell_ids[0]])
        tree.setFocus()
        self.set_camera(scale=1.1, center=QPointF(350, 270))
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        for key, row, frame, position in (
            (Qt.Key_Down, 1, 1, QPointF(400, 300)),
            (Qt.Key_Down, 2, 4, QPointF(350, 190)),
            (Qt.Key_Up, 1, 1, QPointF(400, 300)),
            (Qt.Key_Up, 0, 0, QPointF(250, 220)),
        ):
            with self.subTest(key=key, row=row):
                QTest.keyClick(tree, key)
                self.process_events()
                self.assertEqual(self.window.image_index, frame)
                self.assertEqual(self.selected_cell_ids(), {cell_ids[row]})
                self.assertIs(tree.currentItem(), tree.topLevelItem(row))
                self.assertEqual(tree.selectedItems(), [tree.topLevelItem(row)])
                self.assertTrue(tree.hasFocus())
                self.assertTrue(tree.topLevelItem(row).isExpanded())
                self.assert_linked(expected_scale=1.1, expected_center=position)

    def test_first_freeze_skips_missing_invalid_and_current_events_and_multiselection(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([], [-3, 5, 100], [-1, 4, 2, 99]))
        tree = self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        history_count = self.window.undo_stack.count()
        for row, position in enumerate((QPointF(250, 220), QPointF(400, 300), QPointF(350, 190))):
            with self.subTest(row=row):
                self.window.reselect_cell_ids([])
                self.set_camera(scale=1.0, center=QPointF(500, 420))
                point = tree.visualItemRect(tree.topLevelItem(row)).center()
                QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
                self.assertEqual(self.window.image_index, 2)
                self.assertEqual(self.window.undo_stack.count(), history_count)
                self.assertEqual(self.selected_cell_ids(), {cell_ids[row]})
                self.assert_linked(expected_scale=1.0, expected_center=position)

        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        self.window.cells_panel_force_refresh = True
        self.window.refresh_cells_panel()
        self.window.reselect_cell_ids([cell_ids[0]])
        second = tree.visualItemRect(tree.topLevelItem(1)).center()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.ControlModifier, second)
        self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
        self.assertEqual(self.window.image_index, 2)
        self.assertEqual(self.window.undo_stack.count(), history_count)
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(345, 280))

    def test_first_freeze_centers_the_destination_frames_interpolated_cropped_cell(self):
        cell_id = self.install_moving_cell()
        self.window.apply_cursor_tool_ui()
        self.set_freeze_frames([cell_id], ([3, 1],))
        crop = {"center_x": 280.0, "center_y": 240.0, "width": 400.0, "height": 300.0, "angle": 15.0}
        self.window.apply_image_edit_state(self.window.compose_image_edit_state(crop=crop))
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.5, center=QPointF(320, 260))
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        point = tree.visualItemRect(tree.topLevelItem(0)).center()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
        self.process_events()

        self.assertEqual(self.window.image_index, 1)
        self.assertEqual(self.selected_cell_ids(), {cell_id})
        selected = self.window.get_selected_cell_items()[0]
        self.assertEqual(selected.circle_pixel_positions, (150, 140))
        self.assertEqual(selected.circle_sizes, 15)
        expected = QPointF(*self.window.image_pixel_to_scene_coordinates(150, 140, index=1))
        self.assert_linked(expected_scale=1.5, expected_center=expected)

    def test_first_freeze_navigation_undo_and_redo_do_not_start_another_selection_navigation(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([])
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        point = tree.visualItemRect(tree.topLevelItem(0)).center()
        history_count = self.window.undo_stack.count()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=point)
        self.assertEqual(self.window.image_index, 0)
        self.assertEqual(self.window.undo_stack.count(), history_count + 1)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            self.window.undo_stack.undo()
            self.assertEqual(self.window.image_index, 2)
            self.window.undo_stack.redo()
            self.assertEqual(self.window.image_index, 0)
            self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
            self.assertEqual(center.call_count, 0)
        self.assertEqual(self.window.undo_stack.count(), history_count + 1)

    def test_center_selection_uses_circle_bounds_without_changing_zoom_or_cells(self):
        cell_ids = self.install_selection_cells()
        self.window.reselect_cell_ids(cell_ids[:2])
        self.set_camera(scale=1.6, center=QPointF(550, 410))
        before_cells = [
            (item.cell_id, item.circle_positions, item.circle_pixel_positions, item.circle_sizes)
            for item in self.window.cell_items
        ]
        before_records = copy.deepcopy(self.window.serialize_cell_records())
        before_history = self.window.undo_stack.count()

        self.assertTrue(self.window.center_on_cell_selection())
        self.process_events()

        # The unequal radii give bounds x=240..450 and y=210..350.
        # Averaging cell centers would instead produce (325, 260).
        self.assert_linked(expected_scale=1.6, expected_center=QPointF(345, 280))
        self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
        self.assertEqual([
            (item.cell_id, item.circle_positions, item.circle_pixel_positions, item.circle_sizes)
            for item in self.window.cell_items
        ], before_cells)
        self.assertEqual(self.window.serialize_cell_records(), before_records)
        self.assertEqual(self.window.undo_stack.count(), before_history)

    def test_cursor_center_button_remains_explicit_and_empty_selection_is_a_noop(self):
        self.assertFalse(self.window.cells_auto_center_checkbox.isChecked())
        self.assertFalse(hasattr(self.window, "cells_center_button"))
        self.assertEqual(self.window.cells_show_first_freeze_checkbox.text(), "Show freeze frame")
        self.window.apply_cursor_tool_ui()
        self.set_camera(scale=1.3, center=QPointF(510, 410))
        original_center = self.center(self.window.view)
        self.assertFalse(self.window.center_on_cell_selection())
        self.assertFalse(self.window.cursor_center_button.isEnabled())
        self.assert_linked(expected_scale=1.3, expected_center=original_center)

        cell_ids = self.install_selection_cells()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.assert_linked(expected_scale=1.3, expected_center=original_center)
        self.assertTrue(self.window.cursor_center_button.isEnabled())
        self.window.cursor_center_button.click()
        self.process_events()
        self.assert_linked(expected_scale=1.3, expected_center=QPointF(250, 220))

        self.window.reselect_cell_ids([])
        before_empty = self.center(self.window.view)
        self.assertFalse(self.window.center_on_cell_selection())
        self.assertFalse(self.window.cursor_center_button.isEnabled())
        self.assert_linked(expected_scale=1.3, expected_center=before_empty)

    def test_center_selection_keeps_one_two_and_three_panes_linked_at_recording_edges(self):
        self.window.apply_cursor_tool_ui()
        cell_id = self.window.cell_controller.add_single_cell((8, 10), (8, 10), 6)
        for count in (1, 2, 3):
            for frame in (0, 2, 4):
                with self.subTest(panes=count, frame=frame):
                    self.window.set_viewer_image_count(count)
                    self.window.updateImage(frame)
                    self.process_events()
                    self.set_camera(scale=0.6, center=QPointF(500, 420))
                    self.window.reselect_cell_ids([cell_id])
                    self.assertTrue(self.window.center_on_cell_selection())
                    self.process_events()
                    self.assert_linked(expected_scale=0.6, expected_center=QPointF(8, 10))
                    self.assertEqual(self.window.image_index, frame)

    def test_center_selection_uses_current_interpolated_and_cropped_geometry(self):
        cell_id = self.install_moving_cell()
        self.window.apply_cursor_tool_ui()
        crop = {"center_x": 280.0, "center_y": 240.0, "width": 400.0, "height": 300.0, "angle": 15.0}
        self.window.apply_image_edit_state(self.window.compose_image_edit_state(crop=crop))
        self.window.reselect_cell_ids([cell_id])
        selected = self.window.get_selected_cell_items()[0]
        self.assertEqual(selected.circle_pixel_positions, (200, 160))
        expected = QPointF(*self.window.image_pixel_to_scene_coordinates(200, 160, index=2))
        self.assertNotEqual(expected, QPointF(200, 160))
        self.set_camera(scale=1.5, center=QPointF(320, 260))

        self.assertTrue(self.window.center_on_cell_selection())
        self.process_events()

        self.assert_linked(expected_scale=1.5, expected_center=expected)
        self.assertEqual(selected.circle_sizes, 20)
        self.assertEqual(self.window.image_index, 2)

    def test_cells_list_auto_center_waits_for_release_and_centers_multiselection(self):
        cell_ids = self.install_selection_cells()
        tree = self.show_cells_list()
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        self.window.cells_auto_center_checkbox.setChecked(True)
        first = tree.visualItemRect(tree.topLevelItem(0)).center()
        second = tree.visualItemRect(tree.topLevelItem(1)).center()
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.mousePress(tree.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
            self.assertEqual(center.call_count, 0)
            QTest.mouseRelease(tree.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(center.call_count, 1)
            self.assert_linked(expected_scale=1.0, expected_center=QPointF(250, 220))
            QTest.mousePress(tree.viewport(), Qt.LeftButton, Qt.ControlModifier, second)
            self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
            self.assertEqual(center.call_count, 1)
            QTest.mouseRelease(tree.viewport(), Qt.LeftButton, Qt.ControlModifier, second)
            self.assertEqual(center.call_count, 2)
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(345, 280))

    def test_cells_list_keyboard_selection_centers_only_when_selection_changes(self):
        cell_ids = self.install_selection_cells()
        tree = self.show_cells_list()
        first_item = tree.topLevelItem(0)
        tree.setCurrentItem(first_item)
        self.window.reselect_cell_ids([cell_ids[0]])
        tree.setFocus()
        self.set_camera(scale=1.0, center=QPointF(500, 420))
        self.window.cells_auto_center_checkbox.setChecked(True)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.keyClick(tree, Qt.Key_Down, Qt.ShiftModifier)
            self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
            self.assertEqual(center.call_count, 1)
            self.assert_linked(expected_scale=1.0, expected_center=QPointF(345, 280))
            QTest.keyClick(tree, Qt.Key_Down, Qt.ControlModifier)
            self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
            self.assertEqual(center.call_count, 1)

    def test_viewer_click_never_uses_cells_list_automatic_navigation_options(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        view = self.window.view
        first = view.mapFromScene(QPointF(250, 220))
        original_center = self.center(view)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=first)
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        self.assert_linked(expected_scale=1.0, expected_center=original_center)

        self.window.reselect_cell_ids([])
        self.window.cells_auto_center_checkbox.setChecked(True)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(center.call_count, 0)
            self.assert_linked(expected_scale=1.0, expected_center=original_center)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(center.call_count, 0)
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        self.assert_linked(expected_scale=1.0, expected_center=original_center)
        self.assertEqual(self.window.image_index, 2)

    def test_viewer_rubber_band_never_uses_cells_list_automatic_navigation_options(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        self.window.reselect_cell_ids([])
        self.set_camera(scale=0.7, center=QPointF(350, 270))
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        view = self.window.view
        start = view.mapFromScene(QPointF(225, 205))
        end = view.mapFromScene(QPointF(460, 360))
        original_center = self.center(view)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
            QTest.mouseMove(view.viewport(), end, delay=10)
            self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
            self.assertEqual(center.call_count, 0)
            self.assert_linked(expected_scale=0.7, expected_center=original_center)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=end)
            self.assertEqual(center.call_count, 0)
        self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
        self.assert_linked(expected_scale=0.7, expected_center=original_center)
        self.assertEqual(self.window.image_index, 2)

    def test_only_cells_list_changes_navigate_automatically_and_cursor_button_remains_explicit(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [4], [1]))
        tree = self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        original_center = self.center(self.window.view)
        view = self.window.view

        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(QPointF(250, 220)))
        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
        self.assertEqual(self.window.image_index, 2)
        self.assert_linked(expected_scale=1.0, expected_center=original_center)

        second = tree.visualItemRect(tree.topLevelItem(1)).center()
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=second)
        self.assertEqual(self.selected_cell_ids(), {cell_ids[1]})
        self.assertEqual(self.window.image_index, 4)
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(400, 300))

        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(QPointF(350, 190)))
        self.assertEqual(self.selected_cell_ids(), {cell_ids[2]})
        self.assertEqual(self.window.image_index, 4)
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(400, 300))
        self.window.cursor_center_button.click()
        self.assertEqual(self.window.image_index, 4)
        self.assert_linked(expected_scale=1.0, expected_center=QPointF(350, 190))

    def test_auto_center_ignores_programmatic_selection_redraw_frames_and_history(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.set_camera(scale=1.2, center=QPointF(500, 420))
        original_center = self.center(self.window.view)
        self.window.cells_auto_center_checkbox.setChecked(True)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            self.window.cell_items[0].setSelected(True)
            self.window.reselect_cell_ids(cell_ids[:2])
            self.window.displayMarkedRegions()
            self.window.refresh_cells_panel()
            self.assertEqual(self.window.image_index, 2)
            self.window.updateImage(3)
            self.window.reselect_cell_ids([cell_ids[1]])
            self.assertTrue(self.window.delete_selected_cells())
            self.window.undo_stack.undo()
            self.window.undo_stack.redo()
            self.window.undo_stack.undo()
            self.process_events()
            self.assertEqual(center.call_count, 0)
        self.assert_linked(expected_scale=1.2, expected_center=original_center)
        self.assertEqual(self.window.image_index, 3)

    def test_auto_center_ignores_pan_and_space_pan_selection_restoration(self):
        cell_ids = self.install_selection_cells()
        self.window.reselect_cell_ids(cell_ids[:2])
        self.window.cells_auto_center_checkbox.setChecked(True)
        for temporary_pan in (False, True):
            with self.subTest(space=temporary_pan):
                self.window.apply_cursor_tool_ui()
                self.window.reselect_cell_ids(cell_ids[:2])
                self.set_camera(scale=1.0, center=QPointF(350, 270))
                if temporary_pan:
                    QTest.keyPress(self.window, Qt.Key_Space)
                else:
                    self.window.panTool(True)
                self.assertTrue(self.window.is_pan_interaction_active())
                selected_before_pan = self.selected_cell_ids()
                view = self.window.view
                start = view.viewport().rect().center()
                original_center = self.center(view)
                with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
                    QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
                    QTest.mouseMove(view.viewport(), start + QPoint(25, 20), delay=10)
                    QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=start + QPoint(25, 20))
                    if temporary_pan:
                        QTest.keyRelease(self.window, Qt.Key_Space)
                    self.assertEqual(center.call_count, 0)
                self.assertEqual(self.selected_cell_ids(), selected_before_pan)
                if temporary_pan:
                    self.assertEqual(self.selected_cell_ids(), set(cell_ids[:2]))
                self.assertGreater((self.center(view) - original_center).manhattanLength(), 5)
                self.assert_linked(expected_scale=1.0, expected_center=self.center(view))

    def test_auto_center_ignores_image_preview_crop_and_cell_edit_gestures(self):
        cell_ids = self.install_selection_cells()
        self.window.reselect_cell_ids([cell_ids[0]])
        self.window.cells_auto_center_checkbox.setChecked(True)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            self.enter_image_edit()
            self.window.handle_image_edit_exposure_spinbox_changed(0.5)
            self.window.undo_stack.undo()
            self.window.begin_image_edit_crop()
            view = self.window.view
            start = view.mapFromScene(QPointF(350, 270))
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
            QTest.mouseMove(view.viewport(), start + QPoint(12, 8), delay=10)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=start + QPoint(12, 8))
            self.window.cancel_image_edit_crop()
            self.window.apply_cursor_tool_ui()
            self.window.reselect_cell_ids([cell_ids[0]])
            self.window.activate_edit_cell_item(self.window.get_selected_cell_items()[0])
            start = view.mapFromScene(QPointF(250, 220))
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=start)
            self.assertEqual(center.call_count, 0)

    def test_auto_center_discards_selection_gesture_if_frame_changes_before_release(self):
        self.install_selection_cells()
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        self.window.cells_auto_center_checkbox.setChecked(True)
        view = self.window.view
        first = view.mapFromScene(QPointF(250, 220))
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=first)
            self.window.updateImage(3)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(center.call_count, 0)

    def test_auto_center_discards_interrupted_gestures_even_after_cursor_and_frame_return(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        tree = self.show_cells_list()
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)

        def change_frame_and_return():
            self.window.updateImage(3)
            self.window.updateImage(2)

        def change_tool_and_return():
            self.window.apply_image_edit_tool_ui()
            self.window.apply_cursor_tool_ui()

        def temporary_pan_and_return():
            QTest.keyPress(self.window, Qt.Key_Space)
            self.assertTrue(self.window.is_pan_interaction_active())
            QTest.keyRelease(self.window, Qt.Key_Space)

        interruptions = (
            self.window.displayMarkedRegions,
            change_frame_and_return,
            change_tool_and_return,
            temporary_pan_and_return,
        )
        for surface in (tree, self.window.view):
            for interrupt in interruptions:
                with self.subTest(surface=type(surface).__name__, interrupt=interrupt.__name__):
                    self.window.reselect_cell_ids([])
                    self.set_camera(scale=1.0, center=QPointF(350, 270))
                    original_center = self.center(self.window.view)
                    position = (
                        tree.visualItemRect(tree.topLevelItem(0)).center()
                        if surface is tree else surface.mapFromScene(QPointF(250, 220))
                    )
                    with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
                        QTest.mousePress(surface.viewport(), Qt.LeftButton, pos=position)
                        self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
                        interrupt()
                        self.assertEqual(self.window.tool_mode, "cursor")
                        self.assertEqual(self.window.image_index, 2)
                        self.window.reselect_cell_ids([cell_ids[0]])
                        QTest.mouseRelease(surface.viewport(), Qt.LeftButton, pos=position)
                        self.assertEqual(center.call_count, 0)
                        self.assertEqual(self.window.image_index, 2)
                    self.assert_linked(expected_scale=1.0, expected_center=original_center)

    def test_auto_center_ignores_image_edit_selection_in_viewer_and_cells_list(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        tree = self.show_cells_list()
        self.enter_image_edit()
        self.window.reselect_cell_ids([])
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        original_center = self.center(self.window.view)
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            first = self.window.view.mapFromScene(QPointF(250, 220))
            QTest.mouseClick(self.window.view.viewport(), Qt.LeftButton, pos=first)
            self.assertEqual(self.selected_cell_ids(), {cell_ids[0]})
            second = tree.visualItemRect(tree.topLevelItem(1)).center()
            QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=second)
            self.assertEqual(self.selected_cell_ids(), {cell_ids[1]})
            QTest.keyClick(tree, Qt.Key_Down)
            self.assertEqual(self.selected_cell_ids(), {cell_ids[2]})
            self.assertEqual(center.call_count, 0)
        self.assert_linked(expected_scale=1.0, expected_center=original_center)
        self.assertEqual(self.window.image_index, 2)

    def test_auto_center_ignores_single_and_group_edit_apply_and_return_to_cursor(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        for selected_ids in ([cell_ids[0]], cell_ids[:2]):
            with self.subTest(selected_ids=selected_ids):
                self.window.reset_cursor_tool(True)
                self.window.reselect_cell_ids(selected_ids)
                self.set_camera(scale=1.0, center=QPointF(350, 270))
                original_center = self.center(self.window.view)
                before_positions = {
                    item.cell_id: item.circle_pixel_positions
                    for item in self.window.cell_items if item.cell_id in selected_ids
                }
                with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
                    self.window.editTool(True)
                    self.assertEqual(self.window.tool_mode, "edit-new" if len(selected_ids) == 1 else "edit-group")
                    self.window.preview_offset_x = 35.0
                    self.window.preview_offset_y = 20.0
                    self.window.update_grid_preview()
                    if len(selected_ids) == 1:
                        self.window.handle_circle_apply_action()
                    else:
                        self.window.handle_grid_apply_action()
                    self.window.reset_cursor_tool(True)
                    self.process_events()
                    self.assertEqual(center.call_count, 0)
                self.assertEqual(self.window.tool_mode, "cursor")
                self.assertEqual(self.window.image_index, 2)
                self.assert_linked(expected_scale=1.0, expected_center=original_center)
                for item in self.window.cell_items:
                    if item.cell_id in selected_ids:
                        previous = before_positions[item.cell_id]
                        self.assertEqual(item.circle_pixel_positions, (previous[0] + 35.0, previous[1] + 20.0))

    def test_auto_center_ignores_add_and_delete_gestures_and_return_to_cursor(self):
        cell_ids = self.install_selection_cells()
        self.set_freeze_frames(cell_ids, ([0], [0], [0]))
        self.window.cells_auto_center_checkbox.setChecked(True)
        self.window.cells_show_first_freeze_checkbox.setChecked(True)
        self.set_camera(scale=1.0, center=QPointF(350, 270))
        original_center = self.center(self.window.view)
        view = self.window.view
        with patch.object(self.window, "center_on_cell_selection", wraps=self.window.center_on_cell_selection) as center:
            self.window.selectTool(True)
            position = view.mapFromScene(QPointF(320, 350))
            QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=position)
            self.assertFalse(self.window.grid_preview_floating)
            self.window.handle_circle_apply_action()
            self.assertEqual(len(self.window.cell_items), len(cell_ids) + 1)
            self.window.reset_cursor_tool(True)
            self.window.apply_deselect_tool_ui()
            position = view.mapFromScene(QPointF(250, 220))
            QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=position)
            self.assertNotIn(cell_ids[0], {item.cell_id for item in self.window.cell_items})
            self.window.reset_cursor_tool(True)
            self.process_events()
            self.assertEqual(center.call_count, 0)
        self.assert_linked(expected_scale=1.0, expected_center=original_center)
        self.assertEqual(self.window.image_index, 2)

    def test_each_panel_uses_its_own_cell_keyframe_and_interpolation(self):
        self.install_moving_cell()
        for panel, expected in zip(self.panels(), [(150, 140, 15), (200, 160, 20), (250, 180, 25)]):
            items = self.window.cell_items if panel.is_current else panel.cell_items
            item = self.assert_cell_geometry(items, expected)
            self.assertEqual(item.circle_positions, expected[:2])

        # Exact keyframes and frames outside the marked span use the saved
        # geometry, independently of which frame occupies the current panel.
        self.window.keyframe_list = [1, 3]
        first, last = self.window.keyframe_cell_items_dict.values()
        self.window.keyframe_cell_items_dict = {1: first, 3: last}
        for index, expected in ((2, [(100, 120, 10), (300, 200, 30)]),
                                (1, [(100, 120, 10), (200, 160, 20)]),
                                (3, [(200, 160, 20), (300, 200, 30)])):
            with self.subTest(current=index):
                self.window.updateImage(index)
                for panel, geometry in zip(self.viewer.reference_panels, expected):
                    self.assert_cell_geometry(panel.cell_items, geometry)

    def test_reference_rendering_keeps_cell_models_registry_and_selection_unchanged(self):
        self.install_moving_cell()
        primary = list(self.window.cell_items)
        primary[0].setSelected(True)
        models = copy.deepcopy(self.window.keyframe_cell_items_dict)
        registry = copy.deepcopy(self.window.serialize_cell_records())
        next_id = self.window.next_cell_id
        history_count = self.window.undo_stack.count()
        for _ in range(3):
            self.viewer.refresh_reference_cells()
        self.assertEqual(self.window.cell_items, primary)
        self.assertTrue(primary[0].isSelected())
        self.assertIs(primary[0].scene(), self.window.scene)
        self.assertEqual(self.window.keyframe_cell_items_dict, models)
        self.assertEqual(self.window.serialize_cell_records(), registry)
        self.assertEqual(self.window.next_cell_id, next_id)
        self.assertEqual(self.window.undo_stack.count(), history_count)
        for panel in self.viewer.reference_panels:
            item = panel.cell_items[0]
            self.assertIs(item.scene(), panel.scene)
            self.assertIsNot(item, primary[0])
            self.assertFalse(item.flags() & CellCircle.ItemIsSelectable)
            self.assertEqual(item.acceptedMouseButtons(), Qt.NoButton)
            self.assertFalse(item.acceptHoverEvents())

    def test_reference_cells_follow_each_frames_crop_transform(self):
        # A crop is normalized against each source image. Using the current
        # frame's dimensions would misplace the previous frame's circle.
        small_path = self.root / "small.png"
        small = QImage(320, 240, QImage.Format_RGB32)
        small.fill(Qt.gray)
        self.assertTrue(small.save(str(small_path)))
        paths = list(self.paths)
        paths[1] = small_path
        self.window.set_frame_source(ImageSequenceFrameSource(paths))
        self.window.updateImage(2)
        self.install_moving_cell()
        crop = {"center_x": 400.0, "center_y": 300.0, "width": 400.0, "height": 300.0, "angle": 15.0}
        self.window.apply_image_edit_state(self.window.compose_image_edit_state(crop=crop))
        for panel in self.viewer.reference_panels:
            item = panel.cell_items[0]
            expected = self.window.image_pixel_to_scene_coordinates(
                *item.circle_pixel_positions, panel.pixmap_item.sceneBoundingRect(), index=panel.frame_index
            )
            self.assertEqual(item.circle_positions, expected)
        previous = self.viewer.previous.cell_items[0]
        current_transform = self.window.image_pixel_to_scene_coordinates(*previous.circle_pixel_positions, index=2)
        self.assertNotEqual(previous.circle_positions, current_transform)
        self.enter_image_edit()
        self.window.begin_image_edit_crop()
        for panel in self.viewer.reference_panels:
            self.assertEqual(panel.cell_items[0].circle_positions, panel.cell_items[0].circle_pixel_positions)
        self.window.cancel_image_edit_crop()
        self.assertEqual(self.viewer.previous.cell_items[0].circle_positions, previous.circle_positions)

    def test_reference_cells_refresh_after_keyframe_edit_rename_delete_and_undo(self):
        cell_id = self.install_moving_cell()
        # The fixture loads the source directly rather than through Open Images.
        self.window.image_slider.setEnabled(True)
        self.window.image_slider.toggle_keyframe()
        self.assertIn(2, self.window.keyframe_list)
        self.window.cell_items[0].setSelected(True)
        self.window.cell_controller.replace_active_edit_cell((300, 240), (300, 240), 40)
        self.assert_cell_geometry(self.viewer.previous.cell_items, (200, 180, 25))
        self.assert_cell_geometry(self.viewer.next.cell_items, (300, 220, 35))
        self.window.image_slider.toggle_keyframe()
        self.assert_cell_geometry(self.viewer.previous.cell_items, (150, 140, 15))
        self.assert_cell_geometry(self.viewer.next.cell_items, (250, 180, 25))
        self.window.undo_stack.undo()
        self.assert_cell_geometry(self.viewer.previous.cell_items, (200, 180, 25))

        # Rename through the same control as Edit Cell, then delete in Cursor.
        self.window.activate_edit_cell_item(self.window.cell_items[0])
        self.window.edit_circle_cell_id_spinbox.setValue(cell_id + 10)
        self.window.apply_edit_circle_cell_id_edit()
        self.assertEqual([panel.cell_items[0].cell_id for panel in self.viewer.reference_panels], [cell_id + 10] * 2)
        self.window.undo_stack.undo()
        self.assertEqual([panel.cell_items[0].cell_id for panel in self.viewer.reference_panels], [cell_id] * 2)
        self.window.apply_cursor_tool_ui()
        self.window.cell_items[0].setSelected(True)
        self.assertTrue(self.window.delete_selected_cells())
        self.assertEqual([panel.cell_items for panel in self.viewer.reference_panels], [[], []])
        self.window.undo_stack.undo()
        self.assertEqual([panel.cell_items[0].cell_id for panel in self.viewer.reference_panels], [cell_id] * 2)

    def test_reference_cells_without_keyframes_clear_with_hidden_missing_or_preview_frames(self):
        self.window.cell_controller.add_single_cell((350, 270), (350, 270), 25)
        for panel in self.viewer.reference_panels:
            self.assert_cell_geometry(panel.cell_items, (350, 270, 25))
        self.window.set_viewer_image_count(2)
        self.assertEqual(self.viewer.next.cell_items, [])
        self.window.updateImage(0)
        self.assertEqual(self.viewer.previous.cell_items, [])
        self.window.set_viewer_image_count(3)
        self.window.updateImage(2)
        with patch.object(self.window, "is_video_source", return_value=True):
            self.window.updateImage(3, preview=True)
        self.assertEqual([panel.cell_items for panel in self.viewer.reference_panels], [[], []])
        self.window.updateImage(2)
        self.window.clear_loaded_images(confirm=False)
        self.assertEqual([panel.cell_items for panel in self.viewer.reference_panels], [[], []])

    def test_sample_assignment_undo_and_redo_repaint_cells_in_every_panel(self):
        cell_id = self.window.cell_controller.add_single_cell((350, 270), (350, 270), 25)
        self.set_camera(scale=1.0)
        self.window.cell_items[0].setSelected(True)
        self.window.create_sample_from_cursor_controls()
        assigned_color = self.window.sample_visual_color_for_cell(cell_id).name()
        self.process_events()

        # Observe scene invalidation rather than forcing a render: restored
        # metadata must schedule repainting of the neighboring cell labels.
        for action, expected_color in ((self.window.undo_stack.undo, None),
                                       (self.window.undo_stack.redo, assigned_color)):
            with self.subTest(action=action):
                changes = [QSignalSpy(panel.view.scene().changed) for panel in self.panels()]
                action()
                self.process_events()
                for panel, signal in zip(self.panels(), changes):
                    self.assertGreater(signal.count(), 0)
                    items = self.window.cell_items if panel.is_current else panel.cell_items
                    color = items[0].main_window.sample_visual_color_for_cell(items[0].cell_id)
                    self.assertEqual(color.name() if color is not None else None, expected_color)

    def test_panels_have_separate_scenes_and_keep_neighbor_slots_at_recording_edges(self):
        self.assertEqual(len({id(panel.view.scene()) for panel in self.panels()}), 3)
        self.assertIs(self.viewer.current.view, self.window.view)
        self.assertEqual(self.window.zoom_textbox.text(), f"{self.window.view.transform().m11() * 100:.0f}")
        self.assert_panel_images([1, 2, 3])
        for panel in self.panels():
            pixmaps = [item for item in panel.view.scene().items() if isinstance(item, QGraphicsPixmapItem)]
            self.assertEqual(len(pixmaps), 1)
        self.window.set_viewer_image_count(2)
        self.process_events()
        self.assert_panel_images([1, 2])
        self.window.updateImage(0)
        self.assert_panel_images([None, 0])
        self.window.set_viewer_image_count(3)
        self.window.updateImage(4)
        self.process_events()
        self.assert_panel_images([3, 4, None])

    def test_wheel_zoom_and_drag_pan_in_every_panel_update_all_views(self):
        self.window.cell_controller.add_single_cell((350, 270), (350, 270), 50)
        self.window.panTool(True)
        self.set_camera()
        for panel in self.panels():
            with self.subTest(panel=panel):
                view = panel.view
                position = view.viewport().rect().center()
                previous_scale = view.transform().m11()
                wheel = QWheelEvent(
                    QPointF(position), QPointF(view.viewport().mapToGlobal(position)),
                    QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                    Qt.NoScrollPhase, False,
                )
                self.app.sendEvent(view.viewport(), wheel)
                self.process_events()
                self.assertGreater(view.transform().m11(), previous_scale)
                self.assert_linked(expected_scale=view.transform().m11(), expected_center=self.center(view))
                before_pan = self.center(view)
                QTest.mousePress(view.viewport(), Qt.LeftButton, pos=position)
                QTest.mouseMove(view.viewport(), position + QPoint(35, 24), delay=10)
                QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=position + QPoint(35, 24))
                self.process_events()
                after_pan = self.center(view)
                self.assertGreater((after_pan - before_pan).manhattanLength(), 5)
                self.assert_linked(expected_center=after_pan)

    def test_manual_zoom_navigation_resize_and_layout_preserve_shared_camera(self):
        self.set_camera(scale=1.6)
        center = self.center(self.window.view)
        self.assert_linked(expected_scale=1.6, expected_center=center)
        self.window.navigate_to_image(3)
        self.process_events()
        self.assert_panel_images([2, 3, 4])
        self.assert_linked(expected_scale=1.6, expected_center=center)
        self.window.resize(1350, 850)
        self.process_events()
        self.assert_linked(expected_scale=1.6, expected_center=center)
        for count in (2, 1, 3) * 3:
            self.window.set_viewer_image_count(count)
            self.process_events()
            self.assert_linked(expected_scale=1.6, expected_center=center)
        self.window.toggle_viewer_split_orientation()
        self.process_events()
        self.assert_linked(expected_scale=1.6, expected_center=center)

    def test_edge_center_stays_linked_with_different_frame_dimensions(self):
        # Imported recordings may contain differently sized source images. Camera
        # alignment uses image pixel coordinates, rather than each image's center.
        dimensions = [(800, 600), (320, 240), (800, 600), (1100, 900), (800, 600)]
        paths = []
        for index, (width, height) in enumerate(dimensions):
            path = self.root / f"mixed_size_{index}.png"
            image = QImage(width, height, QImage.Format_RGB32)
            image.fill(QColor(self.brightness[index], self.brightness[index], self.brightness[index]))
            self.assertTrue(image.save(str(path)))
            paths.append(path)
        self.window.set_frame_source(ImageSequenceFrameSource(paths))
        self.window.updateImage(2)
        for panel, dimensions in zip(self.panels(), dimensions[1:4]):
            self.assertEqual((panel.view.content_rect.width(), panel.view.content_rect.height()), dimensions)
        for position in (QPointF(1, 1), QPointF(790, 590)):
            with self.subTest(position=position):
                self.set_camera(scale=0.6, center=position)
                center = self.center(self.window.view)
                for count in (2, 3) * 3:
                    self.window.set_viewer_image_count(count)
                    self.window.toggle_viewer_split_orientation()
                    self.process_events()
                    self.assert_linked(expected_scale=0.6, expected_center=center)

    def test_reference_mouse_and_delete_keys_leave_current_cells_unchanged(self):
        self.window.cell_controller.add_single_cell((350.0, 270.0), (350.0, 270.0), 25.0)
        self.set_camera(scale=1.5)
        current_cell = next(item for item in self.window.scene.items() if isinstance(item, CellCircle))
        current_cell.setSelected(True)
        before = [(item.cell_id, item.circle_pixel_positions, item.circle_sizes) for item in self.window.cell_items]
        for panel in self.viewer.reference_panels:
            start = panel.view.mapFromScene(QPointF(350, 270))
            QTest.mousePress(panel.view.viewport(), Qt.LeftButton, pos=start)
            QTest.mouseMove(panel.view.viewport(), start + QPoint(35, 24), delay=10)
            QTest.mouseRelease(panel.view.viewport(), Qt.LeftButton, pos=start + QPoint(35, 24))
            for key in (Qt.Key_Delete, Qt.Key_Backspace):
                QTest.keyClick(panel.view, key)
            after = [(item.cell_id, item.circle_pixel_positions, item.circle_sizes) for item in self.window.cell_items]
            self.assertEqual(after, before)
        self.window.apply_deselect_tool_ui()
        for panel in self.viewer.reference_panels:
            QTest.mouseClick(panel.view.viewport(), Qt.LeftButton, pos=panel.view.mapFromScene(QPointF(350, 270)))
        self.assertEqual([(item.cell_id, item.circle_pixel_positions, item.circle_sizes) for item in self.window.cell_items], before)

    def test_exposure_and_contrast_preview_refresh_every_panel_and_undo(self):
        self.enter_image_edit()
        self.set_camera()
        center = self.center(self.window.view)
        for count in (2, 3):
            with self.subTest(count=count):
                self.window.set_viewer_image_count(count)
                self.window.handle_image_edit_exposure_spinbox_changed(1.0)
                self.assertEqual([self.panel_pixel(panel) for panel in self.visible_panels()], [120, 160, 200][:count])
                self.window.handle_image_edit_contrast_spinbox_changed(50.0)
                self.assertEqual([self.panel_pixel(panel) for panel in self.visible_panels()], [116, 176, 236][:count])
                self.assert_linked(expected_center=center)
                self.window.undo_stack.undo()
                self.assertEqual([self.panel_pixel(panel) for panel in self.visible_panels()], [120, 160, 200][:count])
                self.window.undo_stack.undo()
                self.assert_panel_images([1, 2, 3][:count])

    def test_uniform_exposure_uses_each_panels_frame_offset(self):
        self.enter_image_edit()
        offsets = {self.window.frame_key(1): 1.0, self.window.frame_key(2): 0.0, self.window.frame_key(3): -1.0}
        self.window.apply_image_edit_state(self.window.compose_image_edit_state(
            uniform_exposure={"area": {"x": 100, "y": 100, "width": 200, "height": 200}, "offsets": offsets}
        ))
        self.assertEqual([self.panel_pixel(panel) for panel in self.panels()], [120, 80, 50])

    def test_crop_draft_cancel_apply_and_undo_update_all_panels(self):
        self.enter_image_edit()
        self.set_camera(scale=1.5, center=QPointF(350, 260))
        original_raw_center = self.window.scene_to_image_pixel_coordinates(self.center(self.window.view))
        original = self.window.current_image_edit_crop_state()
        crop = {"center_x": 400.0, "center_y": 300.0, "width": 400.0, "height": 300.0, "angle": 15.0}
        self.window.begin_image_edit_crop()
        self.window.handle_image_edit_crop_overlay_changed(crop, finalize=True)
        self.assertEqual(self.window.current_image_edit_crop_state(), original)
        for panel in self.panels():
            self.assertEqual(self.panel_pixmap_item(panel).pixmap().size().width(), 800)
        self.window.cancel_image_edit_crop()
        self.assertEqual(self.window.current_image_edit_crop_state(), original)
        self.window.begin_image_edit_crop()
        self.window.handle_image_edit_crop_overlay_changed(crop, finalize=True)
        self.window.apply_image_edit_crop()
        self.assertEqual(self.window.current_image_edit_crop_state(), crop)
        for panel in self.panels():
            self.assertEqual(self.panel_pixmap_item(panel).pixmap().size().width(), 400)
            self.assertEqual(self.panel_pixmap_item(panel).pixmap().size().height(), 300)
        self.assert_linked()
        cropped_raw_center = self.window.scene_to_image_pixel_coordinates(self.center(self.window.view))
        for before, after in zip(original_raw_center, cropped_raw_center):
            self.assertAlmostEqual(before, after, delta=2.1 / 1.5)
        self.window.undo_stack.undo()
        self.assertEqual(self.window.current_image_edit_crop_state(), original)
        self.assertEqual([self.panel_pixmap_item(panel).pixmap().width() for panel in self.panels()], [800, 800, 800])
        self.window.undo_stack.redo()
        self.assertEqual([self.panel_pixmap_item(panel).pixmap().width() for panel in self.panels()], [400, 400, 400])

    def test_crop_overlay_from_reference_changes_one_shared_draft(self):
        self.window.cell_controller.add_single_cell((350, 260), (350, 260), 50)
        self.enter_image_edit()
        self.window.begin_image_edit_crop()
        reference = self.viewer.previous
        self.assertTrue(reference.crop_overlay.isVisible())
        crop = {"center_x": 350.0, "center_y": 260.0, "width": 450.0, "height": 320.0, "angle": 10.0}
        reference.crop_overlay.cropChanged.emit(crop)
        reference.crop_overlay.cropChangeFinished.emit(crop)
        self.assertEqual(self.window.get_image_edit_crop_draft_state(), crop)
        for overlay in (self.window.image_edit_crop_overlay, self.viewer.previous.crop_overlay, self.viewer.next.crop_overlay):
            self.assertEqual(overlay._crop_state, crop)
        self.set_camera(scale=0.7, center=QPointF(350, 260))
        start = reference.view.mapFromScene(QPointF(350, 260))
        QTest.mousePress(reference.view.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(reference.view.viewport(), start + QPoint(21, 14), delay=10)
        QTest.mouseRelease(reference.view.viewport(), Qt.LeftButton, pos=start + QPoint(21, 14))
        moved = self.window.get_image_edit_crop_draft_state()
        self.assertGreater(moved["center_x"], crop["center_x"])
        self.assertGreater(moved["center_y"], crop["center_y"])
        for overlay in (self.window.image_edit_crop_overlay, self.viewer.previous.crop_overlay, self.viewer.next.crop_overlay):
            self.assertEqual(overlay._crop_state, moved)
        self.assertEqual(self.window.image_index, 2)
        self.window.cancel_image_edit_crop()
        self.assertFalse(reference.crop_overlay.isVisible())

    def test_uniform_area_overlay_from_reference_updates_current_and_other_reference(self):
        self.enter_image_edit()
        self.window.begin_image_edit_uniform_exposure_area()
        reference = self.viewer.next
        self.assertTrue(reference.uniform_overlay.isVisible())
        area = {"x": 120.0, "y": 90.0, "width": 220.0, "height": 180.0}
        reference.uniform_overlay.areaChanged.emit(area)
        reference.uniform_overlay.areaChangeFinished.emit(area)
        self.assertEqual(self.window.current_image_edit_uniform_exposure_area_state(), area)
        for overlay in (self.window.image_edit_uniform_exposure_overlay, self.viewer.previous.uniform_overlay, self.viewer.next.uniform_overlay):
            self.assertEqual(overlay.area_state(), area)
        self.set_camera(scale=0.7, center=QPointF(230, 180))
        start = reference.view.mapFromScene(QPointF(230, 180))
        QTest.mousePress(reference.view.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(reference.view.viewport(), start + QPoint(21, 14), delay=10)
        QTest.mouseRelease(reference.view.viewport(), Qt.LeftButton, pos=start + QPoint(21, 14))
        moved = self.window.current_image_edit_uniform_exposure_area_state()
        self.assertGreater(moved["x"], area["x"])
        self.assertGreater(moved["y"], area["y"])
        for overlay in (self.window.image_edit_uniform_exposure_overlay, self.viewer.previous.uniform_overlay, self.viewer.next.uniform_overlay):
            self.assertEqual(overlay.area_state(), moved)
        self.assertEqual(self.window.image_index, 2)

    def test_video_scrub_preview_does_not_read_neighbors_or_leave_stale_reference_frames(self):
        with patch.object(self.window, "is_video_source", return_value=True), patch.object(
            self.window, "get_cached_image", wraps=self.window.get_cached_image
        ) as read_frame:
            self.window.updateImage(3, preview=True)
        self.assertEqual({call.args[0] for call in read_frame.call_args_list}, {3})
        for panel in self.viewer.reference_panels:
            self.assertIsNone(panel.frame_index)
            self.assertTrue(panel.pixmap_item.pixmap().isNull())
        self.window.handle_committed_image_slider_value(3)
        self.assert_panel_images([2, 3, 4])

    def test_video_scrub_returning_to_start_restores_reference_frames_on_release(self):
        history_count = self.window.undo_stack.count()
        self.window.handle_image_slider_pressed()
        with patch.object(self.window, "is_video_source", return_value=True):
            self.window.updateImage(3, preview=True)
            self.window.updateImage(2, preview=True)
            self.assertTrue(self.window.comparison_preview_pending)
            self.assertEqual([panel.frame_index for panel in self.viewer.reference_panels], [None, None])
            self.window.handle_image_slider_released()
        self.assert_panel_images([1, 2, 3])
        self.assertFalse(self.window.comparison_preview_pending)
        self.assertIsNone(self.window.slider_drag_start_index)
        self.assertEqual(self.window.undo_stack.count(), history_count)

    def test_clear_and_reload_do_not_keep_reference_images_or_overlay_state(self):
        self.enter_image_edit()
        self.window.begin_image_edit_crop()
        self.window.clear_loaded_images(confirm=False)
        self.assertFalse(self.window.has_frames())
        self.assertIsNone(self.viewer.current.pixmap_item)
        self.assertIsNone(self.viewer.current.frame_index)
        for panel in self.viewer.reference_panels:
            self.assertIsNone(panel.frame_index)
            self.assertTrue(panel.pixmap_item is None or panel.pixmap_item.pixmap().isNull())
            self.assertTrue(panel.crop_overlay is None or not panel.crop_overlay.isVisible())
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.window.updateImage(1)
        self.window.set_viewer_image_count(3)
        self.process_events()
        self.assert_panel_images([0, 1, 2])


if __name__ == "__main__":
    unittest.main()
