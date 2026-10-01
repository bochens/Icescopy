import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QCloseEvent, QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from Icescopy import IceScopy
from icescopy_cell_items import CellSnapshot
from icescopy_droplet_tools import qimage_to_rgb
from icescopy_frame_source import ImageSequenceFrameSource, VideoFrameSource


def detection(x, y, radius=8):
    return {"circle": {"x": x, "y": y, "radius": radius}, "score": 0.9}


class DropletToolsTests(unittest.TestCase):
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
        # 201 RGB pixels also exercise QImage's padded scan lines.
        for index in range(3):
            path = self.root / f"frame_{index:03d}.png"
            image = QImage(201, 160, QImage.Format_RGB32)
            image.fill(QColor(20 + index * 20, 70, 110))
            self.assertTrue(image.save(str(path)))
            self.paths.append(str(path))
        self.window = IceScopy()
        self.addCleanup(self.dispose_window)
        self.window.session_active = True
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.window.populate_image_list()
        self.window.updateImage(1)
        self.window.update_session_actions_state()
        self.tools = self.window.droplet_tools
        completion = patch.object(self.window, "show_detailed_information_dialog")
        self.completion = completion.start()
        self.addCleanup(completion.stop)

    def dispose_window(self):
        self.tools.cancel_detection()
        if self.tools.worker is not None:
            self.tools.worker.wait(3000)
        self.app.processEvents()
        self.window.hide()
        self.window.stop_video_preview_decoder()
        close_source = getattr(self.window.active_frame_source(), "close", None)
        if close_source is not None:
            close_source()
        self.window.deleteLater()
        self.app.processEvents()

    def add_keyframed_cell(self):
        first = CellSnapshot((60, 60), 8, (60, 60), 7)
        last = CellSnapshot((100, 60), 8, (100, 60), 7)
        self.window.keyframe_list = [0, 2]
        self.window.keyframe_cell_items_dict = {0: [first], 2: [last]}
        self.window.ensure_cell_record(7).sample_id = "sample A"
        self.window.interpolate_and_displayMarkedRegions(1)
        return self.window.cell_items[0]

    def wait_for_detection(self):
        for _attempt in range(300):
            self.app.processEvents()
            if not self.tools.is_running():
                return
            QTest.qWait(10)
        self.fail("Droplet detection did not finish within three seconds.")

    def test_builtin_model_loads_lazily_once_without_changing_session_content(self):
        self.window.mark_session_clean()
        self.assertIsNone(self.tools.model)
        model = SimpleNamespace(name="Test droplets", version="1.2.3")
        with patch("icescopy_neural_detection.load_model", return_value=model) as load, patch("icescopy_neural_detection.NeuralDetector") as detector:
            detector.return_value.predict.return_value = []
            load.assert_not_called()
            for _ in range(2):
                self.tools.start_detection()
                self.wait_for_detection()
            load.assert_called_once_with()
            self.assertEqual(detector.call_count, 2)
            self.assertEqual(detector.return_value.predict.call_args.kwargs["examples"], ())
        self.assertIs(self.tools.model, model)
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_zero_one_two_and_more_selected_examples_use_current_geometry(self):
        items = [CellSnapshot((30 + 25 * index, 70), 8, (30 + 25 * index, 70), index)
                 for index in range(5)]
        self.window.keyframe_list = [1]
        self.window.keyframe_cell_items_dict = {1: items}
        for index in range(5):
            self.window.ensure_cell_record(index)
        self.window.interpolate_and_displayMarkedRegions(1)
        for count in (0, 1, 2, 3, 5):
            with self.subTest(examples=count):
                for index, cell in enumerate(self.window.cell_items):
                    cell.setSelected(index < count)
                snapshot = self.tools.snapshot_current_frame()
                self.assertEqual(snapshot.examples,
                                 tuple((30.0 + 25 * index, 70.0, 8.0) for index in range(count)))
                self.assertEqual(len(snapshot.protected), 5)

    def test_model_choice_changes_between_runs_and_external_is_revalidated(self):
        builtin = SimpleNamespace(name="General droplets", version="1.0.0")
        custom = SimpleNamespace(name="My droplets", version="2.0.0")
        def selected(path=None):
            return builtin if path is None else custom
        with patch("icescopy_neural_detection.load_model", side_effect=selected) as load, patch("icescopy_neural_detection.NeuralDetector") as detector:
            detector.return_value.predict.return_value = []
            for path in ("", "/tmp/custom.icescopy-model", "/tmp/custom.icescopy-model", ""):
                self.window.droplet_model_path = path
                self.tools.start_detection()
                self.wait_for_detection()
                message = self.completion.call_args.args[1]
                self.assertIn("Version: 2.0.0" if path else "Version: 1.0.0", message)
                self.assertIn("Guidance cells: 0", message)
                self.assertIn("New cells found: 0", message)
            self.assertEqual(load.call_count, 4)
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_missing_custom_model_does_not_use_previously_loaded_default(self):
        self.tools.model = SimpleNamespace(name="General droplets", version="1.0.0")
        self.window.droplet_model_path = "/tmp/missing.icescopy-model"
        with patch("icescopy_neural_detection.load_model", side_effect=FileNotFoundError("Missing selected model")) as load, patch("icescopy_droplet_tools.QMessageBox.warning") as warning:
            self.tools.start_detection()
        load.assert_called_once_with(self.window.droplet_model_path)
        warning.assert_called_once()
        self.assertIsNone(self.tools.worker)
        self.completion.assert_not_called()

    def test_changing_selected_examples_discards_stale_results(self):
        cell = self.add_keyframed_cell()
        cell.setSelected(True)
        snapshot = self.tools.snapshot_current_frame()
        cell.setSelected(False)
        self.assertIsNone(self.tools.add_results(snapshot, [detection(140, 70)]))
        self.assertEqual(len(self.window.cell_items), 1)
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_raw_pixels_and_selected_examples_use_current_keyframe_geometry(self):
        cell = self.add_keyframed_cell()
        cell.setSelected(True)
        self.window.apply_image_edit_state({"exposure": 2, "contrast": 50, "crop": {
            "center_x": 100, "center_y": 80, "width": 140, "height": 100, "angle": 25,
        }})
        snapshot = self.tools.snapshot_current_frame()
        self.assertEqual(snapshot.rgb.shape, (160, 201, 3))
        np.testing.assert_array_equal(snapshot.rgb[0, 0], [40, 70, 110])
        self.assertEqual(snapshot.protected, ((80.0, 60.0, 8.0),))
        self.assertEqual(snapshot.examples, ((80.0, 60.0, 8.0),))

    def test_batch_is_one_undo_command_and_restores_keyframes_records_and_analysis(self):
        self.add_keyframed_cell()
        self.window.grayscale_results_headers = ["file_name", "cell_7_grayscale"]
        self.window.grayscale_results_rows = [[f"frame_{index:03d}.png", 10 + index] for index in range(3)]
        self.window.sync_cell_analysis_from_results()
        self.window.apply_manual_freeze_event_indices(7, [2])
        original = self.window.capture_cell_state(include_analysis=True)
        self.window.mark_session_clean()
        snapshot = self.tools.snapshot_current_frame()
        results = [detection(81, 60), detection(140, 70), detection(141, 70), detection(40, 115)]
        self.assertEqual(self.tools.add_results(snapshot, results), 2)
        self.assertEqual(self.window.undo_stack.count(), 1)
        self.assertTrue(self.window.has_unsaved_session_changes())
        self.assertEqual(len({item.cell_id for item in self.window.cell_items}), 3)
        self.assertEqual(self.window.grayscale_results_rows, [])
        self.assertEqual(self.window.cell_records_by_id[7].sample_id, "sample A")
        for frame in (0, 2):
            items = self.window.keyframe_cell_items_dict[frame]
            self.assertEqual(len(items), 3)
            original_item = next(item for item in items if item.cell_id == 7)
            self.assertEqual(original_item.circle_pixel_positions, (60, 60) if frame == 0 else (100, 60))
        self.window.undo_stack.undo()
        self.assertEqual(len(self.window.cell_items), 1)
        self.assertEqual(self.window.serialize_cell_records(), original["cell_records_by_id"])
        self.assertEqual(self.window.grayscale_results_rows, original["grayscale_results_rows"])
        self.assertEqual(self.window.next_cell_id, original["next_cell_id"])
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.window.undo_stack.redo()
        self.assertEqual(len(self.window.cell_items), 3)
        self.assertEqual(self.window.grayscale_results_rows, [])

    def test_later_frame_repeat_detection_preserves_existing_cells(self):
        self.add_keyframed_cell()
        self.tools.add_results(self.tools.snapshot_current_frame(), [detection(140, 70)])
        self.window.updateImage(2)
        before = [(item.cell_id, item.circle_pixel_positions, item.circle_sizes) for item in self.window.cell_items]
        self.assertEqual(self.tools.add_results(self.tools.snapshot_current_frame(), [detection(101, 60), detection(140, 70)]), 0)
        self.assertEqual([(item.cell_id, item.circle_pixel_positions, item.circle_sizes) for item in self.window.cell_items], before)
        self.assertEqual(self.window.undo_stack.count(), 1)

    def test_rotated_crop_and_all_comparison_layouts_keep_original_coordinates(self):
        for panes in (1, 2, 3):
            with self.subTest(panes=panes):
                self.window.set_viewer_image_count(panes)
                self.window.apply_image_edit_state({"crop": {
                    "center_x": 100, "center_y": 80, "width": 110, "height": 90, "angle": 30,
                }})
                snapshot = self.tools.snapshot_current_frame()
                count = self.tools.add_results(snapshot, [detection(120, 90), detection(10, 10)])
                self.assertEqual(count, 1)
                item = self.window.cell_items[0]
                self.assertEqual(item.circle_pixel_positions, (120.0, 90.0))
                expected = self.window.image_pixel_to_scene_coordinates(120, 90)
                np.testing.assert_allclose(item.circle_positions, expected)
                mapped = self.window.scene_to_image_pixel_coordinates(QPointF(*item.circle_positions))
                np.testing.assert_allclose(mapped, [120, 90])
                self.window.undo_stack.undo()

    def test_stale_frame_source_crop_or_cell_edit_drops_results(self):
        self.add_keyframed_cell()
        snapshot = self.tools.snapshot_current_frame()
        self.window.updateImage(2)
        self.assertIsNone(self.tools.add_results(snapshot, [detection(140, 70)]))
        snapshot = self.tools.snapshot_current_frame()
        self.window.keyframe_cell_items_dict[0][0].circle_sizes = 10
        self.assertIsNone(self.tools.add_results(snapshot, [detection(140, 70)]))
        snapshot = self.tools.snapshot_current_frame()
        self.window.image_edit_crop_angle = 10
        self.assertIsNone(self.tools.add_results(snapshot, [detection(140, 70)]))
        snapshot = self.tools.snapshot_current_frame()
        self.window.set_frame_source(ImageSequenceFrameSource(self.paths))
        self.assertIsNone(self.tools.add_results(snapshot, [detection(140, 70)]))
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_cancelled_worker_adds_nothing_and_reenables_actions(self):
        entered = threading.Event()

        class WaitingDetector:
            def __init__(self, model):
                pass

            def predict(self, image, *, examples, protected, cancelled):
                entered.set()
                while not cancelled():
                    threading.Event().wait(0.005)
                return [detection(100, 80)]

        self.tools.model = SimpleNamespace(name="Test droplets", version="1.2.3")
        with patch("icescopy_neural_detection.NeuralDetector", WaitingDetector):
            self.tools.start_detection()
            self.assertTrue(entered.wait(1))
            self.assertFalse(self.window.run_analysis_action.isEnabled())
            self.tools.cancel_detection()
            self.wait_for_detection()
        self.assertEqual(self.window.cell_items, [])
        self.assertEqual(self.window.undo_stack.count(), 0)
        self.assertTrue(self.tools.detect_action.isEnabled())
        self.assertTrue(self.window.run_analysis_action.isEnabled())
        self.assertIsNone(self.tools.progress)

    def test_successful_worker_uses_raw_examples_and_adds_one_undo_batch(self):
        cell = self.add_keyframed_cell()
        cell.setSelected(True)
        calls = []

        class ReturningDetector:
            def __init__(self, model):
                pass

            def predict(self, image, *, examples, protected, cancelled):
                calls.append((image.copy(), examples, protected))
                return [detection(140, 70), detection(40, 115)]

        self.tools.model = SimpleNamespace(name="Test droplets", version="1.2.3")
        with patch("icescopy_neural_detection.NeuralDetector", ReturningDetector):
            self.tools.start_detection()
            self.wait_for_detection()
        self.completion.assert_called_once()
        title, message = self.completion.call_args.args
        self.assertEqual(title, "Droplet Detection Complete")
        for text in ("Model: Test droplets", "Version: 1.2.3", "Guidance cells: 1", "New cells found: 2", "Cells added: 2"):
            self.assertIn(text, message)
        self.assertEqual(len(calls), 1)
        image, examples, protected = calls[0]
        np.testing.assert_array_equal(image[0, 0], [40, 70, 110])
        self.assertEqual([(item.x, item.y, item.radius) for item in examples], [(80, 60, 8)])
        self.assertEqual(examples, protected)
        self.assertEqual(len(self.window.cell_items), 3)
        self.assertEqual(self.window.undo_stack.count(), 1)
        self.assertIsNone(self.tools.progress)

    def test_worker_failure_is_reported_and_leaves_session_unchanged(self):
        self.tools.model = SimpleNamespace(name="Test droplets", version="1.2.3")
        self.window.mark_session_clean()
        with patch("icescopy_neural_detection.NeuralDetector", side_effect=ImportError("Missing detector dependency")), patch("icescopy_droplet_tools.QMessageBox.warning") as warning:
            self.tools.start_detection()
            self.wait_for_detection()
        warning.assert_called_once()
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.assertEqual(self.window.cell_items, [])
        self.assertIsNone(self.tools.progress)

    def test_main_close_cancels_detection_and_defers_destruction(self):
        worker = Mock()
        self.tools.worker = worker
        event = QCloseEvent()
        with patch("Icescopy.QMessageBox.information") as information:
            self.window.closeEvent(event)
        worker.requestInterruption.assert_called_once()
        information.assert_called_once()
        self.assertFalse(event.isAccepted())
        self.tools.worker = None

    def test_detection_menu_contains_only_current_frame_detection(self):
        menu = self.tools.detect_action.associatedObjects()
        actions = next(item for item in menu if hasattr(item, "actions")).actions()
        self.assertEqual([action.text() for action in actions],
                         ["Detect Droplets (Current Frame)"])

    def test_failed_insertion_rolls_back_all_cells_and_keyframes(self):
        self.add_keyframed_cell()
        before = self.window.capture_cell_state(include_analysis=True)
        snapshot = self.tools.snapshot_current_frame()
        with patch.object(self.window, "add_cell_item_to_keyframes", side_effect=RuntimeError("Cannot update cells")):
            with self.assertRaisesRegex(RuntimeError, "Cannot update cells"):
                self.tools.add_results(snapshot, [detection(140, 70)])
        self.assertEqual(self.window.serialize_cell_records(), before["cell_records_by_id"])
        self.assertEqual(len(self.window.cell_items), 1)
        self.assertEqual({frame: len(items) for frame, items in self.window.keyframe_cell_items_dict.items()}, {0: 1, 2: 1})
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_empty_frame_is_reported_before_loading_builtin_model(self):
        self.window.set_frame_source(ImageSequenceFrameSource([]))
        with patch("icescopy_droplet_tools.QMessageBox.warning") as warning, patch("icescopy_neural_detection.load_model") as load:
            self.tools.start_detection()
        warning.assert_called_once()
        load.assert_not_called()
        self.assertIsNone(self.tools.worker)
        with self.assertRaisesRegex(ValueError, "Load an image or video"):
            self.tools.snapshot_current_frame()

    def test_builtin_model_error_is_reported_without_session_changes(self):
        self.window.mark_session_clean()
        with patch("icescopy_neural_detection.load_model", side_effect=ValueError("Bundled model is missing")), patch("icescopy_droplet_tools.QMessageBox.warning") as warning:
            self.tools.start_detection()
        warning.assert_called_once()
        self.assertIsNone(self.tools.worker)
        self.assertIsNone(self.tools.model)
        self.assertFalse(self.window.has_unsaved_session_changes())
        self.assertEqual(self.window.undo_stack.count(), 0)

    def test_duplicates_match_neural_distance_rule_and_protect_unselected_cells(self):
        cell = self.add_keyframed_cell()
        cell.setSelected(True)
        self.tools.add_results(self.tools.snapshot_current_frame(), [detection(140, 70)])
        self.window.cell_items[0].setSelected(True)
        self.window.cell_items[1].setSelected(False)
        snapshot = self.tools.snapshot_current_frame()
        before = self.window.undo_stack.count()
        # Seven pixels is below the minimum eight-pixel radius for both pairs.
        self.assertEqual(self.tools.add_results(snapshot, [detection(87, 60), detection(147, 70)]), 0)
        self.assertEqual(len(self.window.cell_items), 2)
        self.assertEqual(self.window.undo_stack.count(), before)

    def test_video_snapshot_uses_same_decoded_rgb_path(self):
        try:
            import av
        except ImportError:
            self.skipTest("PyAV is not installed")
        path = self.root / "frames.mp4"
        with av.open(str(path), mode="w") as container:
            stream = container.add_stream("mpeg4", rate=10)
            stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
            for level in (30, 80, 130):
                frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), level, dtype=np.uint8), format="rgb24")
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        source = VideoFrameSource(str(path), preview_cache_dir=self.root / "preview")
        self.window.set_frame_source(source)
        self.window.updateImage(1)
        preview = QImage(64, 48, QImage.Format_RGB888)
        preview.fill(QColor(250, 0, 0))
        self.window.cache_raw_frame_image(1, preview, preview_cache=True)
        snapshot = self.tools.snapshot_current_frame()
        np.testing.assert_array_equal(snapshot.rgb, qimage_to_rgb(source.get_qimage(1)))
        self.assertEqual(snapshot.rgb.shape, (48, 64, 3))
        self.assertGreater(float(np.mean(snapshot.rgb)), 60)
        self.assertLess(float(np.mean(snapshot.rgb)), 100)


if __name__ == "__main__":
    unittest.main()
