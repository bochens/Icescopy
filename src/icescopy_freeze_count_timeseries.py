from __future__ import annotations

import os
from datetime import timedelta

import numpy as np

from icescopy_temperature_refresh import make_temperature_refresh_context
from icescopy_sample_metadata import export_sample_metadata_field_keys
from icescopy_freeze_cycles import capture_cycle_metadata, cycle_ids_for_window
from icescopy_temperature_import import (
    CSU_COUNT_SOURCE_COMBINED,
    CSU_COUNT_SOURCE_IMAGES,
    CSU_COUNT_SOURCE_INSTRUMENT,
    IMAGE_TIMESTAMP_SOURCE_FILENAME,
    IMAGE_TIMESTAMP_SOURCE_GENERATED,
    TEMPERATURE_UNIT_CELSIUS,
    TIMESTAMP_STYLE_AUTO,
    TemperatureImportError,
    image_order_warnings,
    epoch_file_time_warnings,
    build_cycle_ids_from_start_indexes as build_cycle_ids_from_temperature_starts,
    detect_cycle_start_indexes_from_temperatures as detect_temperature_cycle_start_indexes,
    normalize_sample_name,
    normalize_temperature_reset_threshold as normalize_temperature_reset_threshold_value,
    parse_tamu_image_timestamp,
    parse_timestamp_text,
    reconcile_counts_by_cycle as reconcile_temperature_counts_by_cycle,
    resolve_image_timestamps,
)


def interpolate_frame_temperatures(image_elapsed_seconds, timeseries_seconds, temperature_values):
    """Log temperature at each frame time; None without a time or outside the log."""
    temperatures = []
    in_range_count = 0
    out_of_range_count = 0
    for elapsed_seconds in image_elapsed_seconds:
        if elapsed_seconds is None:
            temperatures.append(None)
            continue
        temperature = np.interp(
            elapsed_seconds,
            timeseries_seconds,
            temperature_values,
            left=np.nan,
            right=np.nan,
        )
        if np.isnan(temperature):
            out_of_range_count += 1
            temperatures.append(None)
        else:
            in_range_count += 1
            temperatures.append(float(temperature))
    return temperatures, in_range_count, out_of_range_count


def cycle_start_seconds(timeseries_seconds, cycle_start_indexes):
    """Log times of the cycle start rows; [0.0] when there are none."""
    return [
        float(timeseries_seconds[index])
        for index in cycle_start_indexes
        if 0 <= int(index) < len(timeseries_seconds)
    ] or [0.0]


def frame_elapsed_seconds_and_cycles(window, frame_timestamps, origin, cycle_starts):
    """Seconds from the log origin and cycle for each frame; None without a time."""
    image_elapsed_seconds = []
    image_cycle_ids = []
    for image_timestamp in frame_timestamps:
        if image_timestamp is None or origin is None:
            image_elapsed_seconds.append(None)
            image_cycle_ids.append(None)
            continue
        elapsed_seconds = float((image_timestamp - origin).total_seconds())
        image_elapsed_seconds.append(elapsed_seconds)
        image_cycle_ids.append(window.cycle_index_for_position(elapsed_seconds, cycle_starts))
    return image_elapsed_seconds, image_cycle_ids


def count_table_headers(window, matched_samples, include_corrected_temperature=False):
    """Frame columns, then corrected temperature (optional), total and frozen per sample."""
    headers = ["timestamp", "temperature_C", "cycle", "image_name"]
    sample_column_metadata = []
    for sample in matched_samples:
        sample_name = str(sample.get("sample_name", ""))
        if include_corrected_temperature:
            headers.append(f"{sample_name} corrected temperature_C")
        headers.append(f"{sample_name} number total")
        headers.append(f"{sample_name} number frozen")
        sample_column_metadata.append(
            window.build_freeze_count_timeseries_sample_column_metadata(sample)
        )
    return headers, sample_column_metadata


def count_table_rows(
    window,
    frame_timestamps,
    frame_temperatures,
    image_cycle_ids,
    matched_samples,
    image_counts_by_sample,
    calibration_by_well=None,
):
    """One row per frame, matching count_table_headers."""
    rows = []
    for image_index in range(window.frame_count()):
        image_timestamp = frame_timestamps[image_index]
        temperature = frame_temperatures[image_index]
        cycle_id = image_cycle_ids[image_index]
        output_row = [
            image_timestamp.isoformat(timespec="milliseconds") if image_timestamp is not None else "",
            "" if temperature is None else f"{temperature:.3f}",
            "" if cycle_id is None else str(int(cycle_id)),
            os.path.basename(str(window.frame_name(image_index) or "")),
        ]
        for sample in matched_samples:
            if calibration_by_well:
                corrected_temperature = window.corrected_temperature_for_group(
                    temperature,
                    sample,
                    calibration_by_well,
                )
                output_row.append("" if corrected_temperature is None else f"{corrected_temperature:.3f}")
            frozen_count = image_counts_by_sample.get(sample["group_key"], {}).get(image_index, 0)
            output_row.append(str(int(sample.get("total_cells", 0))))
            output_row.append(str(int(frozen_count)))
        rows.append(output_row)
    return rows


def count_summary_sample_fields(
    window,
    parsed_timeseries,
    source_type,
    matched_samples,
    sample_column_metadata,
    grouping_mode,
):
    """Summary fields that open every count import summary."""
    return {
        "source_path": str(getattr(parsed_timeseries, "file_path", "")),
        "source_type": source_type,
        "matched_samples": [sample["sample_name"] for sample in matched_samples],
        "total_cell_count": len(window.cell_records_by_id),
        "sample_total_cells": [
            {
                "sample_id": str(sample.get("sample_id", "") or ""),
                "sample_name": str(sample.get("sample_name", "")),
                "total_cells": int(sample.get("total_cells", 0)),
                "role": "sample",
            }
            for sample in matched_samples
        ],
        "sample_column_metadata": sample_column_metadata,
        "grouping_mode": str(grouping_mode),
        "count_mode": "cycle_reset",
    }


