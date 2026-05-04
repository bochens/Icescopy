from __future__ import annotations

from PySide6.QtCore import QObject, QMetaObject, QThread, Qt, Signal, Slot

from icescopy_frame_source import VideoFrameSource


class VideoPreviewDecodeWorker(QObject):
    decoded = Signal(int, object, str, str)
    failed = Signal(int, str, str)

    def __init__(self, video_path, preview_cache_dir, frame_metadata, frame_size, parent=None):
        super().__init__(parent)
        self.video_path = str(video_path)
        self.preview_cache_dir = str(preview_cache_dir)
        self.frame_metadata = list(frame_metadata or [])
        self.frame_size = tuple(frame_size or (0, 0))
        self.frame_source = None
        self.closed = False

    @Slot(int)
    def decode(self, index):
        if self.closed:
            return
        requested_index = 0
        try:
            index = int(index)
            requested_index = index
            if self.frame_source is None:
                self.frame_source = VideoFrameSource(
                    self.video_path,
                    cache_size=4,
                    preview_cache_dir=self.preview_cache_dir,
                    frame_metadata=self.frame_metadata,
                    frame_size=self.frame_size,
                )
            q_image = self.frame_source.get_preview_qimage(index)
            frame_key = self.frame_source.frame_key(index)
        except Exception as err:
            self.failed.emit(requested_index, str(err), self.video_path)
            return
        if not self.closed:
            self.decoded.emit(index, q_image, frame_key, self.video_path)

    @Slot()
    def close(self):
        self.closed = True
        if self.frame_source is not None:
            self.frame_source.close()
            self.frame_source = None


class VideoPreviewDecodeController(QObject):
    decoded = Signal(int, object, str, str)
    failed = Signal(int, str, str)
    decode_requested = Signal(int)

    def __init__(self, video_path, preview_cache_dir, frame_metadata, frame_size, parent=None):
        super().__init__(parent)
        self.worker = VideoPreviewDecodeWorker(
            video_path,
            preview_cache_dir,
            frame_metadata,
            frame_size,
        )
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.decode_requested.connect(self.worker.decode)
        self.worker.decoded.connect(self.decoded)
        self.worker.failed.connect(self.failed)
        self.thread.finished.connect(self.worker.deleteLater)

    def start(self):
        self.thread.start()

    def request_decode(self, index):
        self.decode_requested.emit(int(index))

    def close(self, timeout_ms=1000):
        worker = self.worker
        thread = self.thread
        if worker is None or thread is None:
            return

        try:
            self.decode_requested.disconnect(worker.decode)
        except (TypeError, RuntimeError):
            pass

        if thread.isRunning():
            if QThread.currentThread() is thread:
                worker.close()
                thread.quit()
                return
            QMetaObject.invokeMethod(worker, "close", Qt.BlockingQueuedConnection)
            thread.quit()
            thread.wait(int(timeout_ms))
        else:
            worker.close()

        self.worker = None
        self.thread = None
