"""Frame acquisition backends for image sequences and videos."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import os
from pathlib import Path
import threading
import tempfile

import cv2
import numpy as np
from PySide6.QtGui import QImage


SOURCE_KIND_IMAGE_SEQUENCE = "image_sequence"
SOURCE_KIND_VIDEO = "video"


@dataclass(frozen=True)
class VideoFrameMetadata:
    index: int
    pts: int | None
    time_seconds: float | None


class FrameSource:
    """Abstract frame provider used by display, analysis, and navigation."""

    def frame_count(self) -> int:
        raise NotImplementedError

    def frame_name(self, index: int) -> str:
        raise NotImplementedError

    def frame_tooltip(self, index: int) -> str:
        return self.frame_name(index)

    def frame_key(self, index: int) -> str:
        raise NotImplementedError

    def frame_timestamp(self, index: int):
        return None

    def frame_time_seconds(self, index: int) -> float | None:
        return None

    def get_qimage(self, index: int) -> QImage:
        raise NotImplementedError

    def get_gray_array(self, index: int) -> np.ndarray:
        raise NotImplementedError

    def iter_gray_arrays(self):
        for index in range(self.frame_count()):
            yield index, self.get_gray_array(index)

    def get_size(self, index: int) -> tuple[int, int]:
        qimage = self.get_qimage(index)
        return int(qimage.width()), int(qimage.height())

    def source_kind(self) -> str:
        raise NotImplementedError

    def source_path(self) -> str:
        return ""

    def supports_image_file_operations(self) -> bool:
        return False

    def to_session_payload(self) -> dict:
        raise NotImplementedError


class ImageSequenceFrameSource(FrameSource):
    """FrameSource implementation backed by individual image files."""

    def __init__(self, image_paths=None):
        self._paths = [str(path) for path in (image_paths or [])]

    def paths(self) -> list[str]:
        return list(self._paths)

    def names(self) -> list[str]:
        return [os.path.basename(path) for path in self._paths]

    def frame_count(self) -> int:
        return len(self._paths)

    def _path_at(self, index: int) -> str:
        index = int(index)
        if index < 0 or index >= len(self._paths):
            raise IndexError(f"Frame index out of range: {index}")
        return self._paths[index]

    def frame_name(self, index: int) -> str:
        return os.path.basename(self._path_at(index))

    def frame_tooltip(self, index: int) -> str:
        return self._path_at(index)

    def frame_key(self, index: int) -> str:
        return os.path.normcase(os.path.normpath(self._path_at(index)))

    def get_qimage(self, index: int) -> QImage:
        return QImage(self._path_at(index))

    def get_gray_array(self, index: int) -> np.ndarray:
        image_path = self._path_at(index)
        image_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image_gray is None:
            raise ValueError(f"Unable to read image: {image_path}")
        return image_gray

    def get_size(self, index: int) -> tuple[int, int]:
        image = self.get_qimage(index)
        return int(image.width()), int(image.height())

    def source_kind(self) -> str:
        return SOURCE_KIND_IMAGE_SEQUENCE

    def source_path(self) -> str:
        if not self._paths:
            return ""
        return os.path.dirname(self._paths[0])

    def supports_image_file_operations(self) -> bool:
        return True

    def to_session_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_IMAGE_SEQUENCE,
            "image_paths": self.paths(),
        }


class VideoFrameSource(FrameSource):
    """PyAV-backed video frame source.

    The backend stores lightweight frame metadata for navigation/timing and
    decodes pixels on demand with a small LRU cache for interactive display.
    """

    def __init__(self, video_path, *, cache_size=24, preview_cache_dir=None, frame_metadata=None, frame_size=None):
        self._path = str(video_path)
        self._cache_size = max(1, int(cache_size))
        self._qimage_cache = OrderedDict()
        self._gray_cache = OrderedDict()
        self._metadata: list[VideoFrameMetadata] = list(frame_metadata or [])
        self._index_by_pts: dict[int, int] = {}
        if frame_size is None:
            self._width = 0
            self._height = 0
        else:
            self._width = int(frame_size[0])
            self._height = int(frame_size[1])
        self._decode_lock = threading.RLock()
        self._decode_container = None
        self._decode_stream = None
        self._decode_iterator = None
        self._decode_next_index: int | None = None
        self._max_forward_decode = 180
        self._preview_cache_owner = None
        if preview_cache_dir is None:
            self._preview_cache_owner = tempfile.TemporaryDirectory(prefix="icescopy_video_preview_")
            self._preview_cache_dir = self._preview_cache_owner.name
        else:
            self._preview_cache_dir = str(preview_cache_dir)
            os.makedirs(self._preview_cache_dir, exist_ok=True)
        if not self._metadata:
            self._probe_metadata()
        self._index_by_pts = {
            int(metadata.pts): int(metadata.index)
            for metadata in self._metadata
            if metadata.pts is not None
        }

    def __del__(self):
        self.close()

    def close(self):
        decode_lock = getattr(self, "_decode_lock", None)
        if decode_lock is None:
            return
        with decode_lock:
            self._close_decode_session_locked()
        preview_cache_owner = getattr(self, "_preview_cache_owner", None)
        if preview_cache_owner is not None:
            preview_cache_owner.cleanup()
            self._preview_cache_owner = None

    @staticmethod
    def available() -> bool:
        try:
            import av  # noqa: F401
        except Exception:
            return False
        return True

    def _import_av(self):
        try:
            import av
        except Exception as exc:
            raise RuntimeError(
                "Video input requires PyAV. Install the 'av' package in the Icescopy environment."
            ) from exc
        return av

    def _open_video_stream(self):
        av = self._import_av()
        container = av.open(self._path)
        streams = list(container.streams.video)
        if not streams:
            container.close()
            raise ValueError(f"No video stream found in {self._path}")
        stream = streams[0]
        stream.thread_type = "AUTO"
        return container, stream

    def _probe_metadata(self):
        container, stream = self._open_video_stream()
        base_time = None
        try:
            for index, frame in enumerate(container.decode(stream)):
                if self._width <= 0 or self._height <= 0:
                    self._width = int(frame.width)
                    self._height = int(frame.height)
                time_seconds = None
                if frame.time is not None:
                    time_seconds = float(frame.time)
                elif frame.pts is not None and stream.time_base is not None:
                    time_seconds = float(frame.pts * stream.time_base)
                if base_time is None and time_seconds is not None:
                    base_time = time_seconds
                relative_time = (
                    float(time_seconds - base_time)
                    if time_seconds is not None and base_time is not None
                    else None
                )
                self._metadata.append(
                    VideoFrameMetadata(
                        index=int(index),
                        pts=None if frame.pts is None else int(frame.pts),
                        time_seconds=relative_time,
                    )
                )
        finally:
            container.close()

    def _close_decode_session_locked(self):
        container = self._decode_container
        self._decode_container = None
        self._decode_stream = None
        self._decode_iterator = None
        self._decode_next_index = None
        if container is not None:
            container.close()

    def _ensure_decode_session_locked(self):
        if self._decode_container is None or self._decode_stream is None:
            self._decode_container, self._decode_stream = self._open_video_stream()
            self._decode_iterator = self._decode_container.decode(self._decode_stream)
            self._decode_next_index = 0

    def _seek_decode_session_locked(self, index: int):
        self._ensure_decode_session_locked()
        metadata = self._metadata_at(index)
        if metadata.pts is not None:
            try:
                self._decode_container.seek(metadata.pts, stream=self._decode_stream, backward=True, any_frame=False)
            except Exception:
                self._decode_container.seek(0)
        else:
            self._decode_container.seek(0)

        self._decode_iterator = self._decode_container.decode(self._decode_stream)
        self._decode_next_index = None if metadata.pts is not None else 0

    def _frame_index_for_decoded_frame(self, frame):
        if frame.pts is not None:
            frame_index = self._index_by_pts.get(int(frame.pts))
            if frame_index is not None:
                return int(frame_index)
        if self._decode_next_index is not None:
            return int(self._decode_next_index)
        return None

    def _decode_until_frame_locked(self, target_index: int):
        for frame in self._decode_iterator:
            decoded_index = self._frame_index_for_decoded_frame(frame)
            if decoded_index is None:
                continue

            self._decode_next_index = max(
                int(decoded_index) + 1,
                int(self._decode_next_index) if self._decode_next_index is not None else 0,
            )
            if decoded_index >= target_index:
                return frame
        raise IndexError(f"Unable to decode video frame {target_index}")

    def frame_count(self) -> int:
        return len(self._metadata)

    def frame_metadata(self) -> list[VideoFrameMetadata]:
        return list(self._metadata)

    def frame_size(self) -> tuple[int, int]:
        return int(self._width), int(self._height)

    def _metadata_at(self, index: int) -> VideoFrameMetadata:
        index = int(index)
        if index < 0 or index >= len(self._metadata):
            raise IndexError(f"Frame index out of range: {index}")
        return self._metadata[index]

    def frame_name(self, index: int) -> str:
        metadata = self._metadata_at(index)
        if metadata.time_seconds is None:
            return f"frame {metadata.index:06d}"
        return f"{metadata.index:06d}  {format_seconds_for_frame_list(metadata.time_seconds)}"

    def frame_tooltip(self, index: int) -> str:
        metadata = self._metadata_at(index)
        parts = [
            str(Path(self._path).name),
            f"frame: {metadata.index}",
        ]
        if metadata.time_seconds is not None:
            parts.append(f"time: {format_seconds_for_frame_list(metadata.time_seconds)}")
        if metadata.pts is not None:
            parts.append(f"pts: {metadata.pts}")
        parts.append(self._path)
        return "\n".join(parts)

    def frame_key(self, index: int) -> str:
        metadata = self._metadata_at(index)
        return f"{os.path.normcase(os.path.normpath(self._path))}#frame={metadata.index}"

    def frame_time_seconds(self, index: int) -> float | None:
        return self._metadata_at(index).time_seconds

    def preview_cache_dir(self) -> str:
        return self._preview_cache_dir

    def _preview_cache_path(self, index: int) -> str:
        metadata = self._metadata_at(index)
        return os.path.join(self._preview_cache_dir, f"frame_{metadata.index:08d}.jpg")

    def preview_qimage_is_cached(self, index: int) -> bool:
        return os.path.isfile(self._preview_cache_path(index))

    def get_preview_qimage(self, index: int) -> QImage:
        cache_path = self._preview_cache_path(index)
        if os.path.isfile(cache_path):
            cached_image = QImage(cache_path)
            if not cached_image.isNull():
                return cached_image

        image = self.get_qimage(index)
        image.save(cache_path, "JPG", 92)
        return image

    def _decode_frame(self, index: int):
        target_index = self._metadata_at(index).index
        self._ensure_decode_session_locked()
        can_decode_forward = (
            self._decode_iterator is not None
            and self._decode_next_index is not None
            and target_index >= self._decode_next_index
            and (target_index - self._decode_next_index) <= self._max_forward_decode
        )
        if not can_decode_forward:
            self._seek_decode_session_locked(target_index)

        try:
            return self._decode_until_frame_locked(target_index)
        except IndexError:
            self._seek_decode_session_locked(target_index)
            return self._decode_until_frame_locked(target_index)

    @staticmethod
    def _qimage_from_rgb_array(rgb_array: np.ndarray) -> QImage:
        contiguous = np.ascontiguousarray(rgb_array)
        height, width = contiguous.shape[:2]
        bytes_per_line = int(contiguous.strides[0])
        return QImage(
            contiguous.data,
            int(width),
            int(height),
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()

    @staticmethod
    def _gray_array_from_frame(frame) -> np.ndarray:
        gray_array = frame.to_ndarray(format="gray")
        if gray_array.ndim == 3 and gray_array.shape[2] == 1:
            gray_array = gray_array[:, :, 0]
        if gray_array.ndim != 2:
            raise ValueError(f"Decoded grayscale frame has unexpected shape: {gray_array.shape}")
        return np.ascontiguousarray(gray_array)

    def get_qimage(self, index: int) -> QImage:
        key = int(index)
        with self._decode_lock:
            cached = self._qimage_cache.get(key)
            if cached is not None:
                self._qimage_cache.move_to_end(key)
                return cached

            frame = self._decode_frame(key)
            rgb_array = frame.to_ndarray(format="rgb24")
            image = self._qimage_from_rgb_array(rgb_array)
            self._qimage_cache[key] = image
            self._qimage_cache.move_to_end(key)
            while len(self._qimage_cache) > self._cache_size:
                self._qimage_cache.popitem(last=False)
            return image

    def get_gray_array(self, index: int) -> np.ndarray:
        key = int(index)
        with self._decode_lock:
            cached = self._gray_cache.get(key)
            if cached is not None:
                self._gray_cache.move_to_end(key)
                return cached.copy()

            frame = self._decode_frame(key)
            gray_array = self._gray_array_from_frame(frame)
            self._gray_cache[key] = gray_array
            self._gray_cache.move_to_end(key)
            while len(self._gray_cache) > self._cache_size:
                self._gray_cache.popitem(last=False)
            return gray_array.copy()

    def iter_gray_arrays(self):
        container, stream = self._open_video_stream()
        decoded_count = 0
        try:
            for decoded_index, frame in enumerate(container.decode(stream)):
                if decoded_index >= self.frame_count():
                    break
                decoded_count = decoded_index + 1
                yield decoded_index, self._gray_array_from_frame(frame)
            if decoded_count < self.frame_count():
                raise IndexError(
                    f"Video ended after {decoded_count} frames; expected {self.frame_count()} frames"
                )
        finally:
            container.close()

    def get_size(self, index: int) -> tuple[int, int]:
        if self._width > 0 and self._height > 0:
            return int(self._width), int(self._height)
        return super().get_size(index)

    def source_kind(self) -> str:
        return SOURCE_KIND_VIDEO

    def source_path(self) -> str:
        return self._path

    def to_session_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_VIDEO,
            "video_path": self._path,
            "frame_count": self.frame_count(),
        }


def format_seconds_for_frame_list(seconds: float) -> str:
    total_milliseconds = int(round(float(seconds) * 1000.0))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    seconds_part = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes_part = total_minutes % 60
    hours_part = total_minutes // 60
    if hours_part:
        return f"{hours_part:02d}:{minutes_part:02d}:{seconds_part:02d}.{milliseconds:03d}"
    return f"{minutes_part:02d}:{seconds_part:02d}.{milliseconds:03d}"


def frame_source_from_session_payload(payload) -> FrameSource:
    payload = dict(payload or {})
    kind = payload.get("kind") or SOURCE_KIND_IMAGE_SEQUENCE
    if kind == SOURCE_KIND_VIDEO:
        return VideoFrameSource(payload.get("video_path", ""))
    return ImageSequenceFrameSource(payload.get("image_paths", []))
