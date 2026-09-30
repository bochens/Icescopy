"""Imported cooling-cycle assignments used when reviewing freeze events.

These assignments are independent of frozen counts and annotations. They are
valid only for the exact ordered frame identities used by the temperature
import. A missing assignment is unknown, never an inferred cycle.
"""

import math
import os
from collections import Counter
from numbers import Integral


def finite_reset_temperature(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def normalize_cycle_metadata(metadata):
    """Return a detached JSON-safe mapping, or empty for untrusted metadata."""
    if not isinstance(metadata, dict):
        return {}
    threshold = finite_reset_temperature(metadata.get("reset_temperature"))
    keys = metadata.get("frame_keys")
    cycles = metadata.get("cycle_ids")
    if (
        threshold is None
        or not isinstance(keys, (list, tuple))
        or not isinstance(cycles, (list, tuple))
        or not keys
        or len(keys) != len(cycles)
        or any(not isinstance(key, str) or not key for key in keys)
    ):
        return {}
    normalized = []
    for value in cycles:
        if value is None:
            normalized.append(None)
        elif isinstance(value, Integral) and not isinstance(value, bool) and value >= 0:
            normalized.append(int(value))
        else:
            return {}
    if not any(value is not None for value in normalized):
        return {}
    return {
        "frame_keys": list(keys),
        "cycle_ids": normalized,
        "reset_temperature": threshold,
    }


def capture_cycle_metadata(window, cycle_ids, reset_temperature, *, require_unique_names=False):
    """Capture the importer's actual assignments; do not redetect cycles."""
    if finite_reset_temperature(reset_temperature) is None or not callable(getattr(window, "frame_key", None)):
        return {}
    cycle_ids = list(cycle_ids)
    if len(cycle_ids) != window.frame_count():
        return {}
    if require_unique_names:
        # CSU matches picture basenames. Duplicate names cannot establish which
        # loaded image owns the imported row, even though frame keys differ.
        names = [os.path.basename(str(window.frame_name(index))).casefold() for index in range(window.frame_count())]
        counts = Counter(names)
        cycle_ids = [value if counts[name] == 1 else None for name, value in zip(names, cycle_ids)]
    return normalize_cycle_metadata({
        "frame_keys": [window.frame_key(index) for index in range(window.frame_count())],
        "cycle_ids": cycle_ids,
        "reset_temperature": reset_temperature,
    })


def cycle_metadata_from_legacy_results(window, headers, rows, summary):
    """Recover only explicit, unambiguously frame-matched old cycle columns.

    The image-based importers saved one row per frame in frame order. CSU saved
    temperature rows with optional picture names; those require unique names.
    Without a configured reset threshold, cycle=0 is only a default and cannot
    establish a cooling cycle.
    """
    if not isinstance(summary, dict) or finite_reset_temperature(summary.get("reset_temperature")) is None:
        return {}
    if not callable(getattr(window, "frame_key", None)):
        return {}
    headers = list(headers or [])
    rows = list(rows or [])
    if "cycle" not in headers:
        return {}
    cycle_column = headers.index("cycle")
    name_header = "image_name" if "image_name" in headers else "picture" if "picture" in headers else None
    if name_header is None:
        return {}
    name_column = headers.index(name_header)
    frame_names = [os.path.basename(str(window.frame_name(index))).casefold() for index in range(window.frame_count())]

    def row_name(row):
        return os.path.basename(str(row[name_column] or "")).casefold() if len(row) > name_column else ""

    def row_cycle(row):
        text = str(row[cycle_column]).strip() if len(row) > cycle_column else ""
        if not text:
            return None
        try:
            value = int(text)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if value >= 0 else None

    if name_header == "image_name":
        if len(rows) != len(frame_names) or any(row_name(row) != name for row, name in zip(rows, frame_names)):
            return {}
        cycles = [row_cycle(row) for row in rows]
    else:
        if len(set(frame_names)) != len(frame_names):
            return {}
        frame_name_set = set(frame_names)
        cycles_by_name = {}
        for row in rows:
            name = row_name(row)
            if not name or name not in frame_name_set:
                continue
            value = row_cycle(row)
            if name in cycles_by_name and cycles_by_name[name] != value:
                return {}
            cycles_by_name[name] = value
        cycles = [cycles_by_name.get(name) for name in frame_names]
    return capture_cycle_metadata(window, cycles, summary["reset_temperature"])


def set_cycle_metadata(window, metadata):
    # Replace this object rather than mutating it; the query cache uses identity.
    window.freeze_review_cycle_metadata = normalize_cycle_metadata(metadata)
    window._freeze_review_cycle_cache = None


def restore_cycle_metadata(window, state):
    metadata = state.get("freeze_review_cycle_metadata")
    if metadata is None:
        summary = state.get("freeze_count_timeseries_summary") or {}
        metadata = summary.get("freeze_review_cycle_metadata")
        if metadata is None:
            metadata = cycle_metadata_from_legacy_results(
                window,
                state.get("freeze_count_timeseries_headers"),
                state.get("freeze_count_timeseries_rows"),
                summary,
            )
    set_cycle_metadata(window, metadata)


def cycle_ids_for_window(window):
    """Return trusted frame-aligned IDs, with one identity check per source."""
    source = window.active_frame_source()
    metadata = getattr(window, "freeze_review_cycle_metadata", None)
    count = window.frame_count()
    cache = getattr(window, "_freeze_review_cycle_cache", None)
    if cache is not None and cache[0] is source and cache[1] is metadata and cache[2] == count:
        return cache[3]
    normalized = normalize_cycle_metadata(metadata)
    result = ()
    if normalized and len(normalized["frame_keys"]) == count:
        keys = tuple(window.frame_key(index) for index in range(count))
        if keys == tuple(normalized["frame_keys"]):
            result = tuple(normalized["cycle_ids"])
    window._freeze_review_cycle_cache = (source, metadata, count, result)
    return result
