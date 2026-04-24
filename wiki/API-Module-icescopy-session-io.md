# API Module: `icescopy_session_io`

Session bundle serialization and deserialization helpers.

## Source

- File: `src/icescopy_session_io.py`

## Classes

_None._

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `SESSION_STATE_FILENAME` | 10 | Stores session state filename. |
| `GRAYSCALE_CSV_FILENAME` | 11 | Stores grayscale CSV filename. |
| `FREEZE_CSV_FILENAME` | 12 | Stores freeze CSV filename. |
| `FREEZE_COUNT_TIMESERIES_CSV_FILENAME` | 13 | Stores freeze count timeseries CSV filename. |
| `SAMPLE_CATALOG_FIELD_NAMES` | 14 | Ordered collection of display names for sample catalog field names. |
| `FREEZE_COUNT_TIMESERIES_SAMPLE_METADATA_FIELD_NAMES` | 27 | Ordered collection of display names for freeze count timeseries sample metadata field names. |
| `ALLOWED_SAMPLE_TYPES` | 30 | Stores allowed sample types. |
| `FREEZE_COUNT_TIMESERIES_PREAMBLE_KEYS` | 31 | Stores freeze count timeseries preamble keys. |
| `FREEZE_COUNT_TIMESERIES_METADATA_ROW_LABELS` | 42 | Stores freeze count timeseries metadata row labels. |
| `FREEZE_COUNT_TIMESERIES_FORMAT_NAME` | 43 | Display name for freeze count timeseries format name. |
| `FREEZE_COUNT_TIMESERIES_FILE_VERSION` | 44 | Stores freeze count timeseries file version. |
| `FREEZE_COUNT_TIMESERIES_MISSING_VALUE` | 45 | Stores freeze count timeseries missing value. |
| `CSV_LINE_TERMINATOR` | 46 | Stores CSV line terminator. |
| `SORT_MODE_LABELS` | 47 | Stores sort mode labels. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `normalize_sample_catalog_record(value)` | 57 | Normalizes sample catalog record. |
| `serialize_sample_catalog_payload(catalog)` | 75 | Serializes sample catalog payload. |
| `deserialize_sample_catalog_payload(payload)` | 84 | Deserializes sample catalog payload. |
| `build_freeze_count_timeseries_csv_text(headers, rows, *, session_metadata=None, summary=None)` | 95 | Builds freeze count timeseries CSV text. |
| `cell_circle_to_dict(circle)` | 144 | Serializes cell circle to a dictionary payload. |
| `cell_circle_from_dict(main_window, payload)` | 154 | Rebuilds cell circle from a dictionary payload. |
| `build_session_payload(main_window)` | 171 | Builds session payload. |
| `build_restore_state(main_window, payload, grayscale_table, freeze_table, freeze_count_timeseries_table)` | 215 | Builds restore state. |
| `_rows_to_csv_text(headers, rows)` | 269 | Serializes rows to CSV text. |
| `_create_csv_writer(buffer)` | 278 | Implements create CSV writer. |
| `_csv_row_to_text(row)` | 282 | Implements CSV row to text. |
| `_csv_text_to_rows(text)` | 288 | Converts CSV text into row-oriented data. |
| `save_session_bundle(file_path, payload, grayscale_headers, grayscale_rows, freeze_headers, freeze_rows, freeze_count_timeseries_headers, freeze_count_timeseries_rows)` | 296 | Saves session bundle. |
| `load_session_bundle(file_path)` | 319 | Loads session bundle. |
