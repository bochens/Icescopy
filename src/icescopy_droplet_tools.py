"""Current-frame droplet detection controls, separate from saved session data."""

from dataclasses import dataclass
import math

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QAction, QImage
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from icescopy_cell_items import CellCircle
from icescopy_image_edit import apply_affine_to_point


def qimage_to_rgb(image):
    """Copy original pixels without exposure, contrast, or crop adjustments."""
    if image is None or image.isNull():
        raise ValueError("The current frame has no readable image.")
    image = image.convertToFormat(QImage.Format_RGB888)
    rows = np.frombuffer(image.bits(), dtype=np.uint8, count=image.sizeInBytes())
    rows = rows.reshape(image.height(), image.bytesPerLine())
    return rows[:, :image.width() * 3].reshape(image.height(), image.width(), 3).copy()


def _circle_geometry(item):
    return (float(item.circle_pixel_positions[0]),
            float(item.circle_pixel_positions[1]), float(item.circle_sizes))


def _layout_geometry(items):
    return tuple(sorted((int(item.cell_id), *_circle_geometry(item)) for item in items))


def _freeze_value(value):
    """Comparable copy of small nested settings."""
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True)
class DetectionSnapshot:
    token: tuple
    rgb: np.ndarray
    protected: tuple
    examples: tuple
    crop_matrix: object
    output_size: tuple