def count_summary_cycle_fields(window, timing_context, reset_temperature):
    """Cycle and frame count fields of a count import summary."""
    return {
        "cycle_count": int(len(timing_context["cycle_start_seconds"])),
        "freeze_review_cycle_metadata": capture_cycle_metadata(
            window,
            timing_context["image_cycle_ids"],
            reset_temperature,
        ),
        "reset_temperature": window.normalize_temperature_reset_threshold(reset_temperature),
        "total_images": int(window.frame_count()),
        "parsed_image_count": int(timing_context["parsed_image_count"]),
    }


def count_summary_unparsed_fields(window, timing_context):
    """Frames without a timestamp, and frames whose times go backwards."""
    return {
        "unparsed_image_count": int(len(timing_context["unparsed_images"])),
        "unparsed_images_preview": list(timing_context["unparsed_images"][:5]),
        "warnings": image_order_warnings(
            timing_context["image_elapsed_seconds"],
            (window.frame_name(i) for i in range(window.frame_count())),
        ),
    }


def output_samples(sample_groups, metadata_field_names):
    """Sample groups as output columns: samples by name, unassigned cells last."""
    matched_samples = []
    for group_key, group in sample_groups.items():
        group_key_text = str(group_key)
        sample_id_text = str(group.get("sample_id", "") or "")
        normalized_name = normalize_sample_name(group.get("sample_name", ""))
        matched_samples.append(
            {
                "group_key": group_key_text,
                "group_role": str(group.get("group_role", "sample") or "sample"),
                "sample_id": sample_id_text,
                "normalized_name": normalized_name,
                "sample_name": str(group.get("sample_name", "")),
                **{
                    field_name: str(group.get(field_name, "") or "")
                    for field_name in metadata_field_names
                    if field_name != "sample_name"
                },
                "total_cells": int(group.get("total_cells", 0)),
                "cell_ids": list(group.get("cell_ids", [])),
                "sort_index": int(group.get("sort_index", 0) or 0),
            }
        )
    matched_samples.sort(
        key=lambda sample: (
            1 if str(sample.get("group_role", "")) in {"unassigned_cell", "unassigned_cells"} else 0,
            ""
            if str(sample.get("group_role", "")) in {"unassigned_cell", "unassigned_cells"}
            else str(sample["sample_name"]).casefold(),
            int(sample.get("sort_index", 0) or 0)
            if str(sample.get("group_role", "")) in {"unassigned_cell", "unassigned_cells"}
            else 0,
            str(sample.get("sample_id", "") or ""),
            str(sample.get("group_key", "")),
        )
    )
    return matched_samples


def cycle_reset_counts(freeze_events_by_cell, image_cycle_ids, total_image_count):
    """Frozen cells at each frame, counting each cell's first freeze in that frame's cycle.

    freeze_events_by_cell holds (cell_id, freeze frame values) pairs.
    """
    first_freeze_frame_by_cell_cycle = {}
    for cell_id, freeze_event_indices in freeze_events_by_cell:
        cycle_first_frames = {}
        resolved_frames = []
        for frame_value in freeze_event_indices:
            try:
                frame_index = int(frame_value)
            except (TypeError, ValueError):
                continue
            if 0 <= frame_index < total_image_count:
                resolved_frames.append(frame_index)
        for frame_index in sorted(set(resolved_frames)):
            cycle_id = image_cycle_ids[frame_index] if frame_index < len(image_cycle_ids) else None
            if cycle_id is None or cycle_id in cycle_first_frames:
                continue
            cycle_first_frames[cycle_id] = int(frame_index)
        first_freeze_frame_by_cell_cycle[int(cell_id)] = cycle_first_frames

    cycle_counts = {}
    for image_index in range(total_image_count):
        cycle_id = image_cycle_ids[image_index] if image_index < len(image_cycle_ids) else None
        frozen_count = 0
        for cycle_first_frames in first_freeze_frame_by_cell_cycle.values():
            first_frame = cycle_first_frames.get(cycle_id)
            if first_frame is not None and first_frame <= image_index:
                frozen_count += 1
        cycle_counts[image_index] = int(frozen_count)
    return cycle_counts


