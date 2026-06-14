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
SOURCE_KIND_VIDEO_SEQUENCE = "video_sequence"
VIDEO_GRAYSCALE_MODE_GRAYSCALE = "grayscale"
VIDEO_GRAYSCALE_MODE_LUMA = "luma"
DEFAULT_VIDEO_GRAYSCALE_MODE = VIDEO_GRAYSCALE_MODE_GRAYSCALE
VIDEO_GRAYSCALE_MODE_LABELS = {
    VIDEO_GRAYSCALE_MODE_GRAYSCALE: "Converted grayscale",
    VIDEO_GRAYSCALE_MODE_LUMA: "Video luma plane",
}


def normalize_video_grayscale_mode(value) -> str:
    value = str(value or DEFAULT_VIDEO_GRAYSCALE_MODE).strip().lower()
    if value in {VIDEO_GRAYSCALE_MODE_GRAYSCALE, VIDEO_GRAYSCALE_MODE_LUMA}:
        return value
    return DEFAULT_VIDEO_GRAYSCALE_MODE


def normalize_frame_ranges(frame_ranges, frame_count: int) -> list[tuple[int, int]]:
    frame_count = int(frame_count)
    if frame_count <= 0:
        return []
    if frame_ranges is None:
        return [(0, frame_count - 1)]

    normalized = []
    for start, end in list(frame_ranges or []):
        try:
            start = int(start)
            end = int(end)
        except (TypeError, ValueError):
            continue
        start = max(0, min(frame_count - 1, start))
        end = max(0, min(frame_count - 1, end))
        if end < start:
            continue
        normalized.append((start, end))

    if not normalized:
        return []

    normalized.sort()
    merged = []
    for start, end in normalized:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(int(start), int(end)) for start, end in merged]


def iter_frame_range_indexes(frame_ranges, frame_count: int):
    for start, end in normalize_frame_ranges(frame_ranges, frame_count):
        for index in range(start, end + 1):
            yield index


@dataclass(frozen=True)
class VideoFrameMetadata:
    index: int
    pts: int | None
    time_seconds: float | None


def _video_metadata_to_payload(metadata_list):
    return [
        {
            "index": int(metadata.index),
            "pts": None if metadata.pts is None else int(metadata.pts),
            "time_seconds": (
                None
                if metadata.time_seconds is None
                else float(metadata.time_seconds)
            ),
        }
        for metadata in list(metadata_list or [])
    ]


