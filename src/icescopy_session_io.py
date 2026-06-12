import csv
import io
import json
import zipfile

from icescopy_cell_items import CellCircle
from icescopy_sample_metadata import (
    ALLOWED_SAMPLE_TYPES,
    default_sample_metadata_schema,
    export_sample_metadata_field_keys,
    normalize_sample_catalog_record,
    sample_metadata_field_keys,
    sample_metadata_schema_from_payload,
    sample_metadata_schema_to_payload,
)


SESSION_STATE_FILENAME = "session.json"
GRAYSCALE_CSV_FILENAME = "grayscale.csv"
FREEZE_CSV_FILENAME = "freeze.csv"
FREEZE_COUNT_TIMESERIES_CSV_FILENAME = "freeze_count_timeseries.csv"
SAMPLE_CATALOG_FIELD_NAMES = sample_metadata_field_keys(default_sample_metadata_schema())
FREEZE_COUNT_TIMESERIES_SAMPLE_METADATA_FIELD_NAMES = export_sample_metadata_field_keys(
    default_sample_metadata_schema()
)
FREEZE_COUNT_TIMESERIES_PREAMBLE_KEYS = (
    "format_name",
    "file_version",
    "project_name",
    "user_name",
    "institution",
    "analysis_date",
    "reset_temperature_C",
)
FREEZE_COUNT_TIMESERIES_METADATA_ROW_LABELS = (
    "sample_id",
    "cell_number",
) + FREEZE_COUNT_TIMESERIES_SAMPLE_METADATA_FIELD_NAMES
FREEZE_COUNT_TIMESERIES_FORMAT_NAME = "icescopy_freeze_count_timeseries"
FREEZE_COUNT_TIMESERIES_FILE_VERSION = 1
FREEZE_COUNT_TIMESERIES_MISSING_VALUE = "nan"
CSV_LINE_TERMINATOR = "\n"
SORT_MODE_LABELS = {
    "natural_filename": "Natural Filename",
    "filename_asc": "Filename (A-Z)",
    "filename_desc": "Filename (Z-A)",
    "created_time": "Created Time",
    "modified_time": "Modified Time",
    "exif_time": "EXIF Time",
}


def freeze_count_timeseries_metadata_row_labels(sample_metadata_schema=None):
    return ("sample_id", "cell_number") + export_sample_metadata_field_keys(
        sample_metadata_schema
    )


def serialize_sample_catalog_payload(catalog, sample_metadata_schema=None):
    payload = {}
    if not isinstance(catalog, dict):
        return payload
    for sample_id, sample_record in sorted(catalog.items(), key=lambda pair: int(pair[0])):
        payload[str(int(sample_id))] = normalize_sample_catalog_record(
            sample_record,
            sample_metadata_schema,
        )
    return payload


def deserialize_sample_catalog_payload(payload, sample_metadata_schema=None):
    catalog = {}
    if not isinstance(payload, dict):
        return catalog
    for key, value in payload.items():
        try:
            sample_id = int(key)
        except (TypeError, ValueError):
            continue
        catalog[sample_id] = normalize_sample_catalog_record(value, sample_metadata_schema)
    return catalog


def build_freeze_count_timeseries_csv_text(
    headers,
    rows,
    *,
    session_metadata=None,
    summary=None,
):
    session_metadata = dict(session_metadata or {})
    summary = dict(summary or {})
    sample_metadata_schema = sample_metadata_schema_from_payload(
        summary.get("sample_metadata_schema")
    )
    sample_column_metadata = list(summary.get("sample_column_metadata") or [])

    def metadata_text(value):
        text = str(value or "").strip()
        return text if text else FREEZE_COUNT_TIMESERIES_MISSING_VALUE

    preamble_values = {
        "format_name": FREEZE_COUNT_TIMESERIES_FORMAT_NAME,
        "file_version": str(FREEZE_COUNT_TIMESERIES_FILE_VERSION),
        "project_name": metadata_text(session_metadata.get("project_name", "")),
        "user_name": metadata_text(session_metadata.get("user_name", "")),
        "institution": metadata_text(session_metadata.get("institution", "")),
        "analysis_date": metadata_text(session_metadata.get("date", "")),
        "reset_temperature_C": metadata_text(summary.get("reset_temperature")),
    }

    buffer = io.StringIO()
    for key in FREEZE_COUNT_TIMESERIES_PREAMBLE_KEYS:
        buffer.write(f"# {key}: {preamble_values.get(key, '')}\n")

    if sample_column_metadata:
        for row_label in freeze_count_timeseries_metadata_row_labels(sample_metadata_schema):
            metadata_row = [row_label]
            for sample_metadata in sample_column_metadata:
                value_text = metadata_text(sample_metadata.get(row_label, ""))
                metadata_row.append(value_text)
            buffer.write(f"# {_csv_row_to_text(metadata_row)}")
    buffer.write(_rows_to_csv_text(headers, rows))
    return buffer.getvalue()


def cell_circle_to_dict(circle):
    return {
        "circle_positions": list(circle.circle_positions),
        "circle_sizes": circle.circle_sizes,
        "circle_pixel_positions": list(circle.circle_pixel_positions),
        "cell_id": circle.cell_id,
        "edit_chosen": getattr(circle, "edit_chosen", False),
    }


