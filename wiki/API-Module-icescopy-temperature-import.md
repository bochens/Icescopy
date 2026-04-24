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
| `StandardTemperatureTimeseries` | Standard Temperature Timeseries class. | [StandardTemperatureTimeseries](API-Class-StandardTemperatureTimeseries) |
| `ResolvedImageTimestamps` | Resolved Image Timestamps class. | [ResolvedImageTimestamps](API-Class-ResolvedImageTimestamps) |

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `CSU_IS_TIMESTAMP_RE` | 15 | Stores csu is timestamp re. |
| `TAMU_IMAGE_TIMESTAMP_RE` | 16 | Stores tamu image timestamp re. |
| `TAMU_LDF_TIMESTAMP_RE` | 21 | Stores tamu ldf timestamp re. |
| `GENERIC_FILENAME_TIMESTAMP_RE` | 25 | Stores generic filename timestamp re. |
| `COMPACT_FILENAME_TIMESTAMP_RE` | 30 | Stores compact filename timestamp re. |
| `XLSX_NS` | 34 | Stores xlsx ns. |
| `COMMON_DATETIME_FORMATS` | 38 | Stores common datetime formats. |
| `YEAR4_DASH_DATETIME_FORMATS` | 52 | Stores year4 dash datetime formats. |
| `YEAR4_T_DATETIME_FORMATS` | 57 | Stores year4 t datetime formats. |
| `YEAR4_SLASH_DATETIME_FORMATS` | 62 | Stores year4 slash datetime formats. |
| `YEAR4_COMPACT_DATETIME_FORMATS` | 67 | Stores year4 compact datetime formats. |
| `YEAR2_COMPACT_DATETIME_FORMATS` | 73 | Stores year2 compact datetime formats. |
| `YEAR2_SLASH_DATETIME_FORMATS` | 85 | Stores year2 slash datetime formats. |
| `SLASH_DAY_MONTH_DATETIME_FORMATS` | 90 | Stores slash day month datetime formats. |
| `EXIF_DATETIME_FORMATS` | 104 | Stores exif datetime formats. |
| `INLINE_EXIF_TIMESTAMP_RE` | 108 | Stores inline exif timestamp re. |
| `EPOCH_TIMESTAMP_RE` | 111 | Stores epoch timestamp re. |
| `TIMESTAMP_STYLE_AUTO` | 113 | Stores timestamp style auto. |
| `TIMESTAMP_STYLE_COMMON` | 114 | Stores timestamp style common. |
| `TIMESTAMP_STYLE_YEAR4_DASH` | 115 | Stores timestamp style year4 dash. |
| `TIMESTAMP_STYLE_YEAR4_T` | 116 | Stores timestamp style year4 t. |
| `TIMESTAMP_STYLE_YEAR4_SLASH` | 117 | Stores timestamp style year4 slash. |
| `TIMESTAMP_STYLE_YEAR4_COMPACT` | 118 | Stores timestamp style year4 compact. |
| `TIMESTAMP_STYLE_YEAR2_COMPACT` | 119 | Stores timestamp style year2 compact. |
| `TIMESTAMP_STYLE_YEAR2_SLASH` | 120 | Stores timestamp style year2 slash. |
| `TIMESTAMP_STYLE_EXIF` | 121 | Stores timestamp style exif. |
| `TIMESTAMP_STYLE_EPOCH_SECONDS` | 122 | Stores timestamp style epoch seconds. |
| `TIMESTAMP_STYLE_EPOCH_MILLISECONDS` | 123 | Stores timestamp style epoch milliseconds. |
| `IMAGE_TIMESTAMP_SOURCE_FILENAME` | 125 | Stores image timestamp source filename. |
| `IMAGE_TIMESTAMP_SOURCE_EXIF` | 126 | Stores image timestamp source exif. |
| `IMAGE_TIMESTAMP_SOURCE_CREATED` | 127 | Stores image timestamp source created. |
| `IMAGE_TIMESTAMP_SOURCE_MODIFIED` | 128 | Stores image timestamp source modified. |
| `IMAGE_TIMESTAMP_SOURCE_GENERATED` | 129 | Stores image timestamp source generated. |
| `TEMPERATURE_UNIT_CELSIUS` | 131 | Stores temperature unit celsius. |
| `TEMPERATURE_UNIT_KELVIN` | 132 | Stores temperature unit kelvin. |
| `TIMESTAMP_STYLE_CHOICES` | 134 | Stores timestamp style choices. |
| `IMAGE_TIMESTAMP_SOURCE_CHOICES` | 147 | Stores image timestamp source choices. |
| `TEMPERATURE_UNIT_CHOICES` | 155 | Stores temperature unit choices. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `normalize_sample_name(value)` | 202 | Normalizes sample name. |
| `_parse_csu_is_timestamp(date_text, time_text)` | 206 | Implements parse csu is timestamp. |
| `_safe_int(value, default=0)` | 223 | Implements safe int. |
| `_safe_float(value)` | 232 | Implements safe float. |
| `_normalize_parsed_datetime(value)` | 239 | Implements normalize parsed datetime. |
| `_parse_datetime_with_formats(text, formats)` | 247 | Implements parse datetime with formats. |
| `parse_flexible_datetime_text(text)` | 256 | Parses flexible datetime text. |
| `parse_exif_datetime_text(text)` | 286 | Parses exif datetime text. |
| `parse_year4_dash_datetime_text(text)` | 293 | Parses year4 dash datetime text. |
| `parse_year4_t_datetime_text(text)` | 300 | Parses year4 t datetime text. |
| `parse_year4_slash_datetime_text(text)` | 307 | Parses year4 slash datetime text. |
| `parse_year4_compact_datetime_text(text)` | 314 | Parses year4 compact datetime text. |
| `parse_year2_compact_datetime_text(text)` | 321 | Parses year2 compact datetime text. |
| `parse_year2_slash_datetime_text(text)` | 328 | Parses year2 slash datetime text. |
| `parse_epoch_datetime_text(text, unit='auto')` | 335 | Parses epoch datetime text. |
| `parse_timestamp_text(text, style=TIMESTAMP_STYLE_AUTO)` | 364 | Parses timestamp text. |
| `_datetime_from_filename_match(match)` | 406 | Implements datetime from filename match. |
| `_parse_timestamp_candidates(candidates, style)` | 425 | Implements parse timestamp candidates. |
| `_extract_filename_timestamp_candidates(stem)` | 433 | Implements extract filename timestamp candidates. |
| `parse_generic_image_timestamp(image_name, timestamp_style=TIMESTAMP_STYLE_AUTO)` | 461 | Parses generic image timestamp. |
| `read_exif_timestamp_text(file_path)` | 469 | Reads exif timestamp text. |
| `resolve_image_timestamp(file_path, image_name, source=IMAGE_TIMESTAMP_SOURCE_FILENAME, timestamp_style=TIMESTAMP_STYLE_AUTO, generated_start_text='', frame_interval_seconds=None, image_index=0)` | 484 | Implements resolve image timestamp. |
| `resolve_image_timestamps(image_paths, image_names, source=IMAGE_TIMESTAMP_SOURCE_FILENAME, timestamp_style=TIMESTAMP_STYLE_AUTO, generated_start_text='', frame_interval_seconds=None)` | 532 | Implements resolve image timestamps. |
| `parse_standard_temperature_csv(file_path, timestamp_style=TIMESTAMP_STYLE_AUTO, temperature_unit=TEMPERATURE_UNIT_CELSIUS)` | 566 | Parses standard temperature CSV. |
| `compute_blank_correction_by_index(blank_sample_keys, corrected_counts_by_sample, total_count)` | 630 | Computes water blank correction by index. |
| `apply_blank_correction(total_cells, frozen_count, blank_correction)` | 649 | Applies water blank correction. |
| `parse_tamu_image_timestamp(image_name)` | 665 | Parses tamu image timestamp. |
| `_read_xlsx_shared_strings(archive)` | 682 | Implements read xlsx shared strings. |
| `_resolve_first_sheet_path(archive)` | 692 | Implements resolve first sheet path. |
| `_read_first_sheet_rows(file_path)` | 711 | Implements read first sheet rows. |
| `_parse_tamu_ldf_timestamp(text)` | 742 | Implements parse tamu ldf timestamp. |
| `_parse_recorded_timestamp(text)` | 758 | Implements parse recorded timestamp. |
| `parse_tamu_linkam_xlsx(file_path)` | 772 | Parses tamu linkam xlsx. |
| `parse_ice_array_calibration_csv(file_path)` | 842 | Parses ice array calibration CSV. |
| `parse_csu_is_dat(file_path)` | 865 | Parses csu is dat. |
| `reconcile_cumulative_counts(raw_counts, anchor_counts, maximum_count)` | 935 | Implements reconcile cumulative counts. |
| `normalize_temperature_reset_threshold(reset_temperature)` | 988 | Normalizes temperature reset threshold. |
| `detect_cycle_start_indexes_from_temperatures(temperatures, reset_temperature, warmup_hysteresis_c=0.02)` | 997 | Detects cycle start indexes from temperatures. |
| `build_cycle_ids_from_start_indexes(total_count, cycle_start_indexes)` | 1044 | Builds cycle ids from start indexes. |
| `reconcile_counts_by_cycle(raw_counts, anchor_counts, maximum_count, cycle_ids)` | 1069 | Implements reconcile counts by cycle. |