def _video_metadata_from_payload(payload):
    metadata_list = []
    for item in list(payload or []):
        if isinstance(item, VideoFrameMetadata):
            metadata_list.append(item)
            continue
        try:
            metadata_list.append(
                VideoFrameMetadata(
                    index=int(item.get("index", 0)),
                    pts=(
                        None
                        if item.get("pts") is None
                        else int(item.get("pts"))
                    ),
                    time_seconds=(
                        None
                        if item.get("time_seconds") is None
                        else float(item.get("time_seconds"))
                    ),
                )
            )
        except (AttributeError, TypeError, ValueError):
            continue
    return metadata_list


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

    def get_gray_array(self, index: int, grayscale_mode=None) -> np.ndarray:
        raise NotImplementedError

    def iter_gray_arrays(self, grayscale_mode=None, frame_ranges=None):
        for index in iter_frame_range_indexes(frame_ranges, self.frame_count()):
            yield index, self.get_gray_array(index, grayscale_mode=grayscale_mode)

    def get_size(self, index: int) -> tuple[int, int]:
        qimage = self.get_qimage(index)
        return int(qimage.width()), int(qimage.height())

    def source_kind(self) -> str:
        raise NotImplementedError

    def source_path(self) -> str:
        return ""

    def source_paths(self) -> list[str]:
        source_path = self.source_path()
        return [source_path] if source_path else []

    def source_token(self) -> str:
        return "\n".join(
            os.path.normcase(os.path.normpath(path))
            for path in self.source_paths()
        )

    def preview_cache_dir(self) -> str:
        return ""

    def preview_payload(self) -> dict:
        return self.to_session_payload()

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

    def get_gray_array(self, index: int, grayscale_mode=None) -> np.ndarray:
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
            if not self._probe_container_metadata():
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
        except Exception as exc:
            VideoFrameSource._last_import_error = exc
            return False
        VideoFrameSource._last_import_error = None
        return True

    _last_import_error = None

    @staticmethod
    def import_error_message() -> str:
        exc = VideoFrameSource._last_import_error
        if exc is None:
            return ""
        return f"{type(exc).__name__}: {exc}"

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

    def _probe_container_metadata(self):
        container, stream = self._open_video_stream()
        try:
            frame_count = int(getattr(stream, "frames", 0) or 0)
            if frame_count <= 0:
                return False

            codec_context = getattr(stream, "codec_context", None)
            if self._width <= 0:
                self._width = int(getattr(codec_context, "width", 0) or 0)
            if self._height <= 0:
                self._height = int(getattr(codec_context, "height", 0) or 0)

            time_base = getattr(stream, "time_base", None)
            duration_pts = getattr(stream, "duration", None)
            start_pts = getattr(stream, "start_time", None)
            frame_rate = (
                getattr(stream, "average_rate", None)
                or getattr(stream, "base_rate", None)
                or getattr(stream, "guessed_rate", None)
            )

            frame_interval_seconds = None
            pts_step = None
            if duration_pts is not None and time_base is not None:
                duration_seconds = float(duration_pts * time_base)
                if duration_seconds > 0:
                    frame_interval_seconds = duration_seconds / float(frame_count)
                    pts_step = float(duration_pts) / float(frame_count)
            if frame_interval_seconds is None and frame_rate:
                rate_value = float(frame_rate)
                if rate_value > 0:
                    frame_interval_seconds = 1.0 / rate_value
                    if time_base is not None:
                        pts_step = frame_interval_seconds / float(time_base)
            if frame_interval_seconds is None:
                return False

            start_pts = 0 if start_pts is None else int(start_pts)
            metadata = []
            for index in range(frame_count):
                pts_value = None
                if pts_step is not None:
                    pts_value = int(round(float(start_pts) + float(index) * float(pts_step)))
                metadata.append(
                    VideoFrameMetadata(
                        index=int(index),
                        pts=pts_value,
                        time_seconds=float(index) * float(frame_interval_seconds),
                    )
                )
            self._metadata = metadata
            return True
        finally:
            container.close()

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
    def _frame_has_direct_luma_plane(frame) -> bool:
        frame_format = getattr(getattr(frame, "format", None), "name", "")
        frame_format = str(frame_format or "").lower()
        return (
            frame_format.startswith("yuv")
            or frame_format.startswith("yuva")
            or frame_format.startswith("yuvj")
            or frame_format in {"nv12", "nv21", "gray", "gray8", "y8"}
        )

    @staticmethod
    def _luma_array_from_frame(frame) -> np.ndarray | None:
        if not VideoFrameSource._frame_has_direct_luma_plane(frame):
            return None
        planes = getattr(frame, "planes", None)
        if not planes:
            return None
        plane = planes[0]
        width = int(getattr(frame, "width", 0) or 0)
        height = int(getattr(frame, "height", 0) or 0)
        line_size = int(getattr(plane, "line_size", 0) or 0)
        if width <= 0 or height <= 0 or line_size < width:
            return None
        try:
            plane_data = np.frombuffer(plane, dtype=np.uint8)
        except TypeError:
            return None
        expected_size = line_size * height
        if plane_data.size < expected_size:
            return None
        return plane_data[:expected_size].reshape((height, line_size))[:, :width]

    @staticmethod
    def _gray_array_from_frame(frame, grayscale_mode=None) -> np.ndarray:
        grayscale_mode = normalize_video_grayscale_mode(grayscale_mode)
        if grayscale_mode == VIDEO_GRAYSCALE_MODE_LUMA:
            luma_array = VideoFrameSource._luma_array_from_frame(frame)
            if luma_array is not None:
                return luma_array
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

    def get_gray_array(self, index: int, grayscale_mode=None) -> np.ndarray:
        key = int(index)
        grayscale_mode = normalize_video_grayscale_mode(grayscale_mode)
        cache_key = (key, grayscale_mode)
        with self._decode_lock:
            cached = self._gray_cache.get(cache_key)
            if cached is not None:
                self._gray_cache.move_to_end(cache_key)
                return cached.copy()

            frame = self._decode_frame(key)
            gray_array = self._gray_array_from_frame(frame, grayscale_mode=grayscale_mode)
            self._gray_cache[cache_key] = gray_array
            self._gray_cache.move_to_end(cache_key)
            while len(self._gray_cache) > self._cache_size:
                self._gray_cache.popitem(last=False)
            return gray_array.copy()

    def _iter_gray_arrays_sequential_range(self, grayscale_mode=None, start=None, end=None):
        grayscale_mode = normalize_video_grayscale_mode(grayscale_mode)
        frame_count = self.frame_count()
        start = 0 if start is None else max(0, int(start))
        end = frame_count - 1 if end is None else min(frame_count - 1, int(end))
        if frame_count <= 0 or end < start:
            return
        container, stream = self._open_video_stream()
        decoded_count = 0
        try:
            for decoded_index, frame in enumerate(container.decode(stream)):
                if decoded_index >= frame_count:
                    break
                decoded_count = decoded_index + 1
                if decoded_index < start:
                    continue
                if decoded_index > end:
                    break
                yield decoded_index, self._gray_array_from_frame(frame, grayscale_mode=grayscale_mode)
            if end >= frame_count - 1 and decoded_count < frame_count:
                raise IndexError(
                    f"Video ended after {decoded_count} frames; expected {frame_count} frames"
                )
        finally:
            container.close()

    def _iter_gray_arrays_seek_range(self, grayscale_mode=None, start=None, end=None):
        grayscale_mode = normalize_video_grayscale_mode(grayscale_mode)
        frame_count = self.frame_count()
        start = 0 if start is None else max(0, int(start))
        end = frame_count - 1 if end is None else min(frame_count - 1, int(end))
        if frame_count <= 0 or end < start:
            return

        metadata = self._metadata_at(start)
        can_seek_by_pts = bool(self._index_by_pts) and metadata.pts is not None
        if not can_seek_by_pts:
            yield from self._iter_gray_arrays_sequential_range(
                grayscale_mode=grayscale_mode,
                start=start,
                end=end,
            )
            return

        container, stream = self._open_video_stream()
        yielded_count = 0
        fallback_to_sequential = False
        try:
            try:
                container.seek(metadata.pts, stream=stream, backward=True, any_frame=False)
            except Exception:
                fallback_to_sequential = True

            if not fallback_to_sequential:
                for frame in container.decode(stream):
                    decoded_index = None
                    if frame.pts is not None:
                        decoded_index = self._index_by_pts.get(int(frame.pts))
                    if decoded_index is None:
                        continue
                    decoded_index = int(decoded_index)
                    if decoded_index < start:
                        continue
                    if decoded_index > end:
                        break
                    yielded_count += 1
                    yield decoded_index, self._gray_array_from_frame(frame, grayscale_mode=grayscale_mode)
        finally:
            container.close()

        if fallback_to_sequential or yielded_count == 0:
            yield from self._iter_gray_arrays_sequential_range(
                grayscale_mode=grayscale_mode,
                start=start,
                end=end,
            )

    def iter_gray_arrays(self, grayscale_mode=None, frame_ranges=None):
        ranges = normalize_frame_ranges(frame_ranges, self.frame_count())
        if not ranges:
            return
        full_range = [(0, self.frame_count() - 1)]
        if ranges == full_range:
            yield from self._iter_gray_arrays_sequential_range(grayscale_mode=grayscale_mode)
            return
        for start, end in ranges:
            yield from self._iter_gray_arrays_seek_range(
                grayscale_mode=grayscale_mode,
                start=start,
                end=end,
            )

    def get_size(self, index: int) -> tuple[int, int]:
        if self._width > 0 and self._height > 0:
            return int(self._width), int(self._height)
        return super().get_size(index)

    def source_kind(self) -> str:
        return SOURCE_KIND_VIDEO

    def source_path(self) -> str:
        return self._path

    def source_paths(self) -> list[str]:
        return [self._path]

    def preview_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_VIDEO,
            "video_path": self._path,
            "frame_metadata": _video_metadata_to_payload(self._metadata),
            "frame_size": [int(self._width), int(self._height)],
        }

    def to_session_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_VIDEO,
            "video_path": self._path,
            "frame_count": self.frame_count(),
        }


