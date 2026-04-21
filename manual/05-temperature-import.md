# Import Temperature Data

Use this page to align image-derived freezing results with external temperature data.

Open temperature import from:
- `Analysis -> Import Temperature Data`

## Choose The Correct Importer

Use:
- `CSU IS .dat import...` for CSU data files
- `TAMU Linkam .xlsx import...` for TAMU Linkam workbooks

The core analysis stays frame-based. These importers add time and temperature later.

## Import CSU Data

Use the CSU importer when the external `.dat` file contains the authoritative image-to-time mapping.

1. Open `Analysis -> Import Temperature Data -> CSU IS .dat import...`.
2. Select the CSU `.dat` file.
3. Select any blank samples if blank correction is required.
4. Set `Reset After Warmed To (°C)` if the run contains repeated cooling and warming cycles.
5. Confirm the import.

Current CSU behavior:
- uses the `Picture` column to match images to temperature rows
- matches samples by sample name
- reports unmatched names
- corrects both false negatives and false positives relative to the current image-based freeze results
- allows blank-sample selection for CSU blank correction

Interpretation:
- the CSU `.dat` file is the authoritative time and temperature source
- the app trusts the `.dat` picture-to-row association instead of EXIF time or file modified time
- if a sample name does not match, that sample is reported instead of silently guessed

## Import TAMU Data

Use the TAMU importer when image timestamps are encoded in filenames and temperature comes from a Linkam workbook.

1. Open `Analysis -> Import Temperature Data -> TAMU Linkam .xlsx import...`.
2. Select the workbook.
3. Optionally select the calibration CSV.
4. Set `Reset After Warmed To (°C)` if the run contains repeated cooling and warming cycles.
5. Confirm the import.

Current TAMU behavior:
- reads image time from the PNG filename
- interpolates temperature from the Linkam temperature trace
- optionally applies well-level calibration by cell ID
- if no sample setup exists, all cells are treated as one output group
- builds frozen counts from Icescopy freeze results

Interpretation:
- the workbook provides the temperature trace
- the image filename provides the timestamp anchor for each frame
- temperature is interpolated onto the image times before the output table is built

## Use Reset After Warmed To

Use `Reset After Warmed To (°C)` when the experiment contains repeated cooling and warming cycles.

Meaning:
- once temperature warms back to the selected threshold, the next cooling segment is treated as a new cycle
- counts are interpreted within each cycle instead of across the entire run
- crossing the threshold counts; the trace does not need to hit the exact value

The cycle detector also uses the analysis preference `Cycle Warm-Up Hysteresis (°C)` to ignore tiny threshold jitter.

Choose this threshold deliberately:
- set it high enough that a genuine warm-up must occur before a new cycle starts
- do not set it so low that tiny oscillations near the threshold create false cycle boundaries

## Understand Blank Correction

Blank correction applies only to the CSU workflow.

Use it when selected samples should act as blanks.

No blank-correction path is used for TAMU.

Current blank-correction rule:
- if a selected blank freezes at a CSU row, that blank event contributes to the CSU blank-correction logic from that point onward

## Review The Output

After import, review the `Temperature Sync` tab.

Typical columns include:
- `timestamp`
- `temperature_C`
- `cycle`
- `image_name` or `picture`
- optional corrected temperature columns
- per-sample frozen counts

Use this table for downstream work such as:
- frozen count versus time
- frozen count versus temperature
- cycle-by-cycle interpretation for repeated freeze-thaw experiments

## Interpret Repeated Cycles

For repeated freeze-thaw runs:
- use the `cycle` column
- compute within-cycle quantities first
- combine cycles later in downstream analysis if needed

Do not treat all cycles as one monotonic run unless that is physically valid for the experiment.
