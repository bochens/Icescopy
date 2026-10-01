"""Read saved droplet examples without restoring result tables or editing sessions."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
import ntpath
import os
from pathlib import Path
import zipfile

from PySide6.QtGui import QImage

from icescopy_droplet_detection import CancelledError, Circle
from icescopy_frame_source import (
    SOURCE_KIND_IMAGE_SEQUENCE,
    SOURCE_KIND_VIDEO,
    SOURCE_KIND_VIDEO_SEQUENCE,
    frame_source_from_session_payload,
)
from icescopy_image_edit import qimage_buffer_array
from icescopy_session_io import SESSION_STATE_FILENAME, migrate_session_payload


MAX_SESSION_STATE_BYTES = 32 * 1024 * 1024


class TrainingSessionError(ValueError):
    """A saved example or its linked media cannot be used for training."""


@dataclass(frozen=True)
class TrainingFrame:
    index: int
    circles: tuple[Circle, ...]
    is_saved_current: bool = False

    @property
    def label(self):
        description = "saved current frame" if self.is_saved_current else "saved keyframe"
        return f"Frame {self.index}: {description} ({len(self.circles)} marked circles)"


@dataclass(frozen=True)
class TrainingSession:
    path: str
    source_payload: dict
    saved_frame_index: int
    frames: tuple[TrainingFrame, ...]
    relink_folder: str | None = None

    def frame(self, index):
        for frame in self.frames:
            if frame.index == index:
                return frame
        raise TrainingSessionError(
            f"{Path(self.path).name} has no saved annotations for frame {index}. "
            "Choose its saved current frame or a saved keyframe."
        )

    def relinked(self, folder):
        """Use this media folder in memory; never change the saved session."""
        folder = Path(folder).expanduser().resolve()
        if not folder.is_dir():
            raise TrainingSessionError(f"The linked media folder does not exist: {folder}")
        return replace(self, relink_folder=str(folder))


def _frame_index(value, description):
    if isinstance(value, bool):
        raise TrainingSessionError(f"Invalid {description}: {value!r}")
    try:
        index = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TrainingSessionError(f"Invalid {description}: {value!r}") from exc
    if index < 0 or (isinstance(value, float) and value != index):
        raise TrainingSessionError(f"Invalid {description}: {value!r}")
    return index


def _circles(items, frame_index):
    if not isinstance(items, list):
        raise TrainingSessionError(f"Frame {frame_index} circles must be a list.")
    circles = []
    for number, item in enumerate(items, start=1):
        try:
            position = item["circle_pixel_positions"]
            if not isinstance(position, (list, tuple)) or len(position) != 2:
                raise ValueError("raw image position must have two coordinates")
            values = (*position, item["circle_sizes"])
            if any(isinstance(value, bool) for value in values):
                raise ValueError("circle coordinates and radius must be numbers")
            x, y, radius = (float(value) for value in values)
            if not all(math.isfinite(value) for value in (x, y, radius)) or radius <= 0:
                raise ValueError("circle coordinates must be finite and radius must be positive")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise TrainingSessionError(
                f"Frame {frame_index}, circle {number} has invalid raw image geometry: {exc}"
            ) from exc
        circles.append(Circle(x, y, radius))
    return tuple(circles)


def _source_payload(payload):
    source = payload.get("frame_source")
    if not isinstance(source, dict):
        raise TrainingSessionError("The session frame source must be an object.")
    kind = source.get("kind") or SOURCE_KIND_IMAGE_SEQUENCE
    if kind == SOURCE_KIND_VIDEO:
        paths = [source.get("video_path")]
        path_key = "video_path"
    elif kind in (SOURCE_KIND_IMAGE_SEQUENCE, SOURCE_KIND_VIDEO_SEQUENCE):
        path_key = "image_paths" if kind == SOURCE_KIND_IMAGE_SEQUENCE else "video_paths"
        paths = source.get(path_key)
        if not isinstance(paths, list):
            raise TrainingSessionError(f"The session {path_key} must be a list.")
    else:
        raise TrainingSessionError(f"Unsupported session frame source: {kind!r}")
    if not paths or any(not isinstance(path, str) or not path.strip() for path in paths):
        raise TrainingSessionError("The session has no valid linked image or video paths.")
    return {"kind": kind, path_key: paths[0] if kind == SOURCE_KIND_VIDEO else list(paths)}


def _unique_json_keys(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise TrainingSessionError(f"Duplicate session JSON key: {key!r}")
        values[key] = value
    return values


def load_training_session(path, *, max_state_bytes=MAX_SESSION_STATE_BYTES):
    """Read just bounded session JSON, including supported historical schemas.

    Result CSVs are intentionally unopened. A copied session still needs its
    external image/video files, either at the saved paths or in a chosen folder.
    """
    path = Path(path).expanduser().resolve()
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = [item for item in archive.infolist() if item.filename == SESSION_STATE_FILENAME]
            if len(members) != 1:
                raise TrainingSessionError("The session must contain exactly one session.json file.")
            member = members[0]
            if member.file_size > max_state_bytes:
                raise TrainingSessionError(
                    f"Session state exceeds the {max_state_bytes // (1024 * 1024)} MB training-reader limit."
                )
            with archive.open(member, "r") as stream:
                state = stream.read(max_state_bytes + 1)
            if len(state) > max_state_bytes:
                raise TrainingSessionError("Session state exceeds the training-reader size limit.")
            payload = json.loads(state.decode("utf-8"), object_pairs_hook=_unique_json_keys)
        payload = migrate_session_payload(payload)
        source = _source_payload(payload)
        saved_index = _frame_index(payload["image_index"], "saved current frame index")
        current = TrainingFrame(saved_index, _circles(payload["cell_items"], saved_index), True)
        keyframes = payload["keyframe_cell_items_dict"]
        if not isinstance(keyframes, dict):
            raise TrainingSessionError("Saved keyframe circles must be an object.")
        frames_by_index = {}
        for key, items in keyframes.items():
            index = _frame_index(key, "keyframe index")
            if index in frames_by_index:
                raise TrainingSessionError(f"The session repeats keyframe index {index}.")
            frames_by_index[index] = TrainingFrame(index, _circles(items, index))
        # Current-frame geometry is the actual saved view; a keyframe snapshot
        # at the same index may predate its most recent edits.
        frames_by_index.pop(saved_index, None)
        frames = (current,) + tuple(frames_by_index[index] for index in sorted(frames_by_index))
        if source["kind"] == SOURCE_KIND_IMAGE_SEQUENCE:
            for frame in frames:
                if frame.index >= len(source["image_paths"]):
                    raise TrainingSessionError(f"Saved frame {frame.index} is outside the image list.")
        return TrainingSession(str(path), source, saved_index, frames)
    except TrainingSessionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, RuntimeError, RecursionError) as exc:
        raise TrainingSessionError(f"Unable to read {path.name}: {exc}") from exc


def _resolve_media_path(session, saved_path):
    if session.relink_folder:
        # ntpath also recognizes filenames saved on Windows when training on macOS.
        return str(Path(session.relink_folder) / ntpath.basename(saved_path))
    if os.path.isabs(saved_path) or ntpath.isabs(saved_path):
        return saved_path
    return str(Path(session.path).parent / saved_path)


def resolved_source_payload(session):
    """Return a new path mapping; the session's original mapping is preserved."""
    source = session.source_payload
    kind = source["kind"]
    if kind == SOURCE_KIND_VIDEO:
        return {"kind": kind, "video_path": _resolve_media_path(session, source["video_path"])}
    key = "image_paths" if kind == SOURCE_KIND_IMAGE_SEQUENCE else "video_paths"
    return {"kind": kind, key: [_resolve_media_path(session, path) for path in source[key]]}