def cell_circle_from_dict(main_window, payload):
    raw_cell_id = payload.get("cell_id", 0)
    try:
        cell_id = int(raw_cell_id)
    except (TypeError, ValueError):
        cell_id = 0
    circle = CellCircle(
        main_window,
        tuple(payload["circle_positions"]),
        payload["circle_sizes"],
        tuple(payload["circle_pixel_positions"]),
        cell_id,
    )
    circle.edit_chosen = payload.get("edit_chosen", False)
    return circle


def build_session_payload(main_window):
    keyframe_cell_items_dict = {
        str(frame): [cell_circle_to_dict(circle) for circle in circles]
        for frame, circles in main_window.keyframe_cell_items_dict.items()
    }

    payload = {
        "session_metadata": main_window.serialize_session_metadata(),
        "image_edit_state": main_window.serialize_image_edit_state(),
        "image_width": main_window.image_width,
        "frame_source": main_window.frame_source_session_payload(),
        "image_paths": main_window.imagePaths.copy(),
        "image_names": main_window.imageNames.copy(),
        "image_index": main_window.image_index,
        "image_list_entry_ids": main_window.image_list_entry_ids.copy(),
        "next_image_list_entry_id": main_window.next_image_list_entry_id,
        "sort_mode": main_window.sort_mode,
        "cell_items": [cell_circle_to_dict(circle) for circle in main_window.cell_items],
        "next_cell_id": int(main_window.next_cell_id),
        "cell_records_by_id": main_window.serialize_cell_records(),
        "sample_metadata_schema": (
            main_window.serialize_sample_metadata_schema()
            if hasattr(main_window, "serialize_sample_metadata_schema")
            else sample_metadata_schema_to_payload(default_sample_metadata_schema())
        ),
        "sample_catalog": main_window.serialize_sample_catalog(),
        "next_sample_id": int(main_window.next_sample_id),
        "keyframe_list": main_window.keyframe_list.copy(),
        "flagframe_list": main_window.flagframe_list.copy(),
        "analysis_start_frame_list": getattr(main_window, "analysis_start_frame_list", []).copy(),
        "analysis_end_frame_list": getattr(main_window, "analysis_end_frame_list", []).copy(),
        "keyframe_cell_items_dict": keyframe_cell_items_dict,
        "tool_mode": main_window.tool_mode,
        "tool_settings": main_window.serialize_tool_settings(),
        "last_grayscale_output_path": main_window.last_grayscale_output_path,
        "last_freeze_output_path": main_window.last_freeze_output_path,
        "last_temperature_import_path": main_window.last_temperature_import_path,
        "last_temperature_calibration_path": main_window.last_temperature_calibration_path,
        "last_temperature_reset_temperature": main_window.last_temperature_reset_temperature,
        "last_temperature_blank_sample_names": list(main_window.last_temperature_blank_sample_names),
        "last_standard_temperature_image_timestamp_source": main_window.last_standard_temperature_image_timestamp_source,
        "last_standard_temperature_image_timestamp_style": main_window.last_standard_temperature_image_timestamp_style,
        "last_standard_temperature_temperature_timestamp_style": main_window.last_standard_temperature_temperature_timestamp_style,
        "last_standard_temperature_use_image_timestamp_style": bool(main_window.last_standard_temperature_use_image_timestamp_style),
        "last_standard_temperature_generated_start_text": main_window.last_standard_temperature_generated_start_text,
        "last_standard_temperature_frame_interval_seconds": main_window.last_standard_temperature_frame_interval_seconds,
        "last_standard_temperature_temperature_unit": main_window.last_standard_temperature_temperature_unit,
        "freeze_count_timeseries_summary": dict(main_window.freeze_count_timeseries_summary),
        "console_history": main_window.terminal.toPlainText(),
    }
    return payload