class VideoSequenceFrameSource(FrameSource):
    """FrameSource implementation backed by ordered video clips."""

    def __init__(
        self,
        video_paths,
        *,
        cache_size=24,
        preview_cache_dir=None,
        segment_payloads=None,
    ):
        self._paths = [str(path) for path in (video_paths or []) if str(path)]
        if not self._paths:
            raise ValueError("No video files were supplied.")
        self._cache_size = max(1, int(cache_size))
        self._preview_cache_owner = None
        if preview_cache_dir is None:
            self._preview_cache_owner = tempfile.TemporaryDirectory(
                prefix="icescopy_video_sequence_preview_"
            )
            self._preview_cache_dir = self._preview_cache_owner.name
        else:
            self._preview_cache_dir = str(preview_cache_dir)
            os.makedirs(self._preview_cache_dir, exist_ok=True)

        segment_payloads = list(segment_payloads or [])
        self._sources = []
        for clip_index, video_path in enumerate(self._paths):
            clip_cache_dir = os.path.join(
                self._preview_cache_dir,
                f"clip_{clip_index:04d}",
            )
            segment_payload = (
                segment_payloads[clip_index]
                if clip_index < len(segment_payloads)
                else {}
            )
            frame_metadata = _video_metadata_from_payload(
                segment_payload.get("frame_metadata", [])
                if isinstance(segment_payload, dict)
                else []
            )
            frame_size = (
                segment_payload.get("frame_size")
                if isinstance(segment_payload, dict)
                else None
            )
            self._sources.append(
                VideoFrameSource(
                    video_path,
                    cache_size=self._cache_size,
                    preview_cache_dir=clip_cache_dir,
                    frame_metadata=frame_metadata,
                    frame_size=frame_size,
                )
            )
        self._segments = []
        self._frame_count = 0
        self._rebuild_segments()

    def __del__(self):
        self.close()

    def close(self):
        for source in getattr(self, "_sources", []):
            source.close()
        preview_cache_owner = getattr(self, "_preview_cache_owner", None)
        if preview_cache_owner is not None:
            preview_cache_owner.cleanup()
            self._preview_cache_owner = None

    @staticmethod
    def available() -> bool:
        return VideoFrameSource.available()

    def _segment_duration_seconds(self, source):
        frame_count = source.frame_count()
        if frame_count <= 0:
            return 0.0
        last_time = source.frame_time_seconds(frame_count - 1)
        if last_time is None:
            return float(frame_count)
        frame_interval = 0.0
        if frame_count > 1:
            first_time = source.frame_time_seconds(0)
            if first_time is not None:
                candidate = (float(last_time) - float(first_time)) / float(frame_count - 1)
                if candidate > 0:
                    frame_interval = float(candidate)
        return max(0.0, float(last_time) + frame_interval)

    def _rebuild_segments(self):
        self._segments = []
        frame_start = 0
        time_start = 0.0
        for source in self._sources:
            frame_count = source.frame_count()
            self._segments.append(
                {
                    "source": source,
                    "frame_start": int(frame_start),
                    "time_start": float(time_start),
                    "frame_count": int(frame_count),
                }
            )
            frame_start += frame_count
            time_start += self._segment_duration_seconds(source)
        self._frame_count = int(frame_start)

    def _locate(self, index: int):
        index = int(index)
        if index < 0 or index >= self._frame_count:
            raise IndexError(f"Frame index out of range: {index}")
        for segment in self._segments:
            frame_start = int(segment["frame_start"])
            frame_count = int(segment["frame_count"])
            if frame_start <= index < frame_start + frame_count:
                return segment, index - frame_start
        raise IndexError(f"Frame index out of range: {index}")

    def frame_reference(self, index: int) -> tuple[str, int]:
        segment, local_index = self._locate(index)
        return str(segment["source"].source_path()), int(local_index)

    def global_index_for_reference(self, video_path, local_index):
        normalized_path = os.path.normcase(os.path.normpath(str(video_path)))
        local_index = int(local_index)
        for segment in self._segments:
            source = segment["source"]
            if os.path.normcase(os.path.normpath(source.source_path())) != normalized_path:
                continue
            if 0 <= local_index < source.frame_count():
                return int(segment["frame_start"]) + int(local_index)
        return None

    def frame_count(self) -> int:
        return self._frame_count

    def frame_name(self, index: int) -> str:
        frame_time_seconds = self.frame_time_seconds(index)
        if frame_time_seconds is None:
            return f"frame {int(index):06d}"
        return f"{int(index):06d}  {format_seconds_for_frame_list(frame_time_seconds)}"

    def frame_tooltip(self, index: int) -> str:
        segment, local_index = self._locate(index)
        source = segment["source"]
        parts = [
            str(Path(source.source_path()).name),
            f"global frame: {int(index)}",
            f"clip frame: {int(local_index)}",
        ]
        frame_time_seconds = self.frame_time_seconds(index)
        if frame_time_seconds is not None:
            parts.append(f"time: {format_seconds_for_frame_list(frame_time_seconds)}")
        parts.append(source.source_path())
        return "\n".join(parts)

    def frame_key(self, index: int) -> str:
        segment, local_index = self._locate(index)
        return segment["source"].frame_key(local_index)

    def frame_time_seconds(self, index: int) -> float | None:
        segment, local_index = self._locate(index)
        source_time = segment["source"].frame_time_seconds(local_index)
        if source_time is None:
            return None
        return float(segment["time_start"]) + float(source_time)

    def get_qimage(self, index: int) -> QImage:
        segment, local_index = self._locate(index)
        return segment["source"].get_qimage(local_index)

    def get_preview_qimage(self, index: int) -> QImage:
        segment, local_index = self._locate(index)
        return segment["source"].get_preview_qimage(local_index)

    def get_gray_array(self, index: int, grayscale_mode=None) -> np.ndarray:
        segment, local_index = self._locate(index)
        return segment["source"].get_gray_array(local_index, grayscale_mode=grayscale_mode)

    def iter_gray_arrays(self, grayscale_mode=None, frame_ranges=None):
        ranges = normalize_frame_ranges(frame_ranges, self.frame_count())
        if not ranges:
            return
        for segment in self._segments:
            frame_start = int(segment["frame_start"])
            frame_count = int(segment["frame_count"])
            frame_end = frame_start + frame_count - 1
            if frame_count <= 0:
                continue
            local_ranges = []
            for start, end in ranges:
                overlap_start = max(frame_start, int(start))
                overlap_end = min(frame_end, int(end))
                if overlap_start <= overlap_end:
                    local_ranges.append((overlap_start - frame_start, overlap_end - frame_start))
            if not local_ranges:
                continue
            source = segment["source"]
            for local_index, gray_array in source.iter_gray_arrays(
                grayscale_mode=grayscale_mode,
                frame_ranges=local_ranges,
            ):
                yield frame_start + int(local_index), gray_array

    def get_size(self, index: int) -> tuple[int, int]:
        segment, local_index = self._locate(index)
        return segment["source"].get_size(local_index)

    def source_kind(self) -> str:
        return SOURCE_KIND_VIDEO

    def source_path(self) -> str:
        return self._paths[0] if self._paths else ""

    def source_paths(self) -> list[str]:
        return list(self._paths)

    def preview_cache_dir(self) -> str:
        return self._preview_cache_dir

    def preview_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_VIDEO_SEQUENCE,
            "video_paths": self.source_paths(),
            "segments": [
                source.preview_payload()
                for source in self._sources
            ],
            "frame_count": self.frame_count(),
        }

    def to_session_payload(self) -> dict:
        return {
            "kind": SOURCE_KIND_VIDEO_SEQUENCE,
            "video_paths": self.source_paths(),
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
    if kind == SOURCE_KIND_VIDEO_SEQUENCE:
        return VideoSequenceFrameSource(payload.get("video_paths", []))
    return ImageSequenceFrameSource(payload.get("image_paths", []))


def frame_source_from_preview_payload(payload, *, preview_cache_dir=None) -> FrameSource:
    payload = dict(payload or {})
    kind = payload.get("kind") or SOURCE_KIND_VIDEO
    if kind == SOURCE_KIND_VIDEO_SEQUENCE:
        return VideoSequenceFrameSource(
            payload.get("video_paths", []),
            cache_size=4,
            preview_cache_dir=preview_cache_dir,
            segment_payloads=payload.get("segments", []),
        )
    if kind == SOURCE_KIND_VIDEO:
        return VideoFrameSource(
            payload.get("video_path", ""),
            cache_size=4,
            preview_cache_dir=preview_cache_dir,
            frame_metadata=_video_metadata_from_payload(payload.get("frame_metadata", [])),
            frame_size=payload.get("frame_size"),
        )
    raise ValueError(f"Unsupported preview frame source kind: {kind}")
