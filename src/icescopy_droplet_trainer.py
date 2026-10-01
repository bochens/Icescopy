"""Separate, user-controlled training window for Icescopy droplet models."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from icescopy_droplet_detection import CancelledError, fit_model, save_model
from icescopy_droplet_training_io import (
    TrainingSession,
    TrainingSessionError,
    load_training_scenes,
    load_training_session,
    validate_training_sources,
)


@dataclass
class _SessionSelection:
    session: TrainingSession
    frame_indexes: set[int] = field(default_factory=set)


class TrainingWorker(QThread):
    """Read images and train away from the window's event-processing thread."""

    progress = Signal(str)
    model_ready = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, selections, parent=None, *, fit_function=None):
        super().__init__(parent)
        self.selections = tuple((session, tuple(indexes)) for session, indexes in selections)
        self._cancel_event = threading.Event()
        self._fit_function = fit_function or fit_model

    def request_cancel(self):
        self._cancel_event.set()

    def cancellation_requested(self):
        return self._cancel_event.is_set()

    def run(self):
        try:
            scenes = []
            for session, indexes in self.selections:
                scenes.extend(load_training_scenes(
                    session,
                    indexes,
                    progress=self.progress.emit,
                    cancelled=self.cancellation_requested,
                ))
            if self.cancellation_requested():
                raise CancelledError("Training cancelled.")
            model = self._fit_function(
                scenes,
                progress=self.progress.emit,
                cancelled=self.cancellation_requested,
            )
            if self.cancellation_requested():
                raise CancelledError("Training cancelled.")
            self.model_ready.emit(model)
        except CancelledError:
            self.cancelled.emit()
        except Exception as exc:
            if self.cancellation_requested():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))