def build_restore_state(main_window, payload, grayscale_table, freeze_table, freeze_count_timeseries_table):
    cell_items = [cell_circle_from_dict(main_window, item) for item in payload["cell_items"]]
    keyframe_cell_items_dict = {
        int(frame): [cell_circle_from_dict(main_window, item) for item in circles]
        for frame, circles in payload["keyframe_cell_items_dict"].items()
    }

    grayscale_headers, grayscale_rows = grayscale_table
    freeze_headers, freeze_rows = freeze_table
    freeze_count_timeseries_headers, freeze_count_timeseries_rows = freeze_count_timeseries_table

    default_tool_settings = (
        main_window.default_tool_settings()
        if hasattr(main_window, "default_tool_settings")
        else {}
    )

    return {
        "session_metadata": payload["session_metadata"],
        "image_edit_state": payload["image_edit_state"],
        "cell_items": cell_items,
        "next_cell_id": payload["next_cell_id"],
        "cell_records_by_id": payload["cell_records_by_id"],
        "sample_metadata_schema": sample_metadata_schema_from_payload(
            payload.get("sample_metadata_schema")
        ),
        "sample_catalog": payload.get("sample_catalog", {}),
        "next_sample_id": payload["next_sample_id"],
        "keyframe_list": payload["keyframe_list"],
        "flagframe_list": payload["flagframe_list"],
        "analysis_start_frame_list": payload.get("analysis_start_frame_list", []),
        "analysis_end_frame_list": payload.get("analysis_end_frame_list", []),
        "keyframe_cell_items_dict": keyframe_cell_items_dict,
        "image_width": payload["image_width"],
        "frame_source": payload.get("frame_source", {
            "kind": "image_sequence",
            "image_paths": payload["image_paths"],
        }),
        "imagePaths": payload["image_paths"],
        "imageNames": payload["image_names"],
        "image_index": payload["image_index"],
        "image_list_entry_ids": payload["image_list_entry_ids"],
        "next_image_list_entry_id": payload["next_image_list_entry_id"],
        "sort_mode": payload["sort_mode"],
        "last_grayscale_output_path": payload["last_grayscale_output_path"],
        "last_freeze_output_path": payload["last_freeze_output_path"],
        "last_temperature_import_path": payload["last_temperature_import_path"],
        "last_temperature_calibration_path": payload["last_temperature_calibration_path"],
        "last_temperature_reset_temperature": payload["last_temperature_reset_temperature"],
        "last_temperature_blank_sample_names": list(payload["last_temperature_blank_sample_names"]),
        "last_standard_temperature_image_timestamp_source": payload["last_standard_temperature_image_timestamp_source"],
        "last_standard_temperature_image_timestamp_style": payload["last_standard_temperature_image_timestamp_style"],
        "last_standard_temperature_temperature_timestamp_style": payload["last_standard_temperature_temperature_timestamp_style"],
        "last_standard_temperature_use_image_timestamp_style": payload["last_standard_temperature_use_image_timestamp_style"],
        "last_standard_temperature_generated_start_text": payload["last_standard_temperature_generated_start_text"],
        "last_standard_temperature_frame_interval_seconds": payload["last_standard_temperature_frame_interval_seconds"],
        "last_standard_temperature_temperature_unit": payload["last_standard_temperature_temperature_unit"],
        "grayscale_results_headers": grayscale_headers,
        "grayscale_results_rows": grayscale_rows,
        "freeze_results_headers": freeze_headers,
        "freeze_results_rows": freeze_rows,
        "freeze_count_timeseries_headers": freeze_count_timeseries_headers,
        "freeze_count_timeseries_rows": freeze_count_timeseries_rows,
        "freeze_count_timeseries_summary": dict(payload["freeze_count_timeseries_summary"]),
        "tool_mode": payload["tool_mode"],
        "tool_settings": payload.get("tool_settings", default_tool_settings),
        "console_history": payload["console_history"],
    }


def _rows_to_csv_text(headers, rows):
    buffer = io.StringIO()
    writer = _create_csv_writer(buffer)
    if headers:
        writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def _create_csv_writer(buffer):
    return csv.writer(buffer, lineterminator=CSV_LINE_TERMINATOR)


def _csv_row_to_text(row):
    buffer = io.StringIO()
    _create_csv_writer(buffer).writerow(row)
    return buffer.getvalue()


def _csv_text_to_rows(text):
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def save_session_bundle(
    file_path,
    payload,
    grayscale_headers,
    grayscale_rows,
    freeze_headers,
    freeze_rows,
    freeze_count_timeseries_headers,
    freeze_count_timeseries_rows,
):
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(SESSION_STATE_FILENAME, json.dumps(payload, indent=2))
        if grayscale_headers:
            archive.writestr(GRAYSCALE_CSV_FILENAME, _rows_to_csv_text(grayscale_headers, grayscale_rows))
        if freeze_headers:
            archive.writestr(FREEZE_CSV_FILENAME, _rows_to_csv_text(freeze_headers, freeze_rows))
        if freeze_count_timeseries_headers:
            archive.writestr(
                FREEZE_COUNT_TIMESERIES_CSV_FILENAME,
                _rows_to_csv_text(freeze_count_timeseries_headers, freeze_count_timeseries_rows),
            )


def load_session_bundle(file_path):
    with zipfile.ZipFile(file_path, "r") as archive:
        payload = json.loads(archive.read(SESSION_STATE_FILENAME).decode("utf-8"))
        grayscale_table = ([], [])
        freeze_table = ([], [])
        freeze_count_timeseries_table = ([], [])

        if GRAYSCALE_CSV_FILENAME in archive.namelist():
            grayscale_table = _csv_text_to_rows(archive.read(GRAYSCALE_CSV_FILENAME).decode("utf-8"))
        if FREEZE_CSV_FILENAME in archive.namelist():
            freeze_table = _csv_text_to_rows(archive.read(FREEZE_CSV_FILENAME).decode("utf-8"))
        if FREEZE_COUNT_TIMESERIES_CSV_FILENAME in archive.namelist():
            freeze_count_timeseries_table = _csv_text_to_rows(
                archive.read(FREEZE_COUNT_TIMESERIES_CSV_FILENAME).decode("utf-8")
            )

    return payload, grayscale_table, freeze_table, freeze_count_timeseries_table
