import csv
import io
import json
import zipfile

from icescopy_cell_items import CellCircle


SESSION_SCHEMA_VERSION = 6
SESSION_STATE_FILENAME = "session.json"
GRAYSCALE_CSV_FILENAME = "grayscale.csv"
FREEZE_CSV_FILENAME = "freeze.csv"
TEMPERATURE_SYNC_CSV_FILENAME = "temperature_sync.csv"
SORT_MODE_LABELS = {
    "natural_filename": "Natural Filename",
    "filename_asc": "Filename (A-Z)",
    "filename_desc": "Filename (Z-A)",
    "created_time": "Created Time",
    "modified_time": "Modified Time",
    "exif_time": "EXIF Time",
}


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
        "schema_version": SESSION_SCHEMA_VERSION,
        "session_metadata": main_window.serialize_session_metadata() if hasattr(main_window, "serialize_session_metadata") else {},
        "image_edit_state": main_window.serialize_image_edit_state() if hasattr(main_window, "serialize_image_edit_state") else {},
        "image_width": main_window.image_width,
        "image_paths": main_window.imagePaths.copy(),
        "image_names": main_window.imageNames.copy(),
        "image_index": main_window.image_index,
        "image_list_entry_ids": main_window.image_list_entry_ids.copy(),
        "next_image_list_entry_id": main_window.next_image_list_entry_id,
        "sort_mode": getattr(main_window, "sort_mode", "natural_filename"),
        "cell_items": [cell_circle_to_dict(circle) for circle in main_window.cell_items],
        "next_cell_id": int(getattr(main_window, "next_cell_id", 0)),
        "cell_records_by_id": main_window.serialize_cell_records() if hasattr(main_window, "serialize_cell_records") else {},
        "sample_catalog": main_window.serialize_sample_catalog() if hasattr(main_window, "serialize_sample_catalog") else {},
        "next_sample_id": int(getattr(main_window, "next_sample_id", 0)),
        "keyframe_list": main_window.keyframe_list.copy(),
        "flagframe_list": main_window.flagframe_list.copy(),
        "keyframe_cell_items_dict": keyframe_cell_items_dict,
        "tool_mode": getattr(main_window, "tool_mode", "cursor"),
        "last_grayscale_output_path": main_window.last_grayscale_output_path,
        "last_freeze_output_path": main_window.last_freeze_output_path,
        "last_temperature_import_path": getattr(main_window, "last_temperature_import_path", None),
        "last_temperature_calibration_path": getattr(main_window, "last_temperature_calibration_path", None),
        "last_temperature_reset_temperature": getattr(main_window, "last_temperature_reset_temperature", None),
        "temperature_sync_summary": dict(getattr(main_window, "temperature_sync_summary", {})),
        "console_history": main_window.terminal.toPlainText() if hasattr(main_window, "terminal") else "",
    }
    return payload


def build_restore_state(main_window, payload, grayscale_table, freeze_table, temperature_sync_table):
    cell_items = [cell_circle_from_dict(main_window, item) for item in payload["cell_items"]]
    keyframe_cell_items_dict = {
        int(frame): [cell_circle_from_dict(main_window, item) for item in circles]
        for frame, circles in payload["keyframe_cell_items_dict"].items()
    }

    grayscale_headers, grayscale_rows = grayscale_table
    freeze_headers, freeze_rows = freeze_table
    temperature_sync_headers, temperature_sync_rows = temperature_sync_table

    return {
        "session_metadata": payload.get("session_metadata", {}),
        "image_edit_state": payload.get("image_edit_state", {}),
        "cell_items": cell_items,
        "next_cell_id": payload.get("next_cell_id", 0),
        "cell_records_by_id": payload.get("cell_records_by_id", {}),
        "sample_catalog": payload.get("sample_catalog", {}),
        "next_sample_id": payload.get("next_sample_id", 0),
        "keyframe_list": payload["keyframe_list"],
        "flagframe_list": payload["flagframe_list"],
        "keyframe_cell_items_dict": keyframe_cell_items_dict,
        "image_width": payload["image_width"],
        "imagePaths": payload["image_paths"],
        "imageNames": payload["image_names"],
        "image_index": payload["image_index"],
        "image_list_entry_ids": payload["image_list_entry_ids"],
        "next_image_list_entry_id": payload["next_image_list_entry_id"],
        "sort_mode": payload.get("sort_mode", "natural_filename"),
        "last_grayscale_output_path": payload.get("last_grayscale_output_path"),
        "last_freeze_output_path": payload.get("last_freeze_output_path"),
        "last_temperature_import_path": payload.get("last_temperature_import_path"),
        "last_temperature_calibration_path": payload.get("last_temperature_calibration_path"),
        "last_temperature_reset_temperature": payload.get("last_temperature_reset_temperature"),
        "grayscale_results_headers": grayscale_headers,
        "grayscale_results_rows": grayscale_rows,
        "freeze_results_headers": freeze_headers,
        "freeze_results_rows": freeze_rows,
        "temperature_sync_headers": temperature_sync_headers,
        "temperature_sync_rows": temperature_sync_rows,
        "temperature_sync_summary": dict(payload.get("temperature_sync_summary", {})),
        "tool_mode": payload.get("tool_mode", "cursor"),
        "console_history": payload.get("console_history", ""),
    }


def _rows_to_csv_text(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if headers:
        writer.writerow(headers)
    writer.writerows(rows)
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
    temperature_sync_headers,
    temperature_sync_rows,
):
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(SESSION_STATE_FILENAME, json.dumps(payload, indent=2))
        if grayscale_headers:
            archive.writestr(GRAYSCALE_CSV_FILENAME, _rows_to_csv_text(grayscale_headers, grayscale_rows))
        if freeze_headers:
            archive.writestr(FREEZE_CSV_FILENAME, _rows_to_csv_text(freeze_headers, freeze_rows))
        if temperature_sync_headers:
            archive.writestr(
                TEMPERATURE_SYNC_CSV_FILENAME,
                _rows_to_csv_text(temperature_sync_headers, temperature_sync_rows),
            )


def load_session_bundle(file_path):
    with zipfile.ZipFile(file_path, "r") as archive:
        payload = json.loads(archive.read(SESSION_STATE_FILENAME).decode("utf-8"))
        grayscale_table = ([], [])
        freeze_table = ([], [])
        temperature_sync_table = ([], [])

        if GRAYSCALE_CSV_FILENAME in archive.namelist():
            grayscale_table = _csv_text_to_rows(archive.read(GRAYSCALE_CSV_FILENAME).decode("utf-8"))
        if FREEZE_CSV_FILENAME in archive.namelist():
            freeze_table = _csv_text_to_rows(archive.read(FREEZE_CSV_FILENAME).decode("utf-8"))
        if TEMPERATURE_SYNC_CSV_FILENAME in archive.namelist():
            temperature_sync_table = _csv_text_to_rows(
                archive.read(TEMPERATURE_SYNC_CSV_FILENAME).decode("utf-8")
            )

    return payload, grayscale_table, freeze_table, temperature_sync_table
