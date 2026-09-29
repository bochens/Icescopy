# Temperature Import

Temperature import matches reviewed freeze events to temperatures and counts frozen cells for each sample. The result appears in **Freeze Count Timeseries**.

First check frame order, review freeze events, and assign cells to samples. Then choose **Analysis → Import Temperature Data**. Import does not run freeze detection. Reimport after changing freeze events or sample assignments, or after rerunning analysis.

## Choose the importer

| Menu item | Input | Image files | Video | Matching method |
|---|---|---|---|---|
| Standard CSV import | Timestamp and temperature in the first two columns | Yes | Yes | Image timestamps or a first timestamp plus video time/fixed interval |
| CSU IS .dat import | CSU instrument `.dat` file | Yes | No | Picture names and sample columns |
| TAMU Linkam .xlsx import | TAMU Linkam workbook | Yes | No | PNG filename timestamps matched to the workbook temperature record |
| PKU Linksys32 .iml import | Linksys32 file with embedded image records | Yes | No | Loaded image order matched to the embedded image-record order |
| UTK CSV import | CSV with `Time` and `PV(C)1` columns | Yes | Yes | Image filename timestamps, or a video filename start time plus video time |

Choose the importer that matches your file's format, not just its extension. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) to load images or video first.

## Standard temperature CSV

Put timestamps in column 1 and temperatures in column 2. The first row may contain column names; extra columns are ignored. For example:

```csv
timestamp,temperature_C
2026-01-01T12:00:00.000,-5.0
2026-01-01T12:00:01.000,-5.1
```

Include at least two temperature rows with no duplicate timestamps. If your file uses a different column order, copy the two required columns into a new CSV.

1. Choose **Standard CSV import** and select the file.
2. Choose the image or video timestamp source described below.
3. Set the temperature timestamp style. Clear **Use image style for temperature timestamps** if the two sources use different formats.
4. Choose **Celsius** or **Kelvin** to match the file. Output temperatures use degrees Celsius.
5. Select any water blank samples and a reset threshold for repeated cooling cycles (see below).
6. Import. Check how many frame timestamps were read and how many fall within the temperature record.

### Image timestamp sources

For images, **Source** can read timestamps from filenames, EXIF (camera information stored in the image), or file creation or modification times. It can also calculate times from **First timestamp** and **Frame interval (s)**. Use file creation or modification times only if they record when the images were taken; copying files can change them.

Check the first image's timestamp in the preview against the experiment clock. When calculating times from an interval, check the image order and interval too.

### Video timestamp sources

For video, enter **First timestamp** and choose:

- **First timestamp + video time** to add the source's elapsed video time to that timestamp.
- **First timestamp + fixed interval** to assign equally spaced times using **Frame interval (s)**.

Check the start and end against the temperature record. For multiple clips, check their order too. Also check whether the camera and temperature logger clocks agree; a successful import does not confirm this.

### Timestamp styles

**Auto** recognizes common year-first formats, including `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DDTHH:MM:SS`, and `YYYY/MM/DD HH:MM:SS`, with supported fractional seconds. You can also select compact formats with four- or two-digit years, or EXIF dates such as `YYYY:MM:DD HH:MM:SS`.

For Unix epoch values (time since `1970-01-01 00:00:00 UTC`), select **epoch seconds** or **epoch milliseconds**; Auto does not detect them. Use the same time zone and clock convention for the frames and temperature file.

## CSU IS .dat

1. Load the corresponding image sequence and keep its picture names.
2. Ensure sample names match the `.dat` sample columns, such as `Sample_0`.
3. Choose **CSU IS .dat import**, select the file, and identify any water blank samples.
4. Set **Reset After Warmed To (°C)** if the experiment contains repeated cooling cycles.
5. Check the matched pictures and samples, and investigate any unmatched entries.

The file must be tab-separated and contain `Avg_Temp`, `Picture`, and `Sample_...` columns. The importer combines the instrument counts with the current image-derived freeze events to track the number frozen within each cycle. Output follows the instrument's temperature rows and may have more rows than the image sequence.

## TAMU Linkam .xlsx

Load the PNG sequence, then choose **TAMU Linkam .xlsx import** and the matching Linkam workbook. Icescopy reads timestamps from PNG filenames and estimates temperatures between workbook readings. This importer requires the Linkam workbook layout.

To apply cell calibration, supply a CSV with `well`, `slope`, and `intercept` headers. Use the Icescopy cell ID for `well`. The corrected temperature is `(measured temperature − intercept) / slope`; the slope must be nonzero. Output includes each group's mean corrected temperature for cells with usable calibration entries. Check the reported number of calibrated cells.

Select any blank samples and cycle reset threshold, then check timestamp matches and the temperature range in the import summary.

## PKU Linksys32 .iml

Load the image sequence, then choose **PKU Linksys32 .iml import** and its matching `.iml` file. The number of loaded images must equal the number of embedded image records, and their order must agree.

Timestamps and temperatures come from the embedded image records, not image filenames or EXIF. The continuous temperature record identifies cycle boundaries.

If you have images and a separate timestamp/temperature list but no `.iml`, prepare a two-column CSV and use **Standard CSV import**.

## UTK CSV

Choose **UTK CSV import** for a file with columns named exactly `Time` and `PV(C)1`. Temperatures must be in degrees Celsius. The `Time` column accepts formats such as `2026-01-01/12:00:00:123` or `2026-01-01 12:00:00`. Include at least two rows with no duplicate timestamps.

- **Images:** timestamps are read from filenames using automatic format recognition.
- **Video:** Icescopy reads the start time from the first clip's filename, such as `2026_0101_120000_001.MP4`, then adds elapsed video time. Check the clip order before importing.

Select any water blanks and cycle reset threshold in the dialog. If the video filename has no recognized start time, prepare a two-column temperature CSV and use **Standard CSV import**, entering the first timestamp yourself.

## Water blanks and repeated cycles

A water blank is a control sample used to account for freezing caused by the water or handling. When you select blank groups, their frozen and total counts are subtracted from each non-blank output group within the cycle. Check both corrected counts before using them.

For repeated cooling cycles, set **Reset After Warmed To (°C)** to a temperature reached during warming. Counts restart when the temperature warms back to that threshold. Check the resulting cycle boundaries. Leave this setting **Off** for a single cycle. A cell is counted once per cycle, after its first freeze event.

## Review and export

Before exporting, check:

- Sample groups and cell totals, including any **Unassigned cells** group.
- Matched or in-range frames and any unmatched samples.
- The first and last timestamps, temperature range, and cycle boundaries.
- Several known freeze frames against their assigned temperatures.

Choose **File → Output Results**, then select **Freeze Count Timeseries CSV**. Rows beginning with `#` contain session details, sample IDs, cell counts, and sample fields enabled for export. The data table follows them. Missing values are written as `nan`; they are not measured zeroes.

Each sample has **number total** and **number frozen** columns. To calculate fraction frozen, divide number frozen by a valid, nonzero number total. Icescopy does not calculate ice-nucleating-particle concentrations from these counts.

Save the session to retain the imported table and settings. See [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for the other export tables.
