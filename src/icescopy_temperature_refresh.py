"""Portable temperature inputs for rebuilding counts without reopening source files."""

from dataclasses import is_dataclass
from datetime import datetime
from types import SimpleNamespace

import numpy as np

from icescopy_temperature_import import TemperatureImportError


def encode_temperature_input(value):
    """Use JSON data only; never pickle executable Python objects in sessions."""
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if is_dataclass(value) or isinstance(value, SimpleNamespace):
        return {"type": "record", "value": encode_temperature_input(vars(value))}
    if isinstance(value, dict):
        return {str(key): encode_temperature_input(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [encode_temperature_input(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported temperature input: {type(value).__name__}")


def decode_temperature_input(value):
    if isinstance(value, list):
        return [decode_temperature_input(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"type", "value"}:
            if value["type"] == "datetime":
                return datetime.fromisoformat(value["value"])
            if value["type"] == "record":
                return SimpleNamespace(**decode_temperature_input(value["value"]))
        return {key: decode_temperature_input(item) for key, item in value.items()}
    return value


def make_temperature_refresh_context(window, kind, parsed, options):
    return {
        "version": 1,
        "kind": kind,
        "frame_names": [window.frame_name(index) for index in range(window.frame_count())],
        "frame_keys": [window.frame_key(index) for index in range(window.frame_count())],
        "parsed": encode_temperature_input(parsed),
        "options": encode_temperature_input(options),
    }


def rebuild_temperature_counts(window, context):
    if context.get("version") != 1:
        raise TemperatureImportError("Re-import temperatures: this saved import format is not supported.")
    names = [window.frame_name(index) for index in range(window.frame_count())]
    keys = [window.frame_key(index) for index in range(window.frame_count())]
    if names != context["frame_names"] or keys != context["frame_keys"]:
        raise TemperatureImportError("Re-import temperatures: the loaded frames, their paths, or their order changed.")
    builders = {
        "standard": window.build_standard_freeze_count_timeseries_results,
        "csu": window.build_csu_freeze_count_timeseries_results,
        "tamu": window.build_tamu_freeze_count_timeseries_results,
        "pku": window.build_pku_linksys32_freeze_count_timeseries_results,
    }
    if context.get("kind") not in builders:
        raise TemperatureImportError("Re-import temperatures: the saved importer is not supported.")
    options = decode_temperature_input(context["options"])
    if options.get("calibration_by_well"):
        options["calibration_by_well"] = {
            int(key): value for key, value in options["calibration_by_well"].items()
        }
    return builders[context["kind"]](decode_temperature_input(context["parsed"]), **options)
