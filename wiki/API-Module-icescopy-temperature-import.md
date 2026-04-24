# API Module: `icescopy_temperature_import`

Temperature import, parsing, reconciliation, and cycle-detection helpers.

## Source

- File: `src/icescopy_temperature_import.py`

## Classes

| Class | Purpose | Page |
| --- | --- | --- |
| `TemperatureImportError` | Temperature Import Error class. | [TemperatureImportError](API-Class-TemperatureImportError) |
| `CSUISDatRow` | CSUISDat Row class. | [CSUISDatRow](API-Class-CSUISDatRow) |
| `TAMULinkamTimeseries` | TAMULinkam Timeseries class. | [TAMULinkamTimeseries](API-Class-TAMULinkamTimeseries) |

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `CSU_IS_TIMESTAMP_RE` | 13 | Stores csu is timestamp re. |
| `TAMU_IMAGE_TIMESTAMP_RE` | 14 | Stores tamu image timestamp re. |
| `TAMU_LDF_TIMESTAMP_RE` | 19 | Stores tamu ldf timestamp re. |
| `XLSX_NS` | 23 | Stores xlsx ns. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `normalize_sample_name(value)` | 54 | Normalizes sample name. |
| `_parse_csu_is_timestamp(date_text, time_text)` | 58 | Implements parse csu is timestamp. |
| `_safe_int(value, default=0)` | 75 | Implements safe int. |
| `_safe_float(value)` | 84 | Implements safe float. |
| `parse_tamu_image_timestamp(image_name)` | 91 | Parses tamu image timestamp. |
| `_read_xlsx_shared_strings(archive)` | 108 | Implements read xlsx shared strings. |
| `_resolve_first_sheet_path(archive)` | 118 | Implements resolve first sheet path. |
| `_read_first_sheet_rows(file_path)` | 137 | Implements read first sheet rows. |
| `_parse_tamu_ldf_timestamp(text)` | 168 | Implements parse tamu ldf timestamp. |
| `_parse_recorded_timestamp(text)` | 184 | Implements parse recorded timestamp. |
| `parse_tamu_linkam_xlsx(file_path)` | 198 | Parses tamu linkam xlsx. |
| `parse_ice_array_calibration_csv(file_path)` | 268 | Parses ice array calibration CSV. |
| `parse_csu_is_dat(file_path)` | 291 | Parses csu is dat. |
| `reconcile_cumulative_counts(raw_counts, anchor_counts, maximum_count)` | 361 | Implements reconcile cumulative counts. |
| `normalize_temperature_reset_threshold(reset_temperature)` | 414 | Normalizes temperature reset threshold. |
| `detect_cycle_start_indexes_from_temperatures(temperatures, reset_temperature, warmup_hysteresis_c=0.02)` | 423 | Detects cycle start indexes from temperatures. |
| `build_cycle_ids_from_start_indexes(total_count, cycle_start_indexes)` | 470 | Builds cycle ids from start indexes. |
| `reconcile_counts_by_cycle(raw_counts, anchor_counts, maximum_count, cycle_ids)` | 495 | Implements reconcile counts by cycle. |