class DropletTrainerWindow(QMainWindow):
    model_saved = Signal(str)

    def __init__(self, parent=None, *, initial_session_paths=()):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Icescopy Droplet Trainer")
        self.resize(760, 620)
        self._selections: list[_SessionSelection] = []
        self._worker: TrainingWorker | None = None
        self._model = None
        self._close_after_cancel = False
        self._updating_frames = False

        root = QWidget(self)
        layout = QVBoxLayout(root)
        instruction = QLabel(
            "Mark every droplet to keep; unmarked regions and circles are background.\n"
            "Add saved .icescopy sessions with complete markings. Only the checked saved frames train the model."
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add Sessions…")
        self.remove_button = QPushButton("Remove Session")
        self.relink_button = QPushButton("Relink Folder…")
        self.add_button.clicked.connect(self._choose_sessions)
        self.remove_button.clicked.connect(self._remove_selected_session)
        self.relink_button.clicked.connect(self._choose_relink_folder)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.relink_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Vertical)
        self.session_table = QTableWidget(0, 4)
        self.session_table.setHorizontalHeaderLabels(["Session", "Frames", "Marks", "Source"])
        self.session_table.setTextElideMode(Qt.ElideMiddle)
        self.session_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.session_table.setSelectionMode(QTableWidget.SingleSelection)
        self.session_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.session_table.verticalHeader().setVisible(False)
        header = self.session_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.session_table.setColumnWidth(3, 175)
        self.session_table.itemSelectionChanged.connect(self._show_selected_frames)
        splitter.addWidget(self.session_table)

        frame_group = QGroupBox("Training frames from the selected session")
        frame_layout = QVBoxLayout(frame_group)
        frame_hint = QLabel(
            "The saved current frame is selected first. Check additional saved keyframes only when every droplet is marked."
        )
        frame_hint.setWordWrap(True)
        frame_layout.addWidget(frame_hint)
        self.frame_list = QListWidget()
        self.frame_list.itemChanged.connect(self._frame_selection_changed)
        frame_layout.addWidget(self.frame_list)
        splitter.addWidget(frame_group)
        splitter.setSizes([230, 160])
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("Add sessions to begin.")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress_log = QTextEdit()
        self.progress_log.setReadOnly(True)
        self.progress_log.document().setMaximumBlockCount(100)
        self.progress_log.setMaximumHeight(110)
        layout.addWidget(self.progress_log)

        training_buttons = QHBoxLayout()
        self.train_button = QPushButton("Train")
        self.cancel_button = QPushButton("Cancel Training")
        self.save_button = QPushButton("Save Model…")
        self.train_button.clicked.connect(self.start_training)
        self.cancel_button.clicked.connect(self.cancel_training)
        self.save_button.clicked.connect(self._choose_model_path)
        training_buttons.addWidget(self.train_button)
        training_buttons.addWidget(self.cancel_button)
        training_buttons.addStretch()
        training_buttons.addWidget(self.save_button)
        layout.addLayout(training_buttons)
        self.setCentralWidget(root)
        self._update_controls()
        if initial_session_paths:
            self.add_sessions(initial_session_paths)

    def _log(self, message):
        # Plain text prevents media paths or backend messages being read as HTML.
        cursor = self.progress_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.progress_log.document().isEmpty():
            cursor.insertBlock()
        cursor.insertText(str(message))
        self.progress_log.setTextCursor(cursor)
        self.progress_log.ensureCursorVisible()

    def _show_error(self, title, message):
        self.status_label.setText(message)
        self._log(message)
        QMessageBox.warning(self, title, message)

    def _selected_row(self):
        row = self.session_table.currentRow()
        return row if 0 <= row < len(self._selections) else None

    def _source_error(self, selection):
        try:
            validate_training_sources(selection.session, sorted(selection.frame_indexes))
        except TrainingSessionError as exc:
            return str(exc)
        return ""

    def _refresh_row(self, row):
        selection = self._selections[row]
        session = selection.session
        count = sum(len(session.frame(index).circles) for index in selection.frame_indexes)
        source_error = self._source_error(selection)
        source_text = "Missing / invalid source" if source_error else "Ready"
        if not selection.frame_indexes:
            source_text = "Choose a frame"
        elif session.relink_folder and not source_error:
            source_text = "Ready (relinked)"
        values = [Path(session.path).name, str(len(selection.frame_indexes)), str(count), source_text]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setToolTip(session.path)
            if column == 3:
                item.setToolTip(source_error or session.relink_folder or "Saved media paths are available.")
                if source_error:
                    item.setForeground(QColor("#b54836"))
            self.session_table.setItem(row, column, item)

    def _update_controls(self):
        running = self._worker is not None
        selected = self._selected_row() is not None
        for widget in (self.add_button, self.session_table, self.frame_list):
            widget.setEnabled(not running)
        self.remove_button.setEnabled(not running and selected)
        self.relink_button.setEnabled(not running and selected)
        ready = bool(self._selections) and all(not self._source_error(item) for item in self._selections)
        self.train_button.setEnabled(not running and ready)
        self.cancel_button.setEnabled(running and not self._worker.cancellation_requested())
        self.save_button.setEnabled(not running and self._model is not None)

    def _invalidate_model(self):
        if self._model is not None:
            self.status_label.setText("Examples changed. Train again before saving a model.")
        self._model = None

    def _choose_sessions(self):
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Choose Marked Icescopy Sessions", "", "Icescopy Sessions (*.icescopy)"
        )
        if paths:
            self.add_sessions(paths)

    def add_sessions(self, paths):
        """Add chosen sessions, retaining visible errors for each rejected file."""
        if self._worker is not None:
            return 0
        added = 0
        errors = []
        known_paths = {selection.session.path for selection in self._selections}
        for path in paths:
            try:
                session = load_training_session(path)
            except TrainingSessionError as exc:
                errors.append(f"{Path(path).name}: {exc}")
                continue
            if session.path in known_paths:
                continue
            known_paths.add(session.path)
            self._invalidate_model()
            row = len(self._selections)
            self._selections.append(_SessionSelection(session, {session.saved_frame_index}))
            self.session_table.insertRow(row)
            self._refresh_row(row)
            added += 1
        if added:
            self.session_table.selectRow(len(self._selections) - 1)
            if any(self._source_error(item) for item in self._selections):
                self.status_label.setText("A selected source is missing. Select its session and use Relink Folder, or remove it.")
            else:
                self.status_label.setText("Ready. Verify that every droplet to keep is marked, then choose Train.")
        self._update_controls()
        if errors:
            self._show_error("Some Sessions Could Not Be Added", "\n\n".join(errors))
        return added

    def _remove_selected_session(self):
        row = self._selected_row()
        if row is None or self._worker is not None:
            return
        self._invalidate_model()
        self._selections.pop(row)
        self.session_table.removeRow(row)
        if self._selections:
            self.session_table.selectRow(min(row, len(self._selections) - 1))
        self._show_selected_frames()
        self._update_controls()

    def _show_selected_frames(self):
        self._updating_frames = True
        try:
            self.frame_list.clear()
            row = self._selected_row()
            if row is not None:
                selection = self._selections[row]
                for frame in selection.session.frames:
                    item = QListWidgetItem(frame.label)
                    item.setToolTip(frame.label)
                    item.setData(Qt.UserRole, frame.index)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if frame.index in selection.frame_indexes else Qt.Unchecked)
                    self.frame_list.addItem(item)
        finally:
            self._updating_frames = False
        self._update_controls()

    def _frame_selection_changed(self, item):
        row = self._selected_row()
        if self._updating_frames or row is None or self._worker is not None:
            return
        selection = self._selections[row]
        index = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            selection.frame_indexes.add(index)
        else:
            selection.frame_indexes.discard(index)
        self._invalidate_model()
        self._refresh_row(row)
        error = self._source_error(selection)
        self.status_label.setText(error or "Saved training frames selected. Verify complete markings, then choose Train.")
        self._update_controls()

    def _choose_relink_folder(self):
        row = self._selected_row()
        if row is None:
            return
        selection = self._selections[row]
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Folder Containing This Session's Images or Videos",
            selection.session.relink_folder or str(Path(selection.session.path).parent),
        )
        if folder:
            self.relink_session(row, folder)

    def relink_session(self, row, folder):
        if self._worker is not None:
            return
        try:
            self._selections[row].session = self._selections[row].session.relinked(folder)
        except TrainingSessionError as exc:
            self._show_error("Unable to Relink Session", str(exc))
            return
        self._invalidate_model()
        self._refresh_row(row)
        error = self._source_error(self._selections[row])
        self.status_label.setText(error or "Media relinked for training. The saved session has not been changed.")
        self._update_controls()

    def start_training(self):
        if self._worker is not None:
            return
        if not self._selections:
            self._show_error("No Training Examples", "Add at least one marked .icescopy session.")
            return
        for selection in self._selections:
            error = self._source_error(selection)
            if error:
                self._show_error("Training Source Not Ready", f"{Path(selection.session.path).name}: {error}")
                return
        selections = [(item.session, sorted(item.frame_indexes)) for item in self._selections]
        self._model = None
        self.progress_log.clear()
        self.status_label.setText("Reading saved training examples…")
        worker = TrainingWorker(selections, self)
        self._worker = worker
        worker.progress.connect(self._training_progress)
        worker.model_ready.connect(self._training_succeeded)
        worker.failed.connect(self._training_failed)
        worker.cancelled.connect(self._training_cancelled)
        worker.finished.connect(self._training_finished)
        self._update_controls()
        worker.start()

    def _training_progress(self, message):
        if self._worker is not None and not self._worker.cancellation_requested():
            self.status_label.setText(message)
        self._log(message)

    def _training_succeeded(self, model):
        if self._worker is None or self._worker.cancellation_requested() or self._close_after_cancel:
            self._training_cancelled()
            return
        self._model = model
        stats = model.get("training_stats", {})
        message = (
            f"Training complete: {stats.get('images', '?')} images, "
            f"{stats.get('circles', '?')} marked circles, {stats.get('samples', '?')} sampled pixels. "
            "Save the model to use it in Icescopy."
        )
        self.status_label.setText(message)
        self._log(message)

    def _training_failed(self, message):
        self._show_error("Droplet Training Failed", message)

    def _training_cancelled(self):
        self._model = None
        self.status_label.setText("Training cancelled. No model was saved.")
        self._log("Training cancelled.")

    def _training_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._update_controls()
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def cancel_training(self):
        if self._worker is not None:
            self._worker.request_cancel()
            self.status_label.setText("Cancelling training…")
            self._update_controls()

    def is_training(self):
        """Remain busy until the finished worker has been released in the UI thread."""
        return self._worker is not None

    def _choose_model_path(self):
        if self._model is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save Droplet Model with a New Filename",
            "droplets.icescopy-model.json",
            "Icescopy Droplet Models (*.icescopy-model.json)",
            options=QFileDialog.DontConfirmOverwrite,
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".icescopy-model.json"
            self.save_model_to(path)

    def save_model_to(self, path):
        """Save only to a new file; an existing model is never replaced."""
        if self._model is None or self._worker is not None:
            return False
        path = str(Path(path).expanduser().resolve())
        try:
            save_model(self._model, path, overwrite=False)
        except FileExistsError:
            self._show_error("Model Already Exists", "Choose a new model filename. Existing model files are not replaced.")
            return False
        except Exception as exc:
            self._show_error("Unable to Save Model", str(exc))
            return False
        self.status_label.setText(f"Model saved: {path}")
        self._log(f"Model saved: {path}")
        self.model_saved.emit(path)
        return True

    def closeEvent(self, event):
        if self._worker is not None:
            self._close_after_cancel = True
            self.cancel_training()
            self.status_label.setText("Cancelling training before closing…")
            event.ignore()
            return
        super().closeEvent(event)


def open_droplet_trainer(parent=None, *, initial_session_paths=()):
    """Show a separate trainer in the caller's QApplication without running it again."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Create a QApplication before opening the droplet trainer.")
    window = DropletTrainerWindow(parent, initial_session_paths=initial_session_paths)
    # Hold Python ownership even if the caller uses this helper without a field.
    windows = getattr(app, "_icescopy_droplet_trainer_windows", None)
    if windows is None:
        windows = []
        app._icescopy_droplet_trainer_windows = windows
    windows.append(window)
    window.show()
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train an Icescopy droplet model from marked saved sessions.")
    parser.add_argument("sessions", nargs="*", help="Saved .icescopy sessions to add initially")
    args = parser.parse_args(argv)
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication([sys.argv[0]])
    open_droplet_trainer(initial_session_paths=args.sessions)
    return app.exec() if owns_app else 0


if __name__ == "__main__":
    raise SystemExit(main())
