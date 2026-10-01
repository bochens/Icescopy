import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import warnings
import zipfile


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from icescopy_droplet_detection import CancelledError, Circle, load_model
import icescopy_droplet_trainer as trainer
import icescopy_droplet_training_io as training_io
from icescopy_session_io import SESSION_SCHEMA_VERSION, save_session_bundle


def circle_payload(x=12, y=13, radius=4):
    return {
        "circle_positions": [x + 500, y + 500],
        "circle_pixel_positions": [x, y],
        "circle_sizes": radius,
        "cell_id": 7,
        "edit_chosen": True,
    }


def write_session(folder, *, name="training.icescopy", paths=None, current=1, keyframes=True, payload=None):
    folder = Path(folder)
    if paths is None:
        paths = []
        for index in range(3):
            path = folder / f"frame_{index}.png"
            pixels = np.empty((37, 43, 3), dtype=np.uint8)
            pixels[:] = [index + 11, index + 31, index + 61]
            Image.fromarray(pixels).save(path)
            paths.append(str(path))
    if payload is None:
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "frame_source": {"kind": "image_sequence", "image_paths": list(paths)},
            "image_paths": list(paths),
            "image_index": current,
            "image_width": 1500,
            "image_edit_state": {
                "exposure": 3.0,
                "contrast": 90.0,
                "crop_state": {"center_x": 30, "center_y": 20, "width": 12, "height": 14, "angle": 70},
            },
            "cell_items": [circle_payload()],
            "keyframe_cell_items_dict": {
                "0": [circle_payload(7, 8, 3)],
                str(current): [circle_payload(18, 19, 5)],
                "2": [circle_payload(22, 23, 4)],
            } if keyframes else {},
        }
    path = folder / name
    save_session_bundle(path, payload, ["cell"], [[1]], ["freeze"], [[2]], ["count"], [[3]])
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TrainingSessionTests(unittest.TestCase):
    def test_current_and_explicit_keyframes_use_raw_pixels_and_never_read_results(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_session(td)
            files = [path, *Path(td).glob("*.png")]
            originals = {str(item): (digest(item), item.stat().st_mtime_ns) for item in files}
            opened = []
            original_open = zipfile.ZipFile.open

            def guarded_open(archive, member, *args, **kwargs):
                member_name = getattr(member, "filename", member)
                opened.append(member_name)
                self.assertEqual(member_name, "session.json")
                return original_open(archive, member, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "open", guarded_open):
                session = training_io.load_training_session(path)
            self.assertEqual(opened, ["session.json"])
            self.assertEqual(session.saved_frame_index, 1)
            self.assertEqual([frame.index for frame in session.frames], [1, 0, 2])
            self.assertEqual(session.frame(1).circles, (Circle(12, 13, 4),))
            scenes = training_io.load_training_scenes(session, [1, 0])
            self.assertEqual(len(scenes), 2)
            self.assertEqual(scenes[0]["image"].shape, (37, 43, 3))
            self.assertEqual(scenes[0]["image"].dtype, np.uint8)
            np.testing.assert_array_equal(scenes[0]["image"][0, 0], [12, 32, 62])
            self.assertEqual(scenes[0]["circles"], [Circle(12, 13, 4)])
            self.assertEqual(scenes[1]["circles"], [Circle(7, 8, 3)])
            for item in files:
                self.assertEqual((digest(item), item.stat().st_mtime_ns), originals[str(item)])

    def test_legacy_and_relative_media_paths_are_supported_without_cwd_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "one.png"
            Image.new("RGB", (30, 30), (10, 20, 30)).save(image)
            payload = {"image_paths": ["one.png"], "cell_items": [circle_payload()]}
            path = write_session(td, payload=payload)
            session = training_io.load_training_session(path)
            self.assertEqual(session.source_payload, {"kind": "image_sequence", "image_paths": ["one.png"]})
            self.assertEqual(session.saved_frame_index, 0)
            scene = training_io.load_training_scenes(session, [0])[0]
            np.testing.assert_array_equal(scene["image"][0, 0], [10, 20, 30])

    def test_missing_media_relink_is_per_session_and_does_not_modify_saved_paths(self):
        with tempfile.TemporaryDirectory() as td:
            paths = ["C:\\old\\frame_0.png", "C:\\old\\frame_1.png", "C:\\old\\frame_2.png"]
            path = write_session(td, paths=paths)
            media = Path(td) / "moved"
            media.mkdir()
            Image.new("RGB", (43, 37), (19, 29, 39)).save(media / "frame_1.png")
            saved_digest = digest(path)
            session = training_io.load_training_session(path)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "Missing linked media"):
                training_io.load_training_scenes(session, [1])
            relinked = session.relinked(media)
            scene = training_io.load_training_scenes(relinked, [1])[0]
            np.testing.assert_array_equal(scene["image"][0, 0], [19, 29, 39])
            self.assertIsNone(session.relink_folder)
            self.assertEqual(relinked.source_payload["image_paths"], paths)
            self.assertEqual(digest(path), saved_digest)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "Missing linked media"):
                training_io.load_training_scenes(relinked, [1, 0])

    def test_relink_refuses_two_distinct_sources_with_the_same_filename(self):
        with tempfile.TemporaryDirectory() as td:
            Image.new("RGB", (43, 37)).save(Path(td) / "one.png")
            path = write_session(td, paths=["/first/one.png", "/second/one.png", "/third/other.png"])
            session = training_io.load_training_session(path).relinked(td)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "cannot distinguish"):
                training_io.validate_training_sources(session, [1, 0])

    def test_unknown_unannotated_frame_and_empty_selected_frame_are_visible_errors(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_session(td, keyframes=False)
            session = training_io.load_training_session(path)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "no saved annotations"):
                training_io.load_training_scenes(session, [0])
            with self.assertRaisesRegex(training_io.TrainingSessionError, "at least one"):
                training_io.load_training_scenes(session, [])
            with zipfile.ZipFile(path) as archive:
                payload = json.loads(archive.read("session.json"))
            payload["cell_items"] = []
            empty_path = write_session(td, name="empty.icescopy", payload=payload)
            empty = training_io.load_training_session(empty_path)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "no marked circles"):
                training_io.load_training_scenes(empty, [1])

    def test_corrupt_or_newer_sessions_are_not_silently_treated_as_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.icescopy"
            cases = [
                (b"not a zip", "Unable to read"),
                (b"{broken", "Unable to read"),
                (b"[]", "JSON object"),
                (b'{"image_index":0,"image_index":1}', "Duplicate session JSON key"),
                (json.dumps({"schema_version": SESSION_SCHEMA_VERSION + 1}).encode(), "newer Icescopy"),
            ]
            for content, error_text in cases:
                with self.subTest(content=content):
                    if content == b"not a zip":
                        path.write_bytes(content)
                    else:
                        with zipfile.ZipFile(path, "w") as archive:
                            archive.writestr("session.json", content)
                    with self.assertRaisesRegex(training_io.TrainingSessionError, error_text):
                        training_io.load_training_session(path)

    def test_bounded_state_and_duplicate_archive_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_session(td)
            with self.assertRaisesRegex(training_io.TrainingSessionError, "limit"):
                training_io.load_training_session(path, max_state_bytes=50)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(path, "a") as archive:
                    archive.writestr("session.json", "{}")
            with self.assertRaisesRegex(training_io.TrainingSessionError, "exactly one"):
                training_io.load_training_session(path)

    def test_decoder_is_closed_after_failure_and_cancel_before_open_does_not_decode(self):
        with tempfile.TemporaryDirectory() as td:
            session = training_io.load_training_session(write_session(td))

            class FailingSource:
                closed = False
                def frame_count(self):
                    return 3
                def get_qimage(self, index):
                    raise ValueError("broken image")
                def close(self):
                    self.closed = True

            source = FailingSource()
            with patch.object(training_io, "frame_source_from_session_payload", return_value=source):
                with self.assertRaisesRegex(training_io.TrainingSessionError, "broken image"):
                    training_io.load_training_scenes(session, [1])
            self.assertTrue(source.closed)
            with patch.object(training_io, "frame_source_from_session_payload") as create_source:
                with self.assertRaises(CancelledError):
                    training_io.load_training_scenes(session, [1], cancelled=lambda: True)
                create_source.assert_not_called()

    def test_video_reads_only_the_explicit_selected_saved_frame(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "saved.mp4"
            video.touch()
            payload = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "frame_source": {"kind": "video", "video_path": str(video)},
                "image_index": 3,
                "cell_items": [circle_payload()],
                "keyframe_cell_items_dict": {"1": [circle_payload(8, 9, 3)]},
            }
            session = training_io.load_training_session(write_session(td, payload=payload))

            class SelectedFrameSource:
                def __init__(self):
                    self.read_indexes = []
                    self.closed = False
                def frame_count(self):
                    return 12
                def get_qimage(self, index):
                    self.read_indexes.append(index)
                    image = QImage(43, 37, QImage.Format_RGB888)
                    image.fill(Qt.white)
                    return image
                def frame_key(self, index):
                    return f"saved.mp4:frame:{index}"
                def close(self):
                    self.closed = True

            source = SelectedFrameSource()
            with patch.object(training_io, "frame_source_from_session_payload", return_value=source):
                scenes = training_io.load_training_scenes(session, [3])
            self.assertEqual(source.read_indexes, [3])
            self.assertTrue(source.closed)
            self.assertEqual(scenes[0]["circles"], [Circle(12, 13, 4)])
            self.assertEqual(scenes[0]["source_key"], "saved.mp4:frame:3")

    @unittest.skipUnless(importlib.util.find_spec("av"), "PyAV is not installed")
    def test_saved_video_frame_decodes_real_linked_media(self):
        import av
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "linked.mp4"
            with av.open(str(video), "w") as output:
                stream = output.add_stream("mpeg4", rate=2)
                stream.width, stream.height, stream.pix_fmt = 40, 36, "yuv420p"
                for value in (30, 80, 130, 180):
                    image = np.full((36, 40, 3), value, dtype=np.uint8)
                    for packet in stream.encode(av.VideoFrame.from_ndarray(image, format="rgb24")):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            payload = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "frame_source": {"kind": "video", "video_path": str(video)},
                "image_index": 2,
                "cell_items": [circle_payload()],
                "keyframe_cell_items_dict": {"0": [circle_payload(8, 9, 3)]},
            }
            path = write_session(td, payload=payload)
            original_digest = digest(video)
            scenes = training_io.load_training_scenes(training_io.load_training_session(path), [2, 0])
            self.assertEqual([scene["image"].shape for scene in scenes], [(36, 40, 3)] * 2)
            self.assertAlmostEqual(float(scenes[0]["image"].mean()), 130, delta=4)
            self.assertAlmostEqual(float(scenes[1]["image"].mean()), 30, delta=4)
            self.assertEqual(digest(video), original_digest)


class DropletTrainerWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.cancel_training()
        self.wait_until(lambda: all(not window.is_training() for window in self.windows))
        for window in self.windows:
            window.close()
        self.app.processEvents()

    def window(self, **kwargs):
        window = trainer.DropletTrainerWindow(**kwargs)
        self.windows.append(window)
        return window

    def wait_until(self, predicate, timeout=6):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            # Qt's qWait can retain the Python lock while waiting. Yield it so
            # first-time imports and training can run in the Python worker.
            time.sleep(0.01)
        self.app.processEvents()
        self.assertTrue(predicate(), "Qt worker or window did not finish in time")

    def test_default_current_frame_and_user_checked_keyframes_are_the_only_examples(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_session(td)
            window = self.window(initial_session_paths=[path])
            self.assertEqual(window._selections[0].frame_indexes, {1})
            self.assertEqual(window.frame_list.count(), 3)
            self.assertEqual(window.frame_list.item(0).checkState(), Qt.Checked)
            self.assertEqual(window.frame_list.item(1).checkState(), Qt.Unchecked)
            window.frame_list.item(1).setCheckState(Qt.Checked)
            received = []
            main_thread = threading.get_ident()

            def fitted(scenes, progress=None, cancelled=None):
                self.assertNotEqual(threading.get_ident(), main_thread)
                received.extend(scenes)
                progress("Training fixture completed.")
                return {"training_stats": {"images": 2, "circles": 2, "samples": 10}}

            with patch.object(trainer, "fit_model", fitted):
                window.start_training()
                self.assertTrue(window.is_training())
                self.assertFalse(window.session_table.isEnabled())
                self.wait_until(lambda: not window.is_training())
            self.assertEqual([scene["circles"] for scene in received], [[Circle(7, 8, 3)], [Circle(12, 13, 4)]])
            self.assertTrue(window.save_button.isEnabled())
            self.assertIn("Training complete", window.status_label.text())
            window.frame_list.item(1).setCheckState(Qt.Unchecked)
            self.assertFalse(window.save_button.isEnabled())

    def test_missing_sources_disable_training_until_that_session_is_relinked(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_session(td, paths=["/missing/frame_0.png", "/missing/frame_1.png", "/missing/frame_2.png"])
            Image.new("RGB", (43, 37)).save(Path(td) / "frame_1.png")
            saved_digest = digest(path)
            window = self.window(initial_session_paths=[path])
            self.assertFalse(window.train_button.isEnabled())
            self.assertIn("Missing", window.session_table.item(0, 3).text())
            window.relink_session(0, td)
            self.assertTrue(window.train_button.isEnabled())
            self.assertIn("relinked", window.session_table.item(0, 3).text())
            self.assertEqual(digest(path), saved_digest)

    def test_training_error_is_visible_and_leaves_the_window_ready_to_retry(self):
        with tempfile.TemporaryDirectory() as td:
            window = self.window(initial_session_paths=[write_session(td)])
            def failed(*args, **kwargs):
                raise ValueError("Every droplet needs a complete marking.")
            with patch.object(trainer, "fit_model", failed), patch.object(QMessageBox, "warning") as warning:
                window.start_training()
                self.wait_until(lambda: not window.is_training())
                warning.assert_called_once()
            self.assertIn("complete marking", window.status_label.text())
            self.assertTrue(window.train_button.isEnabled())
            self.assertFalse(window.save_button.isEnabled())

    def test_close_cooperatively_cancels_and_waits_for_worker_before_hiding(self):
        with tempfile.TemporaryDirectory() as td:
            window = self.window(initial_session_paths=[write_session(td)])
            window.show()
            entered = threading.Event()
            may_finish = threading.Event()
            def waiting_fit(scenes, progress=None, cancelled=None):
                entered.set()
                deadline = time.monotonic() + 4
                while not cancelled() and time.monotonic() < deadline:
                    may_finish.wait(0.01)
                # Even a late result must be discarded after cancellation.
                may_finish.wait(0.1)
                return {"training_stats": {"images": 1, "circles": 1, "samples": 10}}
            with patch.object(trainer, "fit_model", waiting_fit):
                window.start_training()
                self.wait_until(entered.is_set)
                window.close()
                self.assertTrue(window.is_training())
                self.assertTrue(window.isVisible())
                self.assertTrue(window._worker.cancellation_requested())
                may_finish.set()
                self.wait_until(lambda: not window.is_training())
            self.assertFalse(window.isVisible())
            self.assertIsNone(window._model)
            window.cancel_training()  # Safe when no worker exists.

    def test_saved_model_signal_is_sent_only_after_success_and_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            window = self.window()
            window._model = {"training_stats": {}}
            received = []
            window.model_saved.connect(received.append)
            path = Path(td) / "new.icescopy-model.json"
            def save_fixture(model, destination, overwrite=False):
                self.assertFalse(overwrite)
                with open(destination, "x") as output:
                    output.write("fixture model")
            with patch.object(trainer, "save_model", save_fixture), patch.object(QMessageBox, "warning"):
                self.assertTrue(window.save_model_to(path))
                saved_digest = digest(path)
                self.assertFalse(window.save_model_to(path))
            self.assertEqual(received, [str(path.resolve())])
            self.assertEqual(digest(path), saved_digest)

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "The optional training dependency is not installed")
    def test_real_session_trains_and_saves_a_reloadable_small_model(self):
        import cv2
        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "droplets.png"
            image = np.full((128, 144, 3), 185, dtype=np.uint8)
            circles = [circle_payload(35, 35, 11), circle_payload(100, 35, 11), circle_payload(65, 95, 11)]
            for circle in circles:
                center = tuple(circle["circle_pixel_positions"])
                cv2.circle(image, center, 11, (70, 70, 70), 2)
                cv2.circle(image, center, 8, (215, 215, 215), -1)
            Image.fromarray(image).save(image_path)
            payload = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "frame_source": {"kind": "image_sequence", "image_paths": [str(image_path)]},
                "image_index": 0,
                "cell_items": circles,
                "keyframe_cell_items_dict": {},
            }
            path = write_session(td, payload=payload)
            protected = {item: digest(item) for item in (path, image_path)}
            window = self.window(initial_session_paths=[path])
            with patch.object(QMessageBox, "warning") as warning:
                window.start_training()
                self.wait_until(lambda: not window.is_training(), timeout=30)
                self.assertIsNotNone(window._model, window.status_label.text())
                warning.assert_not_called()
                model_path = Path(td) / "droplets.icescopy-model.json"
                self.assertTrue(window.save_model_to(model_path))
            model = load_model(model_path)
            self.assertEqual(model["training_stats"]["images"], 1)
            self.assertEqual(model["training_stats"]["circles"], 3)
            self.assertGreater(model["training_stats"]["positive_samples"], 0)
            self.assertGreater(model["training_stats"]["negative_samples"], 0)
            self.assertLess(model_path.stat().st_size, 5 * 1024 * 1024)
            for item, original in protected.items():
                self.assertEqual(digest(item), original)

    def test_open_helper_uses_the_existing_app_and_keeps_the_window_alive(self):
        with patch.object(QApplication, "exec", side_effect=AssertionError("Must not start another event loop")):
            window = trainer.open_droplet_trainer()
        self.windows.append(window)
        self.assertIs(QApplication.instance(), self.app)
        self.assertTrue(window.isVisible())
        self.assertIn(window, self.app._icescopy_droplet_trainer_windows)


if __name__ == "__main__":
    unittest.main()