class DetectionWorker(QThread):
    results_ready = Signal(object)
    failed = Signal(str)
    detection_cancelled = Signal()

    def __init__(self, model, snapshot, parent=None):
        super().__init__(parent)
        self.model = model
        self.snapshot = snapshot

    def run(self):
        try:
            from icescopy_neural_detection import Circle, NeuralDetector
            detector = NeuralDetector(self.model)
            results = detector.predict(
                self.snapshot.rgb,
                examples=tuple(Circle(*geometry) for geometry in self.snapshot.examples),
                protected=tuple(Circle(*geometry) for geometry in self.snapshot.protected),
                cancelled=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                self.detection_cancelled.emit()
            else:
                self.results_ready.emit(results)
        except Exception as error:
            if self.isInterruptionRequested():
                self.detection_cancelled.emit()
            else:
                self.failed.emit(str(error))


class DropletDetectionTools(QObject):
    """Load the bundled model on demand without making the session dirty."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.model = None
        self.model_path = ""
        self.worker = None
        self.progress = None
        self.snapshot = None
        self.completion_message = None

    def install_menu(self, analysis_menu):
        menu = analysis_menu.addMenu("Droplet Detection (Experimental)")
        self.detect_action = QAction("Detect Droplets (Current Frame)", self.window)
        self.detect_action.setToolTip(
            "Use original pixels and add droplets inside the current crop. "
            "Selected marked cells guide appearance and size. "
            "With no selection, automatic detection may be less accurate."
        )
        self.detect_action.triggered.connect(self.start_detection)
        menu.addAction(self.detect_action)
        self.update_actions()

    def is_running(self):
        return self.worker is not None

    def update_actions(self):
        if not hasattr(self, "detect_action"):
            return
        busy = self.is_running()
        analysis_busy = bool(getattr(self.window, "output_state", False))
        self.detect_action.setEnabled(
            bool(getattr(self.window, "session_active", False))
            and self.window.has_frames() and not busy and not analysis_busy
        )
        # Analysis would change the results while the detector is taking its
        # snapshot. Navigation/editing remain available; stale results are dropped.
        if busy and hasattr(self.window, "run_analysis_action"):
            self.window.run_analysis_action.setEnabled(False)

    def current_token(self):
        window = self.window
        if not window.has_frames():
            return None
        index = int(window.image_index)
        return (
            id(window.active_frame_source()), index, window.frame_key(index),
            _layout_geometry(window.keyframe_interpolation(index)),
            tuple(sorted(int(item.cell_id) for item in window.get_selected_cell_items())),
            tuple((int(frame), _layout_geometry(items)) for frame, items in
                  sorted(window.keyframe_cell_items_dict.items())),
            tuple(window.keyframe_list), int(window.next_cell_id),
            tuple((int(cell_id), str(record.sample_id), tuple(record.freeze_event_indices))
                  for cell_id, record in sorted(window.cell_records_by_id.items())),
            _freeze_value(window.current_image_edit_crop_state(index=index)),
            bool(window.should_apply_crop_in_display()),
            int(window.undo_stack.index()),
        )

    def snapshot_current_frame(self):
        window = self.window
        if not window.has_frames():
            raise ValueError("Load an image or video before detecting droplets.")
        if getattr(window, "output_state", False):
            raise ValueError("Wait for the current analysis to finish.")
        # Current-frame interpolation is the same source used to draw the cells.
        items = list(window.keyframe_interpolation(window.image_index))
        selected_ids = {int(item.cell_id) for item in window.get_selected_cell_items()}
        examples = tuple(_circle_geometry(item) for item in items if int(item.cell_id) in selected_ids)
        if len(examples) != len(selected_ids):
            raise ValueError("The selected examples do not belong to the current frame. Select current cells.")
        # Fast video previews can come from a JPEG cache. Detection uses decoded
        # video pixels, so discard that preview copy before reading the frame.
        window.discard_preview_raw_frame_cache(window.image_index)
        rgb = qimage_to_rgb(window.get_cached_raw_image(window.image_index))
        _state, matrix, _inverse, size = window.current_image_edit_crop_transform()
        return DetectionSnapshot(
            token=self.current_token(), rgb=rgb,
            protected=tuple(_circle_geometry(item) for item in items),
            examples=examples,
            crop_matrix=None if matrix is None else np.array(matrix, copy=True),
            output_size=tuple(size),
        )

    def start_detection(self):
        if self.is_running():
            return
        try:
            snapshot = self.snapshot_current_frame()
            path = str(getattr(self.window, "droplet_model_path", "") or "")
            # External files can be updated between runs. Validate them again;
            # keep the loaded config alive for this worker's entire run.
            if self.model is None or path or path != self.model_path:
                from icescopy_neural_detection import load_model
                self.model = load_model(path) if path else load_model()
                self.model_path = path
        except Exception as error:
            QMessageBox.warning(self.window, "Droplet Detection", str(error))
            return
        self.snapshot = snapshot
        self.completion_message = None
        self.worker = DetectionWorker(self.model, snapshot, self)
        self.worker.results_ready.connect(self._results_ready)
        self.worker.failed.connect(self._failed)
        self.worker.detection_cancelled.connect(self._cancelled)
        self.worker.finished.connect(self._finished)
        self.progress = QProgressDialog(self.window)
        self.progress.setWindowTitle("Detect Droplets")
        self.progress.setLabelText(
            "Finding droplets in this frame.\n"
            f"Selected examples: {len(snapshot.examples)}.\n"
            "Only circles inside the current crop are added."
        )
        self.progress.setRange(0, 0)
        self.progress.setCancelButtonText("Cancel")
        self.progress.setMinimumDuration(0)
        self.progress.setMinimumWidth(440)
        self.progress.canceled.connect(self.cancel_detection)
        self.progress.show()
        self.update_actions()
        self.worker.start()

    def cancel_detection(self):
        if self.worker is not None:
            self.worker.requestInterruption()
            if self.progress is not None:
                self.progress.setLabelText("Cancelling droplet detection...")

    def _results_ready(self, results):
        if self.worker is not None and self.worker.isInterruptionRequested():
            self._cancelled()
            return
        try:
            count = self.add_results(self.snapshot, results)
        except Exception as error:
            self._failed(str(error))
            return
        if count is None:
            self.window.log("Droplet detections discarded because the frame, source, crop, cells, or selected examples changed. Run detection again on the current frame.")
        else:
            self.completion_message = (
                f"Model: {self.model.name}\n"
                f"Version: {self.model.version}\n"
                f"Guidance cells: {len(self.snapshot.examples)}\n"
                f"New cells found: {len(results)}\n"
                f"Cells added: {count}"
            )
            if count != len(results):
                self.completion_message += "\n\nOnly new cells fully inside the current crop are added."
            self.window.log(self.completion_message.replace("\n", " · "))

    def _failed(self, message):
        self.window.log(f"Droplet detection failed: {message}")
        QMessageBox.warning(self.window, "Droplet Detection", message)

    def _cancelled(self):
        self.window.log("Droplet detection cancelled; no cells added.")

    def _finished(self):
        completion_message, self.completion_message = self.completion_message, None
        worker, self.worker = self.worker, None
        if self.progress is not None:
            self.progress.close()
            self.progress.deleteLater()
            self.progress = None
        self.snapshot = None
        if worker is not None:
            worker.deleteLater()
        self.window.update_session_actions_state()
        if completion_message is not None:
            self.window.show_detailed_information_dialog("Droplet Detection Complete", completion_message)

    def add_results(self, snapshot, results):
        """Insert a batch using the manual-add ID, keyframe, and undo rules."""
        if snapshot is None or snapshot.token != self.current_token():
            return None
        from icescopy_neural_detection import Circle, same_object
        accepted = []
        height, width = snapshot.rgb.shape[:2]
        for result in results:
            geometry = result["circle"]
            x, y, radius = (float(geometry[key]) for key in ("x", "y", "radius"))
            if not all(math.isfinite(value) for value in (x, y, radius)) or radius <= 0:
                continue
            # Fully contained circles avoid hidden or clipped measurement areas.
            if x - radius < 0 or y - radius < 0 or x + radius > width or y + radius > height:
                continue
            display_x, display_y = x, y
            if snapshot.crop_matrix is not None:
                display_x, display_y = apply_affine_to_point(snapshot.crop_matrix, x, y)
            crop_width, crop_height = snapshot.output_size
            if (display_x - radius < 0 or display_y - radius < 0
                    or display_x + radius > crop_width or display_y + radius > crop_height):
                continue
            circle = Circle(x, y, radius)
            if any(same_object(circle, Circle(*other)) for other in (*snapshot.protected, *accepted)):
                continue
            accepted.append((x, y, radius))
        if not accepted:
            return 0

        window = self.window
        before_state = window.capture_cell_state(include_analysis=True)
        added_items = []
        try:
            for x, y, radius in accepted:
                scene_position = window.image_pixel_to_scene_coordinates(x, y)
                item = CellCircle(window, scene_position, radius, (x, y), window.allocate_cell_id())
                window.cell_items.append(item)
                added_items.append(item)
            window.displayMarkedRegions()
            window.add_cell_item_to_keyframes(added_items)
            window.ensure_cell_registry_matches_scene_cells()
            window.invalidate_analysis_results("droplet cells added")
            window.refresh_cells_panel()
            window.refresh_comparison_cells()
            window.update_session_actions_state()
        except Exception:
            window.restore_cell_state(before_state, preserve_active_tool=True)
            raise
        window.push_cell_history("Detect Droplets", before_state, include_analysis=True)
        return len(added_items)
