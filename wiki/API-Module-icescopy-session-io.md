# API Module: `icescopy_session_io`

Session bundle serialization and deserialization helpers.

## Source

- File: `src/icescopy_session_io.py`

## Classes

_None._

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `SESSION_SCHEMA_VERSION` | 9 | Stores session schema version. |
| `SESSION_STATE_FILENAME` | 10 | Stores session state filename. |
| `GRAYSCALE_CSV_FILENAME` | 11 | Stores grayscale CSV filename. |
| `FREEZE_CSV_FILENAME` | 12 | Stores freeze CSV filename. |
| `TEMPERATURE_SYNC_CSV_FILENAME` | 13 | Stores freeze count timeseries CSV filename. |
| `SORT_MODE_LABELS` | 14 | Stores sort mode labels. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `cell_circle_to_dict(circle)` | 24 | Serializes cell circle to a dictionary payload. |
| `cell_circle_from_dict(main_window, payload)` | 34 | Rebuilds cell circle from a dictionary payload. |
| `build_session_payload(main_window)` | 51 | Builds session payload. |
| `build_restore_state(main_window, payload, grayscale_table, freeze_table, freeze_count_timeseries_table)` | 88 | Builds restore state. |
| `_rows_to_csv_text(headers, rows)` | 134 | Serializes rows to CSV text. |
| `_csv_text_to_rows(text)` | 143 | Converts CSV text into row-oriented data. |
| `save_session_bundle(file_path, payload, grayscale_headers, grayscale_rows, freeze_headers, freeze_rows, freeze_count_timeseries_headers, freeze_count_timeseries_rows)` | 151 | Saves session bundle. |
| `load_session_bundle(file_path)` | 174 | Loads session bundle. |