class FreezeCountTimeseriesMixin:
    def freeze_review_cycle_ids(self):
        """Imported zero-based cycles in frame order, or empty when unavailable."""
        return cycle_ids_for_window(self)

    def build_freeze_count_timeseries_sample_groups(self, grouping_mode="samples"):
        metadata_field_names = export_sample_metadata_field_keys(
            getattr(self, "sample_metadata_schema", None)
        )
        self.ensure_cell_registry_matches_scene_cells()
        grouping_mode = str(grouping_mode or "samples").strip().casefold()
        if grouping_mode == "all_cells":
            all_cell_ids = []
            for cell_id in sorted(self.cell_records_by_id.keys()):
                if self.ensure_cell_record(cell_id) is None:
                    continue
                all_cell_ids.append(int(cell_id))
            if not all_cell_ids:
                return {}
            return {
                "__all_cells__": {
                    "group_key": "__all_cells__",
                    "sample_id": "",
                    "sample_name": "All Cells",
                    **{
                        field_name: ""
                        for field_name in metadata_field_names
                        if field_name != "sample_name"
                    },
                    "cell_ids": all_cell_ids,
                    "total_cells": len(all_cell_ids),
                }
            }

        groups = {}
        unassigned_cell_ids = []
        for cell_id in sorted(self.cell_records_by_id.keys()):
            record = self.ensure_cell_record(cell_id)
            if record is None:
                continue
            raw_sample_id = getattr(record, "sample_id", "")
            sample_id = "" if raw_sample_id is None else str(raw_sample_id).strip()
            if not sample_id:
                unassigned_cell_ids.append(int(cell_id))
                continue
            sample_record = self.sample_record_for_id(sample_id)
            sample_name = str(sample_record.get("sample_name", "")).strip()
            if not sample_name:
                continue
            group = groups.setdefault(
                sample_id,
                {
                    "group_key": sample_id,
                    "group_role": "sample",
                    "sample_id": sample_id,
                    "sample_name": sample_name,
                    **{
                        field_name: str(sample_record.get(field_name, "") or "")
                        for field_name in metadata_field_names
                        if field_name != "sample_name"
                    },
                    "cell_ids": [],
                    "total_cells": 0,
                    "sort_index": len(groups),
                },
            )
            group["cell_ids"].append(int(cell_id))
            group["total_cells"] += 1
        if unassigned_cell_ids:
            group_key = "__unassigned_cells__"
            groups[group_key] = {
                "group_key": group_key,
                "group_role": "unassigned_cells",
                "sample_id": "",
                "sample_name": "Unassigned cells",
                **{
                    field_name: ""
                    for field_name in metadata_field_names
                    if field_name != "sample_name"
                },
                "cell_ids": unassigned_cell_ids,
                "total_cells": len(unassigned_cell_ids),
                "sort_index": max(unassigned_cell_ids) if unassigned_cell_ids else 0,
            }
        return groups

    def build_tamu_freeze_count_timeseries_sample_groups(self):
        sample_groups = self.build_freeze_count_timeseries_sample_groups(grouping_mode="samples")
        if sample_groups:
            return sample_groups, "samples"
        sample_groups = self.build_freeze_count_timeseries_sample_groups(grouping_mode="all_cells")
        if sample_groups:
            return sample_groups, "all_cells"
        return {}, "samples"

    def build_freeze_count_timeseries_output_samples(self, sample_groups):
        metadata_field_names = export_sample_metadata_field_keys(
            getattr(self, "sample_metadata_schema", None)
        )
        return output_samples(sample_groups, metadata_field_names)

    def normalize_temperature_reset_threshold(self, reset_temperature):
        return normalize_temperature_reset_threshold_value(reset_temperature)

    def detect_cycle_start_indexes_from_temperatures(self, temperatures, reset_temperature):
        return detect_temperature_cycle_start_indexes(
            temperatures,
            reset_temperature,
            warmup_hysteresis_c=float(getattr(self, "temperature_cycle_warmup_hysteresis_c", 0.02)),
        )

    def build_cycle_ids_from_start_indexes(self, total_count, cycle_start_indexes):
        return build_cycle_ids_from_temperature_starts(total_count, cycle_start_indexes)

    def cycle_index_for_position(self, position_value, cycle_start_positions):
        if position_value is None or not cycle_start_positions:
            return None
        index = int(np.searchsorted(np.asarray(cycle_start_positions, dtype=float), float(position_value), side="right") - 1)
        return max(0, index)

    def build_tamu_image_timing_context(self, parsed_timeseries, reset_temperature=None):
        timeseries_seconds = np.asarray(getattr(parsed_timeseries, "timeseries_seconds", []), dtype=float)
        temperature_values = np.asarray(getattr(parsed_timeseries, "temperature_values", []), dtype=float)
        cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            temperature_values,
            reset_temperature,
        )
        cycle_starts = cycle_start_seconds(timeseries_seconds, cycle_start_indexes)
        basenames = [
            os.path.basename(str(self.frame_name(image_index) or ""))
            for image_index in range(self.frame_count())
        ]
        parsed_image_timestamps = [parse_tamu_image_timestamp(basename) for basename in basenames]
        image_elapsed_seconds, image_cycle_ids = frame_elapsed_seconds_and_cycles(
            self,
            parsed_image_timestamps,
            getattr(parsed_timeseries, "start_timestamp", None),
            cycle_starts,
        )
        return {
            "cycle_start_seconds": cycle_starts,
            "cycle_start_indexes": cycle_start_indexes,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(sum(value is not None for value in image_elapsed_seconds)),
            "unparsed_images": [
                basename
                for basename, value in zip(basenames, parsed_image_timestamps)
                if value is None
            ],
            "parsed_image_timestamps": parsed_image_timestamps,
        }

    def build_pku_linksys32_image_timing_context(self, parsed_timeseries, reset_temperature=None):
        timeseries_datetimes = list(getattr(parsed_timeseries, "timeseries_datetimes", []))
        temperature_values = np.asarray(
            list(getattr(parsed_timeseries, "temperature_values", [])),
            dtype=float,
        )
        timeseries_seconds = np.asarray(
            list(getattr(parsed_timeseries, "timeseries_seconds", [])),
            dtype=float,
        )
        if len(timeseries_datetimes) < 2 or len(timeseries_datetimes) != len(temperature_values):
            raise TemperatureImportError("The PKU Linksys32 .iml file does not contain enough aligned datetime and temperature rows.")
        if len(timeseries_seconds) != len(temperature_values):
            timeseries_origin = timeseries_datetimes[0]
            timeseries_seconds = np.asarray(
                [
                    float((timestamp - timeseries_origin).total_seconds())
                    for timestamp in timeseries_datetimes
                ],
                dtype=float,
            )

        image_records = list(getattr(parsed_timeseries, "image_records", []))
        loaded_image_count = self.frame_count()
        if len(image_records) != loaded_image_count:
            raise TemperatureImportError(
                "The PKU Linksys32 .iml image record count does not match the loaded image count. "
                f"The .iml file contains {len(image_records)} image record(s), but the session has {loaded_image_count} loaded image(s)."
            )

        cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            temperature_values,
            reset_temperature,
        )
        cycle_starts = cycle_start_seconds(timeseries_seconds, cycle_start_indexes)

        start_timestamp = getattr(parsed_timeseries, "start_timestamp", None)
        if start_timestamp is None:
            start_timestamp = timeseries_datetimes[0]

        parsed_image_timestamps = []
        image_record_temperatures = []
        for image_record in image_records:
            try:
                image_temperature = float(getattr(image_record, "temperature_value", None))
            except (TypeError, ValueError):
                raise TemperatureImportError(
                    f"PKU Linksys32 .iml image record {len(image_record_temperatures) + 1} has an invalid tagged temperature."
                ) from None
            if not np.isfinite(image_temperature):
                raise TemperatureImportError(
                    f"PKU Linksys32 .iml image record {len(image_record_temperatures) + 1} has an invalid tagged temperature."
                )
            parsed_image_timestamps.append(getattr(image_record, "timestamp", None))
            image_record_temperatures.append(image_temperature)
        image_elapsed_seconds, image_cycle_ids = frame_elapsed_seconds_and_cycles(
            self,
            parsed_image_timestamps,
            start_timestamp,
            cycle_starts,
        )

        return {
            "timeseries_seconds": timeseries_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "cycle_start_seconds": cycle_starts,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(sum(1 for value in parsed_image_timestamps if value is not None)),
            "unparsed_images": [
                os.path.basename(str(self.frame_name(index) or ""))
                for index, value in enumerate(parsed_image_timestamps)
                if value is None
            ],
            "parsed_image_timestamps": parsed_image_timestamps,
            "image_record_temperatures": image_record_temperatures,
            "image_record_count": int(len(image_records)),
        }

    def build_tamu_cycle_reset_image_counts(self, sample_groups, image_cycle_ids):
        image_counts_by_sample = {}
        total_image_count = self.frame_count()
        for group_key, group in sample_groups.items():
            freeze_events_by_cell = []
            for cell_id in group["cell_ids"]:
                record = self.ensure_cell_record(cell_id)
                if record is None:
                    continue
                freeze_events_by_cell.append((cell_id, getattr(record, "freeze_event_indices", [])))
            image_counts_by_sample[group_key] = cycle_reset_counts(
                freeze_events_by_cell,
                image_cycle_ids,
                total_image_count,
            )
        return image_counts_by_sample

    def reconcile_counts_by_cycle(self, raw_counts, anchor_counts, maximum_count, cycle_ids):
        return reconcile_temperature_counts_by_cycle(
            raw_counts,
            anchor_counts,
            maximum_count,
            cycle_ids,
        )

    def corrected_temperature_for_cell(self, measured_temperature, cell_id, calibration_by_well):
        if measured_temperature is None or calibration_by_well is None:
            return None
        try:
            calibration_entry = calibration_by_well.get(int(cell_id))
        except (TypeError, ValueError, AttributeError):
            calibration_entry = None
        if not calibration_entry:
            return None
        slope_value, intercept_value = calibration_entry
        try:
            slope_value = float(slope_value)
            intercept_value = float(intercept_value)
            if slope_value == 0:
                return None
            return (float(measured_temperature) - intercept_value) / slope_value
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def corrected_temperature_for_group(self, measured_temperature, group, calibration_by_well):
        if measured_temperature is None or not calibration_by_well or not group:
            return None
        corrected_values = []
        for cell_id in group.get("cell_ids", []):
            corrected_value = self.corrected_temperature_for_cell(
                measured_temperature,
                cell_id,
                calibration_by_well,
            )
            if corrected_value is not None:
                corrected_values.append(float(corrected_value))
        if not corrected_values:
            return None
        return float(np.mean(corrected_values))

    def build_standard_image_timing_context(
        self,
        parsed_timeseries,
        image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
        image_timestamp_style=TIMESTAMP_STYLE_AUTO,
        generated_start_text="",
        frame_interval_seconds=None,
        reset_temperature=None,
    ):
        timeseries_datetimes = list(getattr(parsed_timeseries, "timeseries_datetimes", []))
        temperature_values = np.asarray(
            list(getattr(parsed_timeseries, "temperature_values", [])),
            dtype=float,
        )
        if len(timeseries_datetimes) < 2 or len(timeseries_datetimes) != len(temperature_values):
            raise TemperatureImportError("The standard temperature CSV does not contain enough aligned datetime and temperature rows.")

        timeseries_origin = timeseries_datetimes[0]
        timeseries_seconds = np.asarray(
            [
                float((timestamp - timeseries_origin).total_seconds())
                for timestamp in timeseries_datetimes
            ],
            dtype=float,
        )
        cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            temperature_values,
            reset_temperature,
        )
        cycle_starts = cycle_start_seconds(timeseries_seconds, cycle_start_indexes)

        if self.is_video_source():
            start_timestamp = parse_timestamp_text(generated_start_text, image_timestamp_style)
            if start_timestamp is None:
                raise TemperatureImportError("Enter a valid first frame timestamp for the video source.")
            parsed_image_timestamps = []
            unparsed_images = []
            parsed_count = 0
            for frame_index in range(self.frame_count()):
                if image_timestamp_source == IMAGE_TIMESTAMP_SOURCE_GENERATED:
                    try:
                        interval = float(frame_interval_seconds)
                    except (TypeError, ValueError):
                        interval = 0.0
                    if interval <= 0:
                        parsed_image_timestamps.append(None)
                        unparsed_images.append(self.frame_name(frame_index))
                        continue
                    image_timestamp = start_timestamp + timedelta(seconds=float(frame_index) * interval)
                else:
                    frame_time_seconds = self.active_frame_source().frame_time_seconds(frame_index)
                    if frame_time_seconds is None:
                        parsed_image_timestamps.append(None)
                        unparsed_images.append(self.frame_name(frame_index))
                        continue
                    image_timestamp = start_timestamp + timedelta(seconds=float(frame_time_seconds))
                parsed_image_timestamps.append(image_timestamp)
                parsed_count += 1
        else:
            resolved_timestamps = resolve_image_timestamps(
                self.imagePaths,
                self.imageNames,
                source=image_timestamp_source,
                timestamp_style=image_timestamp_style,
                generated_start_text=generated_start_text,
                frame_interval_seconds=frame_interval_seconds,
            )
            parsed_image_timestamps = list(resolved_timestamps.image_timestamps)
            unparsed_images = list(resolved_timestamps.unparsed_images)
            parsed_count = int(resolved_timestamps.parsed_count)
        image_elapsed_seconds, image_cycle_ids = frame_elapsed_seconds_and_cycles(
            self,
            parsed_image_timestamps,
            timeseries_origin,
            cycle_starts,
        )

        return {
            "timeseries_origin": timeseries_origin,
            "timeseries_seconds": timeseries_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "cycle_start_seconds": cycle_starts,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(parsed_count),
            "unparsed_images": list(unparsed_images),
            "parsed_image_timestamps": parsed_image_timestamps,
        }

    def build_standard_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
        image_timestamp_style=TIMESTAMP_STYLE_AUTO,
        generated_start_text="",
        frame_interval_seconds=None,
        temperature_timestamp_style=TIMESTAMP_STYLE_AUTO,
        temperature_unit=TEMPERATURE_UNIT_CELSIUS,
        reset_temperature=None,
        timing_context=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples = self.build_freeze_count_timeseries_output_samples(sample_groups)
        timing_context = timing_context or self.build_standard_image_timing_context(
            parsed_timeseries,
            image_timestamp_source=image_timestamp_source,
            image_timestamp_style=image_timestamp_style,
            generated_start_text=generated_start_text,
            frame_interval_seconds=frame_interval_seconds,
            reset_temperature=reset_temperature,
        )
        if int(timing_context["parsed_image_count"]) <= 0:
            raise TemperatureImportError(
                "No loaded frames produced a parseable timestamp for standard freeze count timeseries."
            )

        image_cycle_ids = timing_context["image_cycle_ids"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(
            sample_groups,
            image_cycle_ids,
        )
        frame_temperatures, in_range_image_count, out_of_range_image_count = (
            interpolate_frame_temperatures(
                timing_context["image_elapsed_seconds"],
                np.asarray(list(timing_context["timeseries_seconds"]), dtype=float),
                np.asarray(list(getattr(parsed_timeseries, "temperature_values", [])), dtype=float),
            )
        )
        headers, sample_column_metadata = count_table_headers(self, matched_samples)
        rows = count_table_rows(
            self,
            timing_context["parsed_image_timestamps"],
            frame_temperatures,
            image_cycle_ids,
            matched_samples,
            image_counts_by_sample,
        )

        clock_warnings = epoch_file_time_warnings(
            getattr(parsed_timeseries, 'timeseries_timestamp_texts', []), image_timestamp_source)
        if in_range_image_count <= 0:
            raise TemperatureImportError(
                "No loaded frame timestamp falls inside the standard temperature CSV timeseries range."
                + (' ' + ' '.join(clock_warnings) if clock_warnings else '')
            )

        timeseries_timestamp_texts = list(getattr(parsed_timeseries, "timeseries_timestamp_texts", []))
        summary = {
            **count_summary_sample_fields(
                self, parsed_timeseries, "standard_csv", matched_samples, sample_column_metadata,
                grouping_mode,
            ),
            "timeseries_start_timestamp": (
                timeseries_timestamp_texts[0]
                if timeseries_timestamp_texts
                else timing_context["timeseries_origin"].isoformat(timespec="milliseconds")
            ),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            **count_summary_cycle_fields(self, timing_context, reset_temperature),
            "in_range_image_count": int(in_range_image_count),
            "out_of_range_image_count": int(out_of_range_image_count),
            **count_summary_unparsed_fields(self, timing_context),
            "image_timestamp_source": str(image_timestamp_source),
            "image_timestamp_style": str(image_timestamp_style),
            "temperature_timestamp_style": str(temperature_timestamp_style),
            "temperature_unit": str(temperature_unit),
        }
        summary['warnings'].extend(clock_warnings)
        summary["refresh_context"] = make_temperature_refresh_context(
            self, "standard", parsed_timeseries, dict(
                image_timestamp_source=image_timestamp_source,
                image_timestamp_style=image_timestamp_style,
                generated_start_text=generated_start_text,
                frame_interval_seconds=frame_interval_seconds,
                temperature_timestamp_style=temperature_timestamp_style,
                temperature_unit=temperature_unit, reset_temperature=reset_temperature,
                timing_context=timing_context,
            ),
        )
        return headers, rows, summary

    def build_csu_freeze_count_timeseries_results(
        self, parsed_data, reset_temperature=None,
        count_source=CSU_COUNT_SOURCE_COMBINED,
    ):
        count_source_labels = {
            CSU_COUNT_SOURCE_IMAGES: "Icescopy only",
            CSU_COUNT_SOURCE_INSTRUMENT: "CSU recorded counts",
            CSU_COUNT_SOURCE_COMBINED: "Icescopy + .dat",
        }
        if count_source not in count_source_labels:
            raise TemperatureImportError("Choose a valid CSU count source.")
        warnings = []
        metadata_field_names = export_sample_metadata_field_keys(
            getattr(self, "sample_metadata_schema", None)
        )
        sample_groups = self.build_freeze_count_timeseries_sample_groups()
        dat_sample_columns = list(parsed_data.get("sample_columns", []))
        dat_columns_by_name = {
            normalize_sample_name(column_name): column_name
            for column_name in dat_sample_columns
        }
        groups_by_normalized_name = {}
        for group in sample_groups.values():
            normalized_name = normalize_sample_name(group.get("sample_name", ""))
            groups_by_normalized_name.setdefault(normalized_name, []).append(group)

        matched_samples = []
        for dat_column in (dat_sample_columns if count_source != CSU_COUNT_SOURCE_IMAGES else []):
            normalized_name = normalize_sample_name(dat_column)
            matching_groups = groups_by_normalized_name.get(normalized_name, [])
            if not matching_groups:
                continue
            if len(matching_groups) > 1:
                duplicate_ids = ", ".join(
                    str(group.get("sample_id", "") or "")
                    for group in matching_groups
                )
                raise TemperatureImportError(
                    f"CSU .dat import cannot disambiguate duplicate app sample names for '{dat_column}'. "
                    f"Rename one of the duplicate samples in Sample Catalog. Sample IDs: {duplicate_ids}."
                )
            group = matching_groups[0]
            group_key = str(group.get("group_key", "") or group.get("sample_id", "") or normalized_name)
            sample_id = str(group.get("sample_id", "") or "")
            matched_samples.append(
                {
                    "group_key": group_key,
                    "group_role": str(group.get("group_role", "sample") or "sample"),
                    "sample_id": sample_id,
                    "normalized_name": normalized_name,
                    "sample_name": group["sample_name"],
                    "dat_column": dat_column,
                    **{
                        field_name: str(group.get(field_name, "") or "")
                        for field_name in metadata_field_names
                        if field_name != "sample_name"
                    },
                    "cell_ids": list(group.get("cell_ids", [])),
                    "total_cells": int(group["total_cells"]),
                }
            )

        matched_group_keys = {str(sample.get("group_key", "")) for sample in matched_samples}
        for group in sample_groups.values():
            if count_source == CSU_COUNT_SOURCE_INSTRUMENT:
                continue
            if (count_source != CSU_COUNT_SOURCE_IMAGES
                    and str(group.get("group_role", "")) not in {"unassigned_cell", "unassigned_cells"}):
                continue
            group_key = str(group.get("group_key", ""))
            if group_key in matched_group_keys:
                continue
            normalized_name = normalize_sample_name(group.get("sample_name", ""))
            matched_samples.append(
                {
                    "group_key": group_key,
                    "group_role": str(group.get("group_role", "unassigned_cells") or "unassigned_cells"),
                    "sample_id": str(group.get("sample_id", "") or ""),
                    "normalized_name": normalized_name,
                    "sample_name": str(group.get("sample_name", "")),
                    "dat_column": None,
                    **{
                        field_name: str(group.get(field_name, "") or "")
                        for field_name in metadata_field_names
                        if field_name != "sample_name"
                    },
                    "cell_ids": list(group.get("cell_ids", [])),
                    "total_cells": int(group.get("total_cells", 0)),
                }
            )

        unmatched_app_samples = sorted(
            group["sample_name"]
            for normalized_name, groups in groups_by_normalized_name.items()
            for group in groups
            if count_source != CSU_COUNT_SOURCE_IMAGES
            and (normalized_name not in dat_columns_by_name)
            and (count_source == CSU_COUNT_SOURCE_INSTRUMENT
                 or str(group.get("group_role", "")) not in {"unassigned_cell", "unassigned_cells"})
        )
        unmatched_dat_samples = sorted(
            column_name
            for normalized_name, column_name in dat_columns_by_name.items()
            if count_source != CSU_COUNT_SOURCE_IMAGES and normalized_name not in groups_by_normalized_name
        )

        parsed_rows = list(parsed_data.get("rows", []))
        if not parsed_rows:
            raise TemperatureImportError("The CSU .dat file has no data rows.")
        if count_source == CSU_COUNT_SOURCE_INSTRUMENT and not matched_samples:
            raise TemperatureImportError(
                "To use CSU recorded counts, draw the cells and assign them to samples named "
                "to match the .dat columns (for example, Sample_0). "
                "Or choose Icescopy detections to use image freeze events."
            )

        # CSU images have sequence names, not capture times. Only an exact Picture
        # match identifies the corresponding instrument time and temperature.
        def picture_key(value):
            return str(value or "").strip().replace("\\", "/").rsplit("/", 1)[-1].casefold()

        image_index_by_name = {}
        for image_index in range(self.frame_count()):
            name = picture_key(self.frame_name(image_index))
            if name in image_index_by_name:
                raise TemperatureImportError(
                    "CSU picture matching requires unique loaded image filenames, ignoring letter case."
                )
            image_index_by_name[name] = image_index
        picture_row_by_name = {}
        for row_index, row in enumerate(parsed_rows):
            if int(row.row_index) != row_index:
                raise TemperatureImportError("CSU data rows are not in their original order.")
            name = picture_key(row.picture_name)
            if not name:
                continue
            if name in picture_row_by_name:
                raise TemperatureImportError("The CSU .dat file has duplicate Picture filenames.")
            picture_row_by_name[name] = row_index
        matched_frame_rows = [
            picture_row_by_name[name] for name in image_index_by_name if name in picture_row_by_name
        ]
        if not matched_frame_rows:
            raise TemperatureImportError("No loaded image filenames match the CSU Picture column.")
        if matched_frame_rows != sorted(matched_frame_rows):
            raise TemperatureImportError(
                "The loaded images are out of order relative to the CSU Picture records. "
                "Reload them in acquisition order (use natural filename order for numbered images)."
            )
        unmatched_image_indexes = {
            index for name, index in image_index_by_name.items() if name not in picture_row_by_name
        }
        if unmatched_image_indexes:
            warnings.append(
                f"{len(unmatched_image_indexes)} loaded image(s) have no Picture record; "
                "their capture times, temperatures, and cycles are unknown."
            )
            if count_source != CSU_COUNT_SOURCE_INSTRUMENT:
                for group in sample_groups.values():
                    for cell_id in group.get("cell_ids", []):
                        record = self.ensure_cell_record(cell_id)
                        if any(frame in unmatched_image_indexes for frame in getattr(record, "freeze_event_indices", [])):
                            raise TemperatureImportError(
                                "A cell freeze event is on an image with no matching CSU Picture record. "
                                "Load the corresponding .dat file before importing image counts."
                            )
        previous_timestamp = None
        for row_index in matched_frame_rows:
            row = parsed_rows[row_index]
            if row.avg_temp is None or not np.isfinite(float(row.avg_temp)):
                raise TemperatureImportError("A matched CSU Picture record has no valid sample temperature.")
            if hasattr(row, "timestamp"):
                if row.timestamp is None:
                    raise TemperatureImportError("A matched CSU Picture record has an unreadable date or time.")
                if previous_timestamp is not None and row.timestamp <= previous_timestamp:
                    raise TemperatureImportError("Matched CSU Picture timestamps must be strictly increasing.")
                previous_timestamp = row.timestamp
        row_temperatures = [
            np.nan if getattr(row, "avg_temp", None) is None else float(row.avg_temp)
            for row in parsed_rows
        ]
        row_cycle_start_indexes = self.detect_cycle_start_indexes_from_temperatures(
            row_temperatures,
            reset_temperature,
        )
        row_cycle_ids = self.build_cycle_ids_from_start_indexes(len(parsed_rows), row_cycle_start_indexes)
        image_cycle_ids = [None] * self.frame_count()
        picture_rows_matched = 0
        for row in parsed_rows:
            picture_name = picture_key(row.picture_name)
            if picture_name and picture_name in image_index_by_name:
                picture_rows_matched += 1
                image_index = image_index_by_name[picture_name]
                image_cycle_ids[image_index] = row_cycle_ids[int(row.row_index)]

        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)

        corrected_counts_by_sample = {}
        for sample in matched_samples:
            group_key = sample["group_key"]
            dat_column = sample["dat_column"]
            total_cells = int(sample["total_cells"])
            if dat_column is None or count_source == CSU_COUNT_SOURCE_IMAGES:
                raw_counts = [0 for _row in parsed_rows]
            else:
                raw_counts = [
                    getattr(row, "sample_counts", {}).get(dat_column)
                    for row in parsed_rows
                ]
                if any(value is None for value in raw_counts):
                    raise TemperatureImportError(
                        f"The CSU column {dat_column} contains missing or invalid counts. "
                        "Choose Icescopy detections to use image events, or check the source records."
                    )
                if any(value > total_cells for value in raw_counts):
                    if count_source == CSU_COUNT_SOURCE_INSTRUMENT:
                        raise TemperatureImportError(
                            f"CSU {dat_column} records more frozen droplets than the {total_cells} "
                            "cells assigned to this sample. Assign the full sample's cells before "
                            "using recorded counts; Icescopy will not clip them."
                        )
                    warnings.append(f"{dat_column}: combined counts are limited to the {total_cells} assigned cells.")
                if any(b < a for a, b in zip(raw_counts, raw_counts[1:])):
                    detail = ("Recorded decreases are preserved." if count_source == CSU_COUNT_SOURCE_INSTRUMENT
                              else "Combined counts remain nondecreasing within each cycle.")
                    warnings.append(f"{dat_column}: the recorded count decreases. {detail} Count decreases do not define cycles.")
            anchor_counts = {}
            image_counts = image_counts_by_sample.get(group_key, {})
            for row in parsed_rows:
                picture_name = picture_key(row.picture_name)
                if not picture_name:
                    continue
                image_index = image_index_by_name.get(picture_name)
                if image_index is None:
                    continue
                anchor_counts[int(row.row_index)] = int(image_counts.get(image_index, 0))
            if count_source == CSU_COUNT_SOURCE_INSTRUMENT:
                corrected_counts_by_sample[group_key] = raw_counts
            elif count_source == CSU_COUNT_SOURCE_IMAGES:
                # Hold each observed image count until the next picture, without
                # borrowing an instrument event time or moving events backward.
                image_row_counts = []
                current_count = 0
                previous_cycle = None
                for row_index, cycle_id in enumerate(row_cycle_ids):
                    if cycle_id != previous_cycle:
                        current_count = 0
                    current_count = anchor_counts.get(row_index, current_count)
                    image_row_counts.append(current_count)
                    previous_cycle = cycle_id
                corrected_counts_by_sample[group_key] = image_row_counts
            else:
                corrected_counts_by_sample[group_key] = self.reconcile_counts_by_cycle(
                    raw_counts, anchor_counts, total_cells, row_cycle_ids,
                )

        if count_source != CSU_COUNT_SOURCE_INSTRUMENT and matched_samples:
            if not any(any(image_counts_by_sample.get(sample["group_key"], {}).values())
                       for sample in matched_samples):
                warnings.append(
                    "No cell freeze events are stored for the matched images. "
                    "Image-derived counts are zero; run analysis or set events manually if needed."
                )
        if not matched_samples:
            warnings.append("No cell groups were included. Draw and assign cells, then import again; choose Icescopy detections when the file has no sample counts.")

        headers = ["timestamp", "temperature_C", "cycle", "picture"]
        sample_column_metadata = []
        for sample in matched_samples:
            sample_name = str(sample["sample_name"])
            headers.append(f"{sample_name} number total")
            headers.append(f"{sample_name} number frozen")
            sample_column_metadata.append(
                self.build_freeze_count_timeseries_sample_column_metadata(sample)
            )

        rows = []
        for row in parsed_rows:
            row_index = int(row.row_index)
            output_row = [
                str(getattr(row, "timestamp_text", "") or ""),
                "" if getattr(row, "avg_temp", None) is None else f"{float(row.avg_temp):.3f}",
                str(int(row_cycle_ids[row_index])) if row_index < len(row_cycle_ids) else "0",
                str(getattr(row, "picture_name", "") or ""),
            ]
            for sample in matched_samples:
                group_key = sample["group_key"]
                total_cells = int(sample["total_cells"])
                sample_counts = corrected_counts_by_sample.get(group_key, [])
                frozen_value = sample_counts[row_index] if row_index < len(sample_counts) else 0
                output_row.append(str(total_cells))
                output_row.append(str(int(frozen_value)))
            rows.append(output_row)

        summary = {
            "source_path": str(parsed_data.get("file_path", "")),
            "count_source": count_source,
            "count_source_label": count_source_labels[count_source],
            "temperature_column": str(parsed_data.get("temperature_column", "Avg_Temp")),
            "warnings": warnings,
            "unmatched_image_count": len(unmatched_image_indexes),
            "total_image_count": self.frame_count(),
            "matched_image_count": self.frame_count() - len(unmatched_image_indexes),
            "total_cell_group_count": len(sample_groups),
            "total_dat_sample_count": len(dat_sample_columns),
            "sample_count_matching_used": count_source != CSU_COUNT_SOURCE_IMAGES,
            "dat_sample_matches": [
                {"sample_name": sample["sample_name"], "dat_column": sample["dat_column"]}
                for sample in matched_samples if sample["dat_column"] is not None
            ],
            "matched_samples": [sample["sample_name"] for sample in matched_samples],
            "total_cell_count": len(self.cell_records_by_id),
            "sample_total_cells": [
                {
                    "sample_id": str(sample["sample_id"] or ""),
                    "sample_name": str(sample["sample_name"]),
                    "total_cells": int(sample["total_cells"]),
                    "role": "sample",
                }
                for sample in matched_samples
            ],
            "sample_column_metadata": sample_column_metadata,
            "unmatched_app_samples": unmatched_app_samples,
            "unmatched_dat_samples": unmatched_dat_samples,
            "matched_picture_rows": int(picture_rows_matched),
            "matched_sample_count": int(len(matched_samples)),
            "total_picture_rows": int(sum(1 for row in parsed_rows if getattr(row, "picture_name", ""))),
            "cycle_count": int(max(row_cycle_ids) + 1) if row_cycle_ids else 1,
            "freeze_review_cycle_metadata": capture_cycle_metadata(
                self, image_cycle_ids, reset_temperature, require_unique_names=True,
            ),
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
        }
        summary["refresh_context"] = make_temperature_refresh_context(
            self, "csu", parsed_data, dict(reset_temperature=reset_temperature, count_source=count_source),
        )
        return headers, rows, summary

    def build_tamu_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        calibration_by_well=None,
        reset_temperature=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples = self.build_freeze_count_timeseries_output_samples(sample_groups)
        timing_context = self.build_tamu_image_timing_context(parsed_timeseries, reset_temperature=reset_temperature)
        image_cycle_ids = timing_context["image_cycle_ids"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)
        frame_temperatures, in_range_image_count, out_of_range_image_count = (
            interpolate_frame_temperatures(
                timing_context["image_elapsed_seconds"],
                np.asarray(list(getattr(parsed_timeseries, "timeseries_seconds", [])), dtype=float),
                np.asarray(list(getattr(parsed_timeseries, "temperature_values", [])), dtype=float),
            )
        )

        calibrated_cell_ids = set()
        if calibration_by_well:
            for group in matched_samples:
                for cell_id in group.get("cell_ids", []):
                    if int(cell_id) in calibration_by_well:
                        calibrated_cell_ids.add(int(cell_id))

        headers, sample_column_metadata = count_table_headers(
            self,
            matched_samples,
            include_corrected_temperature=bool(calibration_by_well),
        )
        rows = count_table_rows(
            self,
            timing_context["parsed_image_timestamps"],
            frame_temperatures,
            image_cycle_ids,
            matched_samples,
            image_counts_by_sample,
            calibration_by_well,
        )

        if in_range_image_count <= 0:
            raise TemperatureImportError(
                "No loaded image timestamp falls inside the TAMU Linkam temperature timeseries range."
            )

        summary = {
            **count_summary_sample_fields(
                self, parsed_timeseries, "tamu", matched_samples, sample_column_metadata,
                grouping_mode,
            ),
            "timeseries_start_timestamp": str(getattr(parsed_timeseries, "start_timestamp_text", "") or ""),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            "sample_period_seconds": getattr(parsed_timeseries, "sample_period_seconds", None),
            **count_summary_cycle_fields(self, timing_context, reset_temperature),
            "in_range_image_count": int(in_range_image_count),
            "out_of_range_image_count": int(out_of_range_image_count),
            **count_summary_unparsed_fields(self, timing_context),
            "calibration_path": "" if not calibration_by_well else str(getattr(self, "last_temperature_calibration_path", "") or ""),
            "calibrated_cell_count": int(len(calibrated_cell_ids)),
        }
        summary["refresh_context"] = make_temperature_refresh_context(
            self, "tamu", parsed_timeseries, dict(reset_temperature=reset_temperature, calibration_by_well=calibration_by_well),
        )
        return headers, rows, summary

    def build_pku_linksys32_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        reset_temperature=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples = self.build_freeze_count_timeseries_output_samples(sample_groups)
        timing_context = self.build_pku_linksys32_image_timing_context(
            parsed_timeseries,
            reset_temperature=reset_temperature,
        )
        image_cycle_ids = timing_context["image_cycle_ids"]
        image_record_temperatures = timing_context["image_record_temperatures"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)
        headers, sample_column_metadata = count_table_headers(self, matched_samples)
        rows = count_table_rows(
            self,
            timing_context["parsed_image_timestamps"],
            image_record_temperatures,
            image_cycle_ids,
            matched_samples,
            image_counts_by_sample,
        )

        summary = {
            **count_summary_sample_fields(
                self, parsed_timeseries, "pku_linksys32_iml", matched_samples, sample_column_metadata,
                grouping_mode,
            ),
            "timeseries_start_timestamp": str(getattr(parsed_timeseries, "start_timestamp_text", "") or ""),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            "sample_period_seconds": getattr(parsed_timeseries, "sample_period_seconds", None),
            "image_record_count": int(timing_context.get("image_record_count", 0)),
            "linksys32_version": str(getattr(parsed_timeseries, "version", "") or ""),
            **count_summary_cycle_fields(self, timing_context, reset_temperature),
            "temperature_source": "pku_linksys32_image_record",
            "tagged_temperature_count": int(
                sum(value is not None for value in image_record_temperatures)
            ),
            **count_summary_unparsed_fields(self, timing_context),
        }
        summary["refresh_context"] = make_temperature_refresh_context(
            self, "pku", parsed_timeseries, dict(reset_temperature=reset_temperature),
        )
        return headers, rows, summary