def validate_training_sources(session, frame_indexes):
    """Check only selected images, or all clips required for video frame indexes."""
    indexes = tuple(frame_indexes)
    if not indexes:
        raise TrainingSessionError("Choose at least one saved frame for this session.")
    for index in indexes:
        if not session.frame(index).circles:
            raise TrainingSessionError(f"Frame {index} has no marked circles. Choose a frame with complete droplet markings.")
    source = resolved_source_payload(session)
    if source["kind"] == SOURCE_KIND_IMAGE_SEQUENCE:
        paths = [source["image_paths"][index] for index in indexes]
        saved_paths = [session.source_payload["image_paths"][index] for index in indexes]
    elif source["kind"] == SOURCE_KIND_VIDEO:
        paths, saved_paths = [source["video_path"]], [session.source_payload["video_path"]]
    else:
        paths, saved_paths = source["video_paths"], session.source_payload["video_paths"]
    if session.relink_folder:
        originals_by_link = {}
        for original, linked in zip(saved_paths, paths):
            previous = originals_by_link.setdefault(os.path.normcase(linked), original)
            if previous != original:
                raise TrainingSessionError(
                    f"Two different source files have the name {ntpath.basename(original)}. "
                    "A single relink folder cannot distinguish them."
                )
    missing = [path for path in paths if not Path(path).is_file()]
    if missing:
        shown = "; ".join(missing[:3])
        remainder = f"; and {len(missing) - 3} more" if len(missing) > 3 else ""
        raise TrainingSessionError(
            f"Missing linked media: {shown}{remainder}. Choose Relink Folder or remove this session."
        )
    return source


def load_training_scenes(session, frame_indexes, *, progress=None, cancelled=None):
    """Decode explicitly selected saved frames and keep their raw coordinates."""
    indexes = tuple(frame_indexes)
    source_payload = validate_training_sources(session, indexes)

    def check_cancelled():
        if cancelled is not None and cancelled():
            raise CancelledError("Training cancelled.")

    check_cancelled()
    source = None
    try:
        source = frame_source_from_session_payload(source_payload)
        scenes = []
        for index in indexes:
            check_cancelled()
            frame = session.frame(index)
            if index >= source.frame_count():
                raise TrainingSessionError(f"Saved frame {index} is outside the linked video.")
            if progress is not None:
                progress(f"Reading {Path(session.path).name}, frame {index} ({len(frame.circles)} marks).")
            qimage = source.get_qimage(index)
            if qimage is None or qimage.isNull():
                raise TrainingSessionError(f"Unable to decode {source.frame_tooltip(index)}.")
            # FrameSource returns original media. Display exposure, cropping,
            # rotation and scene positions are deliberately not applied.
            converted = qimage.convertToFormat(QImage.Format_RGBA8888)
            width, height = converted.width(), converted.height()
            rows = qimage_buffer_array(converted).reshape(height, converted.bytesPerLine())
            rgb = rows[:, : width * 4].reshape(height, width, 4)[:, :, :3].copy()
            for circle in frame.circles:
                if not (0 <= circle.x < width and 0 <= circle.y < height):
                    raise TrainingSessionError(
                        f"A circle center in frame {index} is outside the original {width} x {height} image."
                    )
            check_cancelled()
            scenes.append({
                "image": rgb,
                "circles": list(frame.circles),
                "source_key": source.frame_key(index),
            })
        return scenes
    except (TrainingSessionError, CancelledError):
        raise
    except Exception as exc:
        raise TrainingSessionError(f"Unable to read media for {Path(session.path).name}: {exc}") from exc
    finally:
        close_source = getattr(source, "close", None)
        if callable(close_source):
            close_source()
