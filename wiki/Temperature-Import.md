# Temperature Import

Temperature import combines the current freeze events, sample assignments, and a temperature record to build **Freeze Count Timeseries**. It does not run freeze detection.

First check frame order, review the freeze events, and assign cells to samples. Then choose **Analysis → Import Temperature Data**. Reimport after changing freeze events or sample assignments, or after running analysis again.

## Choose the importer

| Menu item | Input | Image files | Video | Matching method |
|---|---|---|---|---|
| Standard CSV import | Timestamp and temperature in the first two columns | Yes | Yes | Image timestamps or a first timestamp plus video time/fixed interval |
| CSU IS .dat import | CSU instrument `.dat` file | Yes | No | Picture names and sample columns |
| TAMU Linkam .xlsx import | TAMU Linkam workbook | Yes | No | PNG filename timestamps matched to the workbook temperature record |
| PKU Linksys32 .iml import | Linksys32 file with embedded image records | Yes | No | Loaded image order matched to the embedded image-record order |
| UTK CSV import | CSV with `Time` and `PV(C)1` columns | Yes | Yes | Image filename timestamps, or a video filename start time plus video time |

Use the importer for the file's actual format. A `.csv` extension alone does not identify the format. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) for image and video loading.

## Standard temperature CSV

Prepare a CSV with timestamp in column 1 and temperature in column 2. An optional header can occupy the first row; additional columns are ignored. For example:

```csv
timestamp,temperature_C
2026-01-01T12:00:00.000,-5.0
2026-01-01T12:00:01.000,-5.1
```

Use at least two temperature rows and avoid duplicate timestamps. If a source manifest contains other columns before timestamp and temperature, copy the two required columns into a new CSV in this order.

1. Choose **Standard CSV import** and select the file.
2. Choose how Icescopy obtains the image or video frame timestamps, as described below.
3. Set the temperature timestamp style. Clear **Use image style for temperature timestamps** if the two sources use different formats.
4. Choose **Celsius** or **Kelvin**. Imported output temperatures are in degrees Celsius.
5. Select any water blank samples and, for repeated cooling cycles, the reset threshold.
6. Import and review the reported numbers of parsed and in-range frames.

### Image timestamp sources

For image sequences, **Source** can read the filename, EXIF (camera metadata stored inside the image), file creation time, or file modification time. It can also generate times from **First timestamp** and **Frame interval (s)**. File creation and modification times are useful only when they represent acquisition times; copying files can change them.

The dialog previews the first image's resolved timestamp. Check it against the experiment clock. With generated times, confirm the image order and interval before importing.

### Video timestamp sources

For video, enter **First timestamp** and choose:

- **First timestamp + video time** to add the source's elapsed video time to that timestamp.
- **First timestamp + fixed interval** to assign equally spaced times using **Frame interval (s)**.

Check the start and end against the temperature record. For multiple clips, confirm the clip order before importing. The selected timing method determines the alignment; these options do not establish that the camera and temperature logger clocks agree.

### Timestamp styles

**Auto** recognizes common year-first formats, including `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DDTHH:MM:SS`, and `YYYY/MM/DD HH:MM:SS`, with supported fractional-second variants. Explicit choices also cover compact four- or two-digit-year formats and EXIF date text such as `YYYY:MM:DD HH:MM:SS`.

For Unix epoch values, select **epoch seconds** or **epoch milliseconds** explicitly; Auto does not detect them. These are elapsed seconds or milliseconds since `1970-01-01 00:00:00 UTC`. Use a consistent clock convention for the image/video start time and temperature file.

## CSU IS .dat

1. Load the corresponding image sequence and keep its picture names.
2. Ensure sample names match the `.dat` sample columns, such as `Sample_0`.
3. Choose **CSU IS .dat import**, select the file, and identify any water blank samples.
4. Set **Reset After Warmed To (°C)** if the experiment contains repeated cooling cycles.
5. Review matched pictures and samples, including any unmatched columns or app samples.

The importer expects a tab-separated CSU file with `Avg_Temp`, `Picture`, and `Sample_...` columns. It uses the current image-derived freeze events to reconcile the instrument's cumulative counts: the number frozen so far within each cycle. Its output follows the instrument temperature rows, so the output row count can exceed the number of images.

## TAMU Linkam .xlsx

Load the PNG sequence, then select **TAMU Linkam .xlsx import** and the matching workbook. Icescopy reads image timestamps from the PNG filenames and interpolates temperatures between workbook readings. A generic spreadsheet with temperature columns is not necessarily a Linkam workbook.

An optional calibration CSV must have `well`, `slope`, and `intercept` headers. Here, `well` is the Icescopy cell ID. The correction is `(measured temperature − intercept) / slope`; the slope must be nonzero. When calibration is supplied, the output includes the group's mean corrected temperature for cells with usable calibration entries. Review the reported calibrated-cell count.

Select blank samples and a cycle reset threshold as needed, then check timestamp matching and the temperature range in the import summary.

## PKU Linksys32 .iml

Load the image sequence, then choose **PKU Linksys32 .iml import** and its matching `.iml` file. The number of loaded images must equal the number of embedded image records, and their order must agree.

This importer uses timestamps and tagged temperatures from the embedded image records. It uses the continuous temperature record to identify cycle boundaries. It does not obtain PKU timestamps or temperatures from image filenames or EXIF metadata.

If only exported images and a timestamp/temperature manifest are available, prepare a new two-column CSV from the manifest and use the **Standard CSV** workflow instead.

## UTK CSV

Choose **UTK CSV import** for a file with the exact column names `Time` and `PV(C)1`. Temperature is read in degrees Celsius. The `Time` column accepts forms such as `2026-01-01/12:00:00:123` or `2026-01-01 12:00:00`, with at least two rows and no duplicate timestamps.

- **Images:** timestamps are read from filenames using automatic format recognition.
- **Video:** the start timestamp is read from the first clip's filename, for example `2026_0101_120000_001.MP4`. Icescopy adds the source's elapsed video time. Confirm the first clip and clip order before import.

The UTK dialog also supports water blank selection and cycle reset. If the video filename lacks a recognized start time, use the Standard CSV workflow with a prepared two-column temperature file and an explicitly entered first timestamp.

## Water blanks and repeated cycles

A water blank is a control sample used to account for freezing in the water or handling process. When blank groups are selected, their frozen counts and total counts are subtracted from each non-blank output group within the cycle. Review the selected groups and resulting denominators; blank selection changes both counts.

**Reset After Warmed To (°C)** starts a new cycle when the temperature warms back to the chosen threshold. Leave it **Off** for a single cycle. Within a cycle, a cell is counted after its first freeze event. Choose the threshold from the experiment's warming stage and check the resulting cycle boundaries.

## Review and export

Before exporting, check:

- The expected sample groups and cell totals, including any separate **Unassigned cells** group.
- The number of matched or in-range frames and any unmatched samples.
- The first and last timestamps, temperature range, and cycle boundaries.
- Several known freeze frames against their assigned temperatures.

Use **File → Output Results** and select **Freeze Count Timeseries CSV**. The file has metadata comment lines beginning with `#`, followed by the data table. The metadata includes session details, sample IDs and cell counts, and sample fields selected for export in Preferences. Missing values are written as `nan`; do not treat them as measured zeroes.

Each sample has **number total** and **number frozen** columns. Current exports do not include **fraction frozen**; downstream software can calculate it from these counts when the total is valid and nonzero. The count table alone is not an ice-nucleating-particle concentration calculation.

Save the session to retain the imported table and its settings. See [Analysis and Results](Analysis-and-Results.md) for reviewing detections and exporting the other result tables.
