"""Utilities for limiting analysis to inclusive frame windows."""


def normalize_analysis_marker_ranges(start_frames, end_frames, frame_count):
    """Build inclusive analysis ranges from start/end frame markers.

    Consecutive starts keep the nearest start before an end. Consecutive ends
    after a closed range are ignored. Missing start/end markers use the source
    beginning/end respectively.
    """
    frame_count = int(frame_count)
    if frame_count <= 0:
        return []

    last_frame = frame_count - 1
    events = []
    for frame in set(start_frames or []):
        try:
            frame = int(frame)
        except (TypeError, ValueError):
            continue
        if 0 <= frame <= last_frame:
            events.append((frame, "start"))
    for frame in set(end_frames or []):
        try:
            frame = int(frame)
        except (TypeError, ValueError):
            continue
        if 0 <= frame <= last_frame:
            events.append((frame, "end"))

    if not events:
        return [(0, last_frame)]

    events.sort(key=lambda item: (item[0], 0 if item[1] == "start" else 1))
    ranges = []
    open_start = None
    for frame, marker_kind in events:
        if marker_kind == "start":
            open_start = int(frame)
            continue

        if open_start is None:
            if not ranges:
                ranges.append((0, int(frame)))
            continue

        if open_start <= int(frame):
            ranges.append((int(open_start), int(frame)))
        open_start = None

    if open_start is not None:
        ranges.append((int(open_start), last_frame))

    return ranges or [(0, last_frame)]


def frame_count_from_ranges(frame_ranges):
    return sum((int(end) - int(start) + 1) for start, end in list(frame_ranges or []))
