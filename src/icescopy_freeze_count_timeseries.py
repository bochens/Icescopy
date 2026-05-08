from __future__ import annotations

import os
from datetime import timedelta

import numpy as np

from icescopy_sample_metadata import export_sample_metadata_field_keys
from icescopy_temperature_import import (
    IMAGE_TIMESTAMP_SOURCE_FILENAME,
    IMAGE_TIMESTAMP_SOURCE_GENERATED,
    IMAGE_TIMESTAMP_SOURCE_VIDEO_PTS,
    TEMPERATURE_UNIT_CELSIUS,
    TIMESTAMP_STYLE_AUTO,
    TemperatureImportError,
    apply_blank_correction_counts,
    build_cycle_ids_from_start_indexes as build_cycle_ids_from_temperature_starts,
    compute_blank_correction_by_index,
    detect_cycle_start_indexes_from_temperatures as detect_temperature_cycle_start_indexes,
    normalize_sample_name,
    normalize_temperature_reset_threshold as normalize_temperature_reset_threshold_value,
    parse_tamu_image_timestamp,
    parse_timestamp_text,
    reconcile_counts_by_cycle as reconcile_temperature_counts_by_cycle,
    resolve_image_timestamps,
)


class FreezeCountTimeseriesMixin:
    def freeze_count_timeseries_sample_metadata_field_names(self):
        schema = getattr(self, "sample_metadata_schema", None)
        return export_sample_metadata_field_keys(schema)

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
                "sample_name": "Unassigned cells" if groups else "All cells",
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

    def build_freeze_count_timeseries_image_counts(self, sample_groups, count_mode="cumulative"):
        count_mode = str(count_mode or "cumulative").strip().casefold()
        image_counts_by_sample = {}
        total_frame_count = self.frame_count()
        for group_key, group in sample_groups.items():
            if count_mode == "state":
                state_counts = {}
                per_cell_events = []
                for cell_id in group["cell_ids"]:
                    record = self.ensure_cell_record(cell_id)
                    if record is None:
                        continue
                    resolved_frames = []
                    for frame_value in getattr(record, "freeze_event_indices", []):
                        try:
                            frame_index = int(frame_value)
                        except (TypeError, ValueError):
                            continue
                        if 0 <= frame_index < total_frame_count:
                            resolved_frames.append(frame_index)
                    per_cell_events.append(sorted(set(resolved_frames)))

                event_pointers = [0] * len(per_cell_events)
                cell_states = [0] * len(per_cell_events)
                for image_index in range(total_frame_count):
                    frozen_count = 0
                    for cell_position, event_frames in enumerate(per_cell_events):
                        while event_pointers[cell_position] < len(event_frames) and event_frames[event_pointers[cell_position]] <= image_index:
                            cell_states[cell_position] = 1 - cell_states[cell_position]
                            event_pointers[cell_position] += 1
                        frozen_count += cell_states[cell_position]
                    state_counts[image_index] = int(frozen_count)
                image_counts_by_sample[group_key] = state_counts
                continue

            freeze_frames = []
            for cell_id in group["cell_ids"]:
                record = self.ensure_cell_record(cell_id)
                if record is None:
                    continue
                resolved_frames = []
                for frame_value in getattr(record, "freeze_event_indices", []):
                    try:
                        resolved_frames.append(int(frame_value))
                    except (TypeError, ValueError):
                        continue
                if resolved_frames:
                    freeze_frames.append(min(resolved_frames))
            freeze_frames.sort()
            cumulative_counts = {}
            freeze_pointer = 0
            for image_index in range(total_frame_count):
                while freeze_pointer < len(freeze_frames) and freeze_frames[freeze_pointer] <= image_index:
                    freeze_pointer += 1
                cumulative_counts[image_index] = int(freeze_pointer)
            image_counts_by_sample[group_key] = cumulative_counts
        return image_counts_by_sample

    def build_tamu_freeze_count_timeseries_sample_groups(self):
        sample_groups = self.build_freeze_count_timeseries_sample_groups(grouping_mode="samples")
        if sample_groups:
            return sample_groups, "samples"
        sample_groups = self.build_freeze_count_timeseries_sample_groups(grouping_mode="all_cells")
        if sample_groups:
            return sample_groups, "all_cells"
        return {}, "samples"

    def build_freeze_count_timeseries_blank_selection(self, sample_groups, blank_sample_names=None):
        metadata_field_names = export_sample_metadata_field_keys(
            getattr(self, "sample_metadata_schema", None)
        )
        blank_identifier_set = {
            str(sample_identifier).strip()
            for sample_identifier in (blank_sample_names or [])
            if str(sample_identifier or "").strip()
        }
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
                    "is_blank": (
                        group_key_text in blank_identifier_set
                        or (sample_id_text and sample_id_text in blank_identifier_set)
                    ),
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
        blank_samples = [sample for sample in matched_samples if sample["is_blank"]]
        output_samples = [sample for sample in matched_samples if not sample["is_blank"]]
        matched_identifiers = {
            identifier
            for sample in matched_samples
            for identifier in (sample.get("group_key", ""), sample.get("sample_id", ""))
            if str(identifier or "").strip()
        }
        unmatched_blank_samples = sorted(
            sample_identifier
            for sample_identifier in blank_identifier_set
            if sample_identifier not in matched_identifiers
        )
        return matched_samples, blank_samples, output_samples, unmatched_blank_samples

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
        cycle_start_seconds = [
            float(timeseries_seconds[index])
            for index in cycle_start_indexes
            if 0 <= int(index) < len(timeseries_seconds)
        ] or [0.0]
        start_timestamp = getattr(parsed_timeseries, "start_timestamp", None)
        image_elapsed_seconds = []
        image_cycle_ids = []
        parsed_image_count = 0
        unparsed_images = []
        for image_index in range(self.frame_count()):
            image_name = self.frame_name(image_index)
            basename = os.path.basename(str(image_name or ""))
            image_timestamp = parse_tamu_image_timestamp(basename)
            if image_timestamp is None or start_timestamp is None:
                image_elapsed_seconds.append(None)
                image_cycle_ids.append(None)
                if image_timestamp is None:
                    unparsed_images.append(basename)
                continue
            parsed_image_count += 1
            elapsed_seconds = float((image_timestamp - start_timestamp).total_seconds())
            image_elapsed_seconds.append(elapsed_seconds)
            image_cycle_ids.append(self.cycle_index_for_position(elapsed_seconds, cycle_start_seconds))
        return {
            "cycle_start_seconds": cycle_start_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(parsed_image_count),
            "unparsed_images": list(unparsed_images),
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
        cycle_start_seconds = [
            float(timeseries_seconds[index])
            for index in cycle_start_indexes
            if 0 <= int(index) < len(timeseries_seconds)
        ] or [0.0]

        start_timestamp = getattr(parsed_timeseries, "start_timestamp", None)
        if start_timestamp is None:
            start_timestamp = timeseries_datetimes[0]

        image_elapsed_seconds = []
        image_cycle_ids = []
        parsed_image_timestamps = []
        image_record_temperatures = []
        for image_record in image_records:
            image_timestamp = getattr(image_record, "timestamp", None)
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
            parsed_image_timestamps.append(image_timestamp)
            image_record_temperatures.append(image_temperature)
            if image_timestamp is None:
                image_elapsed_seconds.append(None)
                image_cycle_ids.append(None)
                continue
            elapsed_seconds = float((image_timestamp - start_timestamp).total_seconds())
            image_elapsed_seconds.append(elapsed_seconds)
            image_cycle_ids.append(self.cycle_index_for_position(elapsed_seconds, cycle_start_seconds))

        return {
            "timeseries_seconds": timeseries_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "cycle_start_seconds": cycle_start_seconds,
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
            first_freeze_frame_by_cell_cycle = {}
            for cell_id in group["cell_ids"]:
                record = self.ensure_cell_record(cell_id)
                if record is None:
                    continue
                cycle_first_frames = {}
                resolved_frames = []
                for frame_value in getattr(record, "freeze_event_indices", []):
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
            image_counts_by_sample[group_key] = cycle_counts
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
        cycle_start_seconds = [
            float(timeseries_seconds[index])
            for index in cycle_start_indexes
            if 0 <= int(index) < len(timeseries_seconds)
        ] or [0.0]

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
        image_elapsed_seconds = []
        image_cycle_ids = []
        for image_timestamp in parsed_image_timestamps:
            if image_timestamp is None:
                image_elapsed_seconds.append(None)
                image_cycle_ids.append(None)
                continue
            elapsed_seconds = float((image_timestamp - timeseries_origin).total_seconds())
            image_elapsed_seconds.append(elapsed_seconds)
            image_cycle_ids.append(
                self.cycle_index_for_position(elapsed_seconds, cycle_start_seconds)
            )

        return {
            "timeseries_origin": timeseries_origin,
            "timeseries_seconds": timeseries_seconds,
            "cycle_start_indexes": cycle_start_indexes,
            "cycle_start_seconds": cycle_start_seconds,
            "image_elapsed_seconds": image_elapsed_seconds,
            "image_cycle_ids": image_cycle_ids,
            "parsed_image_count": int(parsed_count),
            "unparsed_images": list(unparsed_images),
            "parsed_image_timestamps": parsed_image_timestamps,
        }

    def build_standard_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        blank_sample_names=None,
        image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME,
        image_timestamp_style=TIMESTAMP_STYLE_AUTO,
        generated_start_text="",
        frame_interval_seconds=None,
        temperature_timestamp_style=TIMESTAMP_STYLE_AUTO,
        temperature_unit=TEMPERATURE_UNIT_CELSIUS,
        reset_temperature=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples, blank_samples, output_samples, unmatched_blank_samples = (
            self.build_freeze_count_timeseries_blank_selection(
                sample_groups,
                blank_sample_names=blank_sample_names,
            )
        )
        timing_context = self.build_standard_image_timing_context(
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

        image_elapsed_seconds = timing_context["image_elapsed_seconds"]
        image_cycle_ids = timing_context["image_cycle_ids"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(
            sample_groups,
            image_cycle_ids,
        )
        blank_correction_by_image = compute_blank_correction_by_index(
            [sample["group_key"] for sample in blank_samples],
            image_counts_by_sample,
            self.frame_count(),
        )

        timeseries_seconds = np.asarray(
            list(timing_context["timeseries_seconds"]),
            dtype=float,
        )
        temperature_values = np.asarray(
            list(getattr(parsed_timeseries, "temperature_values", [])),
            dtype=float,
        )
        parsed_image_timestamps = timing_context["parsed_image_timestamps"]

        headers = ["timestamp", "temperature_C", "cycle", "image_name", "water blank correction count"]
        sample_column_metadata = []
        for sample in output_samples:
            sample_name = str(sample.get("sample_name", ""))
            headers.append(f"{sample_name} number total")
            headers.append(f"{sample_name} number frozen")
            sample_column_metadata.append(
                self.build_freeze_count_timeseries_sample_column_metadata(sample)
            )

        rows = []
        in_range_image_count = 0
        out_of_range_image_count = 0
        for image_index in range(self.frame_count()):
            basename = os.path.basename(str(self.frame_name(image_index) or ""))
            image_timestamp = parsed_image_timestamps[image_index]
            raw_temperature = None
            elapsed_seconds = (
                image_elapsed_seconds[image_index]
                if image_index < len(image_elapsed_seconds)
                else None
            )
            if image_timestamp is not None and elapsed_seconds is not None:
                interpolated_temperature = np.interp(
                    elapsed_seconds,
                    timeseries_seconds,
                    temperature_values,
                    left=np.nan,
                    right=np.nan,
                )
                if np.isnan(interpolated_temperature):
                    out_of_range_image_count += 1
                else:
                    in_range_image_count += 1
                    raw_temperature = float(interpolated_temperature)

            output_row = [
                image_timestamp.isoformat(timespec="milliseconds")
                if image_timestamp is not None
                else "",
                "" if raw_temperature is None else f"{raw_temperature:.3f}",
                ""
                if image_cycle_ids[image_index] is None
                else str(int(image_cycle_ids[image_index])),
                basename,
                "nan"
                if blank_correction_by_image[image_index] is None
                else str(int(blank_correction_by_image[image_index])),
            ]
            for sample in output_samples:
                group_key = sample["group_key"]
                total_cells = int(sample.get("total_cells", 0))
                frozen_count = image_counts_by_sample.get(group_key, {}).get(
                    image_index,
                    0,
                )
                adjusted_total, adjusted_frozen = apply_blank_correction_counts(
                    total_cells,
                    frozen_count,
                    blank_correction_by_image[image_index],
                )
                output_row.append(str(int(adjusted_total)))
                output_row.append(str(int(adjusted_frozen)))
            rows.append(output_row)

        if in_range_image_count <= 0:
            raise TemperatureImportError(
                "No loaded frame timestamp falls inside the standard temperature CSV timeseries range."
            )

        timeseries_timestamp_texts = list(getattr(parsed_timeseries, "timeseries_timestamp_texts", []))
        summary = {
            "source_path": str(getattr(parsed_timeseries, "file_path", "")),
            "source_type": "standard_csv",
            "matched_samples": [sample["sample_name"] for sample in output_samples],
            "matched_blank_samples": [sample["sample_name"] for sample in blank_samples],
            "sample_total_cells": [
                {
                    "sample_id": str(sample.get("sample_id", "") or ""),
                    "sample_name": str(sample.get("sample_name", "")),
                    "total_cells": int(sample.get("total_cells", 0)),
                    "role": "blank" if bool(sample.get("is_blank")) else "sample",
                }
                for sample in matched_samples
            ],
            "sample_column_metadata": sample_column_metadata,
            "grouping_mode": str(grouping_mode),
            "count_mode": "cycle_reset",
            "timeseries_start_timestamp": (
                timeseries_timestamp_texts[0]
                if timeseries_timestamp_texts
                else timing_context["timeseries_origin"].isoformat(timespec="milliseconds")
            ),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            "cycle_count": int(len(timing_context["cycle_start_seconds"])),
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
            "total_images": int(self.frame_count()),
            "parsed_image_count": int(timing_context["parsed_image_count"]),
            "in_range_image_count": int(in_range_image_count),
            "out_of_range_image_count": int(out_of_range_image_count),
            "unparsed_image_count": int(len(timing_context["unparsed_images"])),
            "unparsed_images_preview": list(timing_context["unparsed_images"][:5]),
            "unmatched_blank_samples": unmatched_blank_samples,
            "image_timestamp_source": str(image_timestamp_source),
            "image_timestamp_style": str(image_timestamp_style),
            "temperature_timestamp_style": str(temperature_timestamp_style),
            "temperature_unit": str(temperature_unit),
        }
        return headers, rows, summary

    def build_csu_freeze_count_timeseries_results(self, parsed_data, blank_sample_names=None, reset_temperature=None):
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
        blank_identifier_set = {
            str(sample_identifier).strip()
            for sample_identifier in (blank_sample_names or [])
            if str(sample_identifier or "").strip()
        }

        matched_samples = []
        for dat_column in dat_sample_columns:
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
                    "is_blank": (
                        group_key in blank_identifier_set
                        or (sample_id and sample_id in blank_identifier_set)
                    ),
                }
            )

        matched_group_keys = {str(sample.get("group_key", "")) for sample in matched_samples}
        for group in sample_groups.values():
            if str(group.get("group_role", "")) not in {"unassigned_cell", "unassigned_cells"}:
                continue
            group_key = str(group.get("group_key", ""))
            if group_key in matched_group_keys:
                continue
            normalized_name = normalize_sample_name(group.get("sample_name", ""))
            matched_samples.append(
                {
                    "group_key": group_key,
                    "group_role": str(group.get("group_role", "unassigned_cells") or "unassigned_cells"),
                    "sample_id": "",
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
                    "is_blank": group_key in blank_identifier_set,
                }
            )

        unmatched_app_samples = sorted(
            group["sample_name"]
            for normalized_name, groups in groups_by_normalized_name.items()
            for group in groups
            if normalized_name not in dat_columns_by_name
            and str(group.get("group_role", "")) not in {"unassigned_cell", "unassigned_cells"}
        )
        unmatched_dat_samples = sorted(
            column_name
            for normalized_name, column_name in dat_columns_by_name.items()
            if normalized_name not in groups_by_normalized_name
        )
        unmatched_blank_samples = sorted(
            sample_identifier
            for sample_identifier in blank_identifier_set
            if sample_identifier not in {
                identifier
                for sample in matched_samples
                for identifier in (sample.get("group_key", ""), sample.get("sample_id", ""))
                if str(identifier or "").strip()
            }
        )

        image_index_by_name = {
            os.path.basename(str(image_name)).casefold(): index
            for index, image_name in (
                (frame_index, self.frame_name(frame_index))
                for frame_index in range(self.frame_count())
            )
        }
        parsed_rows = list(parsed_data.get("rows", []))
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
            picture_name = os.path.basename(str(getattr(row, "picture_name", ""))).casefold()
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
            if dat_column is None:
                raw_counts = [0 for _row in parsed_rows]
            else:
                raw_counts = [
                    int(getattr(row, "sample_counts", {}).get(dat_column, 0))
                    for row in parsed_rows
                ]
            anchor_counts = {}
            image_counts = image_counts_by_sample.get(group_key, {})
            for row in parsed_rows:
                picture_name = os.path.basename(str(getattr(row, "picture_name", ""))).casefold()
                if not picture_name:
                    continue
                image_index = image_index_by_name.get(picture_name)
                if image_index is None:
                    continue
                anchor_counts[int(row.row_index)] = int(image_counts.get(image_index, 0))
            corrected_counts_by_sample[group_key] = self.reconcile_counts_by_cycle(
                raw_counts,
                anchor_counts,
                total_cells,
                row_cycle_ids,
            )

        blank_samples = [sample for sample in matched_samples if sample["is_blank"]]
        output_samples = [sample for sample in matched_samples if not sample["is_blank"]]
        blank_correction_by_row = compute_blank_correction_by_index(
            [sample["group_key"] for sample in blank_samples],
            corrected_counts_by_sample,
            len(parsed_rows),
        )

        headers = ["timestamp", "temperature_C", "cycle", "picture", "water blank correction count"]
        sample_column_metadata = []
        for sample in output_samples:
            sample_name = str(sample["sample_name"])
            headers.append(f"{sample_name} number total")
            headers.append(f"{sample_name} number frozen")
            sample_column_metadata.append(
                self.build_freeze_count_timeseries_sample_column_metadata(sample)
            )

        rows = []
        for row in parsed_rows:
            row_index = int(row.row_index)
            blank_correction = blank_correction_by_row[row_index] if row_index < len(blank_correction_by_row) else 0
            output_row = [
                str(getattr(row, "timestamp_text", "") or ""),
                "" if getattr(row, "avg_temp", None) is None else f"{float(row.avg_temp):.3f}",
                str(int(row_cycle_ids[row_index])) if row_index < len(row_cycle_ids) else "0",
                str(getattr(row, "picture_name", "") or ""),
                "nan" if blank_correction is None else str(int(blank_correction)),
            ]
            for sample in output_samples:
                group_key = sample["group_key"]
                total_cells = int(sample["total_cells"])
                sample_counts = corrected_counts_by_sample.get(group_key, [])
                frozen_value = sample_counts[row_index] if row_index < len(sample_counts) else 0
                adjusted_total, adjusted_frozen = apply_blank_correction_counts(
                    total_cells,
                    frozen_value,
                    blank_correction,
                )
                output_row.append(str(int(adjusted_total)))
                output_row.append(str(int(adjusted_frozen)))
            rows.append(output_row)

        summary = {
            "source_path": str(parsed_data.get("file_path", "")),
            "matched_samples": [sample["sample_name"] for sample in output_samples],
            "matched_blank_samples": [sample["sample_name"] for sample in blank_samples],
            "sample_total_cells": [
                {
                    "sample_id": str(sample["sample_id"] or ""),
                    "sample_name": str(sample["sample_name"]),
                    "total_cells": int(sample["total_cells"]),
                    "role": "blank" if bool(sample["is_blank"]) else "sample",
                }
                for sample in matched_samples
            ],
            "sample_column_metadata": sample_column_metadata,
            "unmatched_app_samples": unmatched_app_samples,
            "unmatched_dat_samples": unmatched_dat_samples,
            "unmatched_blank_samples": unmatched_blank_samples,
            "matched_picture_rows": int(picture_rows_matched),
            "matched_sample_count": int(len(output_samples)),
            "total_picture_rows": int(sum(1 for row in parsed_rows if getattr(row, "picture_name", ""))),
            "cycle_count": int(max(row_cycle_ids) + 1) if row_cycle_ids else 1,
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
        }
        return headers, rows, summary

    def build_tamu_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        calibration_by_well=None,
        blank_sample_names=None,
        reset_temperature=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples, blank_samples, output_samples, unmatched_blank_samples = (
            self.build_freeze_count_timeseries_blank_selection(
                sample_groups,
                blank_sample_names=blank_sample_names,
            )
        )
        timing_context = self.build_tamu_image_timing_context(parsed_timeseries, reset_temperature=reset_temperature)
        cycle_start_seconds = timing_context["cycle_start_seconds"]
        image_elapsed_seconds = timing_context["image_elapsed_seconds"]
        image_cycle_ids = timing_context["image_cycle_ids"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)
        blank_correction_by_image = compute_blank_correction_by_index(
            [sample["group_key"] for sample in blank_samples],
            image_counts_by_sample,
            self.frame_count(),
        )

        timeseries_seconds = np.asarray(list(getattr(parsed_timeseries, "timeseries_seconds", [])), dtype=float)
        temperature_values = np.asarray(list(getattr(parsed_timeseries, "temperature_values", [])), dtype=float)
        start_timestamp = getattr(parsed_timeseries, "start_timestamp", None)
        include_corrected_temperature = bool(calibration_by_well)

        calibrated_cell_ids = set()
        if calibration_by_well:
            for group in output_samples:
                for cell_id in group.get("cell_ids", []):
                    if int(cell_id) in calibration_by_well:
                        calibrated_cell_ids.add(int(cell_id))

        headers = ["timestamp", "temperature_C", "cycle", "image_name", "water blank correction count"]
        sample_column_metadata = []
        for sample in output_samples:
            sample_name = str(sample.get("sample_name", ""))
            if include_corrected_temperature:
                headers.append(f"{sample_name} corrected temperature_C")
            headers.append(f"{sample_name} number total")
            headers.append(f"{sample_name} number frozen")
            sample_column_metadata.append(
                self.build_freeze_count_timeseries_sample_column_metadata(sample)
            )

        rows = []
        in_range_image_count = 0
        out_of_range_image_count = 0
        for image_index in range(self.frame_count()):
            image_name = self.frame_name(image_index)
            basename = os.path.basename(str(image_name or ""))
            image_timestamp = parse_tamu_image_timestamp(basename)
            raw_temperature = None
            elapsed_seconds = image_elapsed_seconds[image_index] if image_index < len(image_elapsed_seconds) else None
            if image_timestamp is not None and elapsed_seconds is not None:
                interpolated_temperature = np.interp(
                    elapsed_seconds,
                    timeseries_seconds,
                    temperature_values,
                    left=np.nan,
                    right=np.nan,
                )
                if np.isnan(interpolated_temperature):
                    out_of_range_image_count += 1
                else:
                    in_range_image_count += 1
                    raw_temperature = float(interpolated_temperature)

            output_row = [
                image_timestamp.isoformat(timespec="milliseconds") if image_timestamp is not None else "",
                "" if raw_temperature is None else f"{raw_temperature:.3f}",
                "" if image_cycle_ids[image_index] is None else str(int(image_cycle_ids[image_index])),
                basename,
                "nan"
                if blank_correction_by_image[image_index] is None
                else str(int(blank_correction_by_image[image_index])),
            ]
            for sample in output_samples:
                group_key = sample["group_key"]
                if include_corrected_temperature:
                    corrected_temperature = self.corrected_temperature_for_group(
                        raw_temperature,
                        sample,
                        calibration_by_well,
                    )
                    output_row.append("" if corrected_temperature is None else f"{corrected_temperature:.3f}")
                total_cells = int(sample.get("total_cells", 0))
                frozen_count = image_counts_by_sample.get(group_key, {}).get(image_index, 0)
                adjusted_total, adjusted_frozen = apply_blank_correction_counts(
                    total_cells,
                    frozen_count,
                    blank_correction_by_image[image_index],
                )
                output_row.append(str(int(adjusted_total)))
                output_row.append(str(int(adjusted_frozen)))
            rows.append(output_row)

        if in_range_image_count <= 0:
            raise TemperatureImportError(
                "No loaded image timestamp falls inside the TAMU Linkam temperature timeseries range."
            )

        summary = {
            "source_path": str(getattr(parsed_timeseries, "file_path", "")),
            "source_type": "tamu",
            "matched_samples": [sample["sample_name"] for sample in output_samples],
            "matched_blank_samples": [sample["sample_name"] for sample in blank_samples],
            "sample_total_cells": [
                {
                    "sample_id": str(sample.get("sample_id", "") or ""),
                    "sample_name": str(sample.get("sample_name", "")),
                    "total_cells": int(sample.get("total_cells", 0)),
                    "role": "blank" if bool(sample.get("is_blank")) else "sample",
                }
                for sample in matched_samples
            ],
            "sample_column_metadata": sample_column_metadata,
            "grouping_mode": str(grouping_mode),
            "count_mode": "cycle_reset",
            "timeseries_start_timestamp": str(getattr(parsed_timeseries, "start_timestamp_text", "") or ""),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            "sample_period_seconds": getattr(parsed_timeseries, "sample_period_seconds", None),
            "cycle_count": int(len(cycle_start_seconds)),
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
            "total_images": int(self.frame_count()),
            "parsed_image_count": int(timing_context["parsed_image_count"]),
            "in_range_image_count": int(in_range_image_count),
            "out_of_range_image_count": int(out_of_range_image_count),
            "unparsed_image_count": int(len(timing_context["unparsed_images"])),
            "unparsed_images_preview": list(timing_context["unparsed_images"][:5]),
            "calibration_path": "" if not calibration_by_well else str(getattr(self, "last_temperature_calibration_path", "") or ""),
            "calibrated_cell_count": int(len(calibrated_cell_ids)),
            "unmatched_blank_samples": unmatched_blank_samples,
        }
        return headers, rows, summary

    def build_pku_linksys32_freeze_count_timeseries_results(
        self,
        parsed_timeseries,
        blank_sample_names=None,
        reset_temperature=None,
    ):
        sample_groups, grouping_mode = self.build_tamu_freeze_count_timeseries_sample_groups()
        matched_samples, blank_samples, output_samples, unmatched_blank_samples = (
            self.build_freeze_count_timeseries_blank_selection(
                sample_groups,
                blank_sample_names=blank_sample_names,
            )
        )
        timing_context = self.build_pku_linksys32_image_timing_context(
            parsed_timeseries,
            reset_temperature=reset_temperature,
        )
        cycle_start_seconds = timing_context["cycle_start_seconds"]
        image_cycle_ids = timing_context["image_cycle_ids"]
        parsed_image_timestamps = timing_context["parsed_image_timestamps"]
        image_record_temperatures = timing_context["image_record_temperatures"]
        image_counts_by_sample = self.build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)
        blank_correction_by_image = compute_blank_correction_by_index(
            [sample["group_key"] for sample in blank_samples],
            image_counts_by_sample,
            self.frame_count(),
        )

        headers = ["timestamp", "temperature_C", "cycle", "image_name", "water blank correction count"]
        sample_column_metadata = []
        for sample in output_samples:
            sample_name = str(sample.get("sample_name", ""))
            headers.append(f"{sample_name} number total")
            headers.append(f"{sample_name} number frozen")
            sample_column_metadata.append(
                self.build_freeze_count_timeseries_sample_column_metadata(sample)
            )

        rows = []
        tagged_temperature_count = 0
        for image_index in range(self.frame_count()):
            image_name = self.frame_name(image_index)
            basename = os.path.basename(str(image_name or ""))
            image_timestamp = (
                parsed_image_timestamps[image_index]
                if image_index < len(parsed_image_timestamps)
                else None
            )
            raw_temperature = (
                image_record_temperatures[image_index]
                if image_index < len(image_record_temperatures)
                else None
            )
            if raw_temperature is not None:
                tagged_temperature_count += 1

            output_row = [
                image_timestamp.isoformat(timespec="milliseconds") if image_timestamp is not None else "",
                "" if raw_temperature is None else f"{raw_temperature:.3f}",
                "" if image_cycle_ids[image_index] is None else str(int(image_cycle_ids[image_index])),
                basename,
                "nan"
                if blank_correction_by_image[image_index] is None
                else str(int(blank_correction_by_image[image_index])),
            ]
            for sample in output_samples:
                group_key = sample["group_key"]
                total_cells = int(sample.get("total_cells", 0))
                frozen_count = image_counts_by_sample.get(group_key, {}).get(image_index, 0)
                adjusted_total, adjusted_frozen = apply_blank_correction_counts(
                    total_cells,
                    frozen_count,
                    blank_correction_by_image[image_index],
                )
                output_row.append(str(int(adjusted_total)))
                output_row.append(str(int(adjusted_frozen)))
            rows.append(output_row)

        summary = {
            "source_path": str(getattr(parsed_timeseries, "file_path", "")),
            "source_type": "pku_linksys32_iml",
            "matched_samples": [sample["sample_name"] for sample in output_samples],
            "matched_blank_samples": [sample["sample_name"] for sample in blank_samples],
            "sample_total_cells": [
                {
                    "sample_id": str(sample.get("sample_id", "") or ""),
                    "sample_name": str(sample.get("sample_name", "")),
                    "total_cells": int(sample.get("total_cells", 0)),
                    "role": "blank" if bool(sample.get("is_blank")) else "sample",
                }
                for sample in matched_samples
            ],
            "sample_column_metadata": sample_column_metadata,
            "grouping_mode": str(grouping_mode),
            "count_mode": "cycle_reset",
            "timeseries_start_timestamp": str(getattr(parsed_timeseries, "start_timestamp_text", "") or ""),
            "timeseries_row_count": int(getattr(parsed_timeseries, "timeseries_row_count", 0) or 0),
            "sample_period_seconds": getattr(parsed_timeseries, "sample_period_seconds", None),
            "image_record_count": int(timing_context.get("image_record_count", 0)),
            "linksys32_version": str(getattr(parsed_timeseries, "version", "") or ""),
            "cycle_count": int(len(cycle_start_seconds)),
            "reset_temperature": self.normalize_temperature_reset_threshold(reset_temperature),
            "total_images": int(self.frame_count()),
            "parsed_image_count": int(timing_context["parsed_image_count"]),
            "temperature_source": "pku_linksys32_image_record",
            "tagged_temperature_count": int(tagged_temperature_count),
            "unparsed_image_count": int(len(timing_context["unparsed_images"])),
            "unparsed_images_preview": list(timing_context["unparsed_images"][:5]),
            "unmatched_blank_samples": unmatched_blank_samples,
        }
        return headers, rows, summary
