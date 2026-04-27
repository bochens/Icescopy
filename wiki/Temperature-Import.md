# Temperature Import

This page describes the temperature import workflows currently supported by Icescopy.

## Supported importers

The current application supports:

- standard two-column temperature CSV
- CSU `.dat`
- TAMU Linkam `.xlsx`

These importers are not interchangeable.
Choose the importer that matches the external data format you actually have.

## When to import temperature

Import temperature data after:

- image order is correct
- cells are annotated
- freeze events have been reviewed or accepted
- sample assignments are correct

Temperature import builds the freeze count timeseries table from current freeze events and current sample grouping.
If sample assignment or freeze events change later, reimport the temperature data.

## Standard temperature CSV import

Use the standard importer when you can prepare a simple CSV with:

- column 1: timestamp
- column 2: temperature

Other columns are ignored.
The temperature column can be Celsius or Kelvin, selected in the dialog.

The dialog has separate sections for image timestamps, the temperature CSV, and water blank correction.

Image timestamps can come from:

- filename
- EXIF
- creation time
- modification time
- generated sequence from first timestamp plus frame interval

Timestamp text can use:

- `YYYY-MM-DD HH:MM:SS`
- `YYYY-MM-DDTHH:MM:SS`
- `YYYY/MM/DD HH:MM:SS`
- `YYYYMMDD_HHMMSS`
- `YYYYMMDD HHMMSS`
- `YYMMDD_HHMMSS`
- `YYMMDD HHMMSS`
- `YYMMDD HHMM`
- `YYMMDD-HHMMSS`
- `YY/MM/DD HH:MM:SS`
- EXIF text such as `YYYY:MM:DD HH:MM:SS`
- explicit Unix epoch seconds or milliseconds

Epoch timestamps are not auto-detected.
Choose the explicit epoch seconds or epoch milliseconds style when using epoch values.
Epoch is interpreted as seconds or milliseconds since `1970-01-01 00:00:00 UTC`, then stored internally as a timezone-free timestamp for matching.

The dialog tests the first image timestamp before import.
If no image timestamp can be resolved, the import cannot proceed.

## CSU import

Use the CSU importer when you have the CSU `.dat` output format.

The CSU workflow supports:

- sample matching
- water blank sample designation
- reset-after-warmed-to cycle splitting

## CSU Water Blank Correction

Water blank correction is applied within a cycle.

In the current logic:

- the imported `.dat` series is treated as cumulative count data
- image-derived anchor points from Icescopy are used to reconcile the cumulative series
- water blank samples contribute a cumulative correction within each cycle

The algorithm defaults to the imported cumulative series when it is consistent, but corrects it when it violates:

- monotonic accumulation
- anchor constraints
- count bounds

## TAMU Linkam import

Use the TAMU importer when you have a TAMU Linkam workbook.

This workflow uses:

- image timestamps parsed from PNG filenames
- time interpolation against the workbook timeseries
- optional calibration CSV by cell ID

## Reset After Warmed To

The reset threshold is used to split repeated cooling-warming cycles.

Use it when:

- the experiment contains repeated cycles
- counts should restart after the timeseries warms back above a chosen threshold

If the threshold is wrong, cycle boundaries will also be wrong.

## Review the output

After import, check:

- sample matching
- temperature alignment
- cycle boundaries
- whether the cumulative count shape makes sense against the image sequence
- whether the number of images inside the temperature timeseries range is nonzero

## Freeze count timeseries CSV output

The exported `freeze_count_timeseries.csv` contains commented metadata preamble rows followed by the data table.
Comment rows start with `#`.

Preamble fields include:

- `format_name`
- `file_version`
- `project_name`
- `user_name`
- `institution`
- `analysis_date`
- `well_volume_uL`
- `reset_temperature_C`

Sample metadata rows include:

- `sample_id`
- `cell_number`
- `sample_name`
- `sample_long_name`
- `sampling_site`
- `collection_start`
- `collection_end`
- `sample_type`
- `dilution`
- `air_volume_L`
- `filter_fraction_used`
- `suspension_volume_mL`
- `dry_mass_g`

The table columns include temperature and count data.
For each sample, Icescopy writes:

- `number total`
- `number frozen`

Icescopy does not export `fraction frozen`.
Downstream tools should calculate fractions themselves if needed.

## Practical warnings

- if image timestamps are wrong, TAMU output will be wrong
- if standard CSV timestamp settings are wrong, interpolation will fail or align to the wrong images
- if sample assignment is wrong, grouped output will be wrong
- if freeze annotations are stale, freeze count timeseries will also be stale
