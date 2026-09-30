# Temperature Import

Temperature import matches the current freeze events to a temperature record and builds **Freeze Count Timeseries**: the number of cells and the number frozen in each sample over time. CSU imports can also use counts already recorded by the instrument. Importing does not run freeze detection or calculate particle concentrations.

Review frame order, cell placement, freeze events, and sample assignments first. Then choose **Analysis → Import Temperature Data**. Reimport after changing events or sample assignments, or after rerunning analysis.

Use the sections below to [choose an importer](#choose-the-importer), [prepare a standard CSV](#standard-temperature-csv), [handle blanks and cycles](#water-blanks-and-repeated-cycles), and [check the result](#review-and-export). [Output Reference](Output-Reference.md) describes the emitted columns.

## Choose the importer

Choose by the file's actual format, not just its extension. Load the images or video separately before importing temperatures.

| Menu item | Temperature input | Images | Video | How frames are matched |
| --- | --- | --- | --- | --- |
| **Standard CSV import...** | Timestamp and temperature in the first two columns | Yes | Yes | Chosen image timestamp source, or a video start time plus elapsed time/fixed interval. |
| **CSU .dat import...** | CSU IS or cold-stage records | Yes | No | `Picture` filenames give exact record times and temperatures. |
| **TAMU Linkam .xlsx import...** | Linkam workbook with its metadata and table layout | Yes | No | Image filename timestamps relative to the workbook's start time. |
| **PKU Linksys32 .iml import...** | Original Linksys32 file with image records | Yes | No | Loaded images matched by count and order to embedded image records. |
| **UTK CSV import...** | Columns named `Time` and `PV(C)1` | Yes | Yes | Image filename timestamps, or the first video filename's start time plus elapsed video time. |

The dialog can select water blank samples and a reset temperature for repeated cooling cycles. TAMU also offers an optional cell-calibration file. The detailed examples below use invented names and values.

## Before importing

1. For image-derived counts, finish automatic detection and manual corrections. Importing uses the current event list, including manual events outside analysis intervals. CSU recorded counts do not require image freeze detection.
2. Assign cells to samples and give each sample a nonempty name. Use distinct names for easier checking; CSU matching requires names it can distinguish.
3. Check recording order. Sorting the temperature record does not fix an incorrectly ordered image sequence.
4. Confirm that the frame clock and temperature logger use the same time basis. A successful import does not prove that the clocks agree.
5. Save the session under a new name if you want to compare imports or retain an earlier result.

## Standard temperature CSV

### Prepare the file

Use a comma-separated text file with timestamp in column 1 and temperature in column 2:

```csv
timestamp,temperature_C
2026-01-01T12:00:00.000,-5.0
2026-01-01T12:00:02.000,-5.2
2026-01-01T12:00:04.000,-5.4
```

- The first row may contain column names. Put it on the first line; this importer does not treat arbitrary comment lines as headers.
- Include at least two data rows, with no repeated timestamps. Rows are sorted by timestamp during import.
- Additional columns are ignored. If your timestamp and temperature are elsewhere, prepare a new two-column file and preserve the source file.
- Provide finite numeric temperatures and choose the correct unit in the dialog. Column names do not determine the unit.
- Use plain CSV, not an Excel workbook renamed `.csv`.

### Set the import options

1. Choose **Standard CSV import...** and select the file.
2. Choose how the app obtains frame timestamps using the sections below.
3. Set the temperature **Timestamp style**. Clear **Use image style for temperature timestamps** if the frame and temperature formats differ.
4. Select **Celsius** or **Kelvin**. Kelvin values are converted by subtracting 273.15; output temperatures are in °C.
5. Select any water blank samples and set **Reset After Warmed To (°C)**, or leave it **Off** for a single cycle.
6. Import and check the summary: parsed frames, frames within the temperature range, unmatched frames, samples, and cycle count.

Temperature at a frame is found by linear interpolation between neighboring temperature readings. In the example above, a frame at 12:00:01 has temperature −5.1 °C. The app does not extrapolate beyond the first or last reading. At least one frame must fall inside the temperature record; otherwise the import fails.

### Image timestamp sources

| **Source** option | Where the time comes from | What to check |
| --- | --- | --- |
| **Filename** | Timestamp text in each image filename. | Check the first-frame preview and images across the sequence. A sequence number alone is not a timestamp. |
| **EXIF** | Camera date/time information stored inside the image. | Confirm that the images contain it and that the camera clock was set correctly. |
| **Creation time** | The filesystem's birth time, where the platform provides it. | Availability varies by platform; copied files may have new dates. |
| **Modification time** | The file's modification date. | Use only if it records acquisition time, not a copy or edit. |
| **Generated from first timestamp** | First timestamp plus frame index × interval. | Enter the time of frame 0 and a positive **Frame interval (s)**; confirm that acquisition was evenly spaced. |

For a generated sequence starting at 12:00:00 with a 2-second interval, frames 0, 1, and 2 are assigned 12:00:00, 12:00:02, and 12:00:04. Missing or extra images change this alignment unless accounted for in the sequence.

### Video timestamp sources

Enter **First timestamp** for the first frame of the loaded video sequence, then choose:

- **First timestamp + video time:** adds the source's elapsed video timeline.
- **First timestamp + fixed interval:** adds frame index × **Frame interval (s)**.

The elapsed timeline may use timing derived from video/container or frame-rate metadata. Do not assume exact camera timestamps or guaranteed variable-frame-rate accuracy. Check recognizable frames near the beginning and end against the temperature record.

Multiple clips are joined end-to-end. Their timeline does not recover real pauses between clips from each clip's filename. Check clip order and continuity; separate sessions are appropriate when clips need separate wall-clock start times.

### Timestamp styles

| Style | Example | Notes |
| --- | --- | --- |
| Year-first date and time | `2026-01-01 12:00:00.123456` | Space-separated, `T`-separated, and slash-separated year-first styles are available. |
| Compact four-digit year | `20260101_120000` | Select the matching compact style if automatic recognition is unsuitable. |
| Compact two-digit year | `260101_120000` | Check the preview to avoid a mistaken year or missing seconds. |
| EXIF text | `2026:01:01 12:00:00` | Used for camera date/time text. |
| Unix epoch seconds | A 10-digit integer | Select explicitly; Auto does not recognize numeric epoch values. |
| Unix epoch milliseconds | A 13-digit integer | Select explicitly. These are milliseconds since 1970-01-01 00:00:00 UTC. |

The parser expects date/time text without a time-zone suffix. Convert time-zone-aware records, such as values ending in `Z` or `+00:00`, to a consistent clock basis before preparing the import CSV. Epoch values are interpreted in UTC. Ordinary date text carries no time-zone information, and filesystem times use the computer's local time, so do not mix these without checking the conversion.

Ambiguous day/month slash dates can be rejected. Year-first text avoids that ambiguity. Preview recognition does not check camera/logger clock offsets or drift over the experiment.

## CSU .dat

### Required records and matching

Use the original tab-separated CSU IS or cold-stage export. It must contain `Picture` and either `Avg_Temp` or `Sample_Temp`. The first two columns supply date and time, even if the second header is blank. `Sample_...` count columns are optional when using Icescopy detections. A simplified cold-stage layout is:

```text
Time<TAB><TAB>Sample_Temp<TAB>Sample_0<TAB>Picture
01/01/26<TAB>12:00:00:.25<TAB>-5.0<TAB>0<TAB>Image_0.png
01/01/26<TAB>12:00:10:.75<TAB>-5.2<TAB>1<TAB>Image_1.png
```

`<TAB>` above represents a tab character; it is not literal file content. Dates use month/day/two-digit-year and times use hours:minutes:seconds, with supported fractional seconds.

1. Load the corresponding images without changing their filenames. Use natural filename order for numbered images, so `Image_2.png` precedes `Image_10.png`.
2. Draw cells and assign samples. Run and review analysis if using Icescopy detections or the combined method.
3. Choose **CSU .dat import...**, select the file, and choose a **Count source** from the table below. Select blanks and a reset temperature only when needed.
4. Check the matched pictures, included samples, count source, and warnings before exporting.

Picture matching uses the filename without its folder and ignores letter case. Each matching row supplies that image's capture time and sample temperature. Image filenames do not need timestamps; filesystem dates and an assumed camera interval are not used. `CP_Sink_Temp` and electrical telemetry are not sample temperatures.

Use unique image names and keep the loaded images in the same order as the picture records. Duplicate names, ambiguous temperature columns, and invalid matched-picture times or temperatures stop the import. Unmatched loaded images are reported; image-derived counts cannot be imported if a freeze event lies on an unmatched image.

### Choose the count source

| Count source | Use it when | How counts are built |
| --- | --- | --- |
| **Icescopy detections** | You want counts from reviewed cell freeze events, including recordings without instrument detections. | All app sample groups are included. Counts change at the matching image's `Picture` row and remain at that value until another image or a cycle reset. Instrument counts are ignored. |
| **CSU recorded counts** | You want the instrument's existing sample counts. | Name app samples to match the `Sample_...` columns and assign the full set of cells to each sample. These assignments supply the total droplet count. Recorded values, including decreases, are retained before any selected blank correction. |
| **Icescopy + CSU (existing method)** | You want the previous CSU reconciliation method. | Image-derived counts set reference values at matched pictures. CSU counts fill between them, constrained by the neighboring references, the assigned cell total, and nondecreasing counts within each cycle. This remains the default. |

CSU output has one row per instrument record, so many rows can have an empty `picture` field. The import does **not** create or change individual cells' freeze events: instrument sample totals do not identify which droplets froze.

For recorded and combined counts, sample-name matching ignores case and repeated whitespace. Rename duplicate app sample names before importing. Unmatched named samples are omitted and reported. Combined mode can also include unassigned cells using image counts; recorded mode cannot assign instrument counts to unassigned cells.

Missing or invalid counts stop recorded and combined imports for the affected matched samples; choose **Icescopy detections** to ignore those columns. Recorded mode also stops if a count exceeds the sample's assigned cell total, rather than clipping the value. All-zero counts do not establish whether the instrument detector was enabled.

Review decreases in recorded counts. They are reported but do not start a new cooling cycle; cycles follow the chosen temperature threshold. Blank correction, when selected, is applied after counts are built. With no stored cell events, image counts are zero and can override positive instrument counts in combined mode; use recorded mode if you intend to keep those instrument counts.

## TAMU Linkam .xlsx

### Workbook and image requirements

Keep the Linkam export's metadata and table layout. An arbitrary workbook with temperature columns is not enough. The importer reads the first worksheet and expects:

- A start time obtained from a recognized `LDF file:` or `Source:` entry, or a `Recorded:` entry.
- A header row with `Temperature` in column B and `Image` in column R.
- Data beginning two rows below that header, with elapsed seconds in B and temperature in C.

Keep elapsed times in increasing order and inspect missing or invalid readings before import. The importer needs at least two usable temperature rows.

Image filename stems must have the form `YYYY-MM-DD-HH-MM-SS-ffffff`, where the final six digits are microseconds. For example:

```text
2026-01-01-12-00-01-000000.png
```

Load the images, choose **TAMU Linkam .xlsx import...**, and select the matching workbook. The app subtracts the workbook start time from each image timestamp and interpolates temperature on the workbook's elapsed-time axis. Images outside that time range have no assigned temperature; at least one image must be in range.

### Optional cell calibration

Supply a calibration CSV with these exact headers:

```csv
well,slope,intercept
0,1.02,0.20
1,0.98,-0.10
```

`well` is the Icescopy **cell ID**, not a plate label such as A1. For each usable entry:

`corrected temperature = (measured temperature − intercept) / slope`

Use finite numeric slopes and intercepts, with a nonzero slope. Rows that fail parsing are skipped; a zero slope cannot yield a corrected temperature. However, values such as `nan` and infinity can parse successfully and propagate into corrected output. Check the calibration file rather than assuming these values will be rejected. If a cell appears more than once, the last parsed entry for that ID is used.

When the calibration file yields at least one parsed entry, output adds a **corrected temperature_C** column for each sample. A header-only file or a file whose rows are all skipped adds no corrected columns. The value is the mean correction over that sample's cells with usable entries, not a separate temperature column for each freezing cell. The original **temperature_C** remains unchanged. Check coverage yourself: the summary's calibrated-cell count identifies matching calibration IDs and is not proof that every slope was usable.

Calibration does not move freeze frames or change the raw temperature record used to find cycle boundaries.

## PKU Linksys32 .iml

1. Load the images from the corresponding recording in their original export order.
2. Choose **PKU Linksys32 .iml import...** and select the original `.iml` file.
3. Choose blanks and a reset temperature if needed.
4. Check the image-record count, assigned temperatures, samples, and cycles.

The loaded image count must equal the number of embedded image records. Position 0 in the loaded sequence is paired with the first embedded image record, position 1 with the next, and so on. Count agreement does not verify that the pictures themselves are in the correct order.

Each image's timestamp and tagged temperature come directly from its embedded image record. The importer does not infer them from JPEG filenames or EXIF, and it does not replace tagged image temperatures by interpolating the continuous temperature record. That continuous record is used to identify cycle boundaries.

If you have images and a separate list of timestamps and temperatures but no original `.iml`, prepare a two-column file for **Standard CSV import...**. That is a separate timestamp-matching workflow; it does not reproduce the embedded-record matching automatically.

## UTK CSV

Use **UTK CSV import...** for a file with columns named exactly `Time` and `PV(C)1`. Temperatures must be in °C. For example:

```csv
Time,PV(C)1
2026-01-01/12:00:00:000,-5.0
2026-01-01/12:00:02:000,-5.2
```

The `Time` column also accepts forms such as `2026-01-01 12:00:00`, with no fractional seconds. Include at least two rows and no duplicate timestamps. Rows are sorted by time during import.

- **Images:** frame times come from automatically recognized image filename timestamps.
- **Video:** the first clip's filename supplies the start time. For example, `2026_0101_120000_001.MP4` supplies 2026-01-01 12:00:00. The app then adds elapsed video time; subsequent clip filenames do not establish separate starts.

UTK uses the same interpolation, blank correction, and per-cycle counting as Standard CSV. Check the video timing limitations above. If the first video filename lacks a recognized timestamp, prepare a two-column file and use **Standard CSV import...** to enter the first timestamp yourself.

## Water blanks and repeated cycles

### Water blank correction

Select the control samples to use as water blanks in the import dialog. At each output row, the app sums their frozen counts into `B`, the **water blank correction count**. It removes those selected blank groups from the ordinary sample columns.

For each remaining sample with assigned total `N` and frozen count `F`, the exported counts are:

- **number total:** `max(0, N − B)`.
- **number frozen:** `min(number total, max(0, F − B))`.

The same frozen-blank count is subtracted from both values. The app does not subtract the blank's entire cell total, scale by blank volume, or subtract a blank fraction. Several selected blanks contribute their summed frozen counts, not an average.

For example, a sample with 20 cells and 8 frozen cells, at a row where 2 blank cells are frozen, exports **18 total** and **6 frozen**. If no blanks are selected, counts are unchanged and the correction column contains `nan`. If blanks are selected but none has frozen yet, the correction is **0**.

This correction can change both the numerator and denominator over time. Check that the implemented count correction suits your experiment; further blank treatment or concentration calculations belong in your downstream analysis.

### Repeated cooling cycles

Leave **Reset After Warmed To (°C)** **Off** for a single cycle. For repeated cycles, select a threshold reached during the warming stage and inspect the resulting cycle boundaries.

The first cycle is numbered **0** in stored and exported data. The [Cells event selector](Annotation-Workflow.md#review-a-selected-cells-freeze-events) displays it as **Cycle 1**. A later cycle begins at a temperature reading that crosses from below the threshold to at least the threshold, provided the warm-up is large enough. The additional **Cycle Warm-Up Hysteresis (°C)** setting is in **Preferences → Analysis → Freeze Finding**, with bundled default **0.02 °C** and allowed range **0.00–10.00 °C**.

The implemented warm-up check compares the crossing temperature with the minimum reached during the preceding below-threshold segment. The rise must be at least the hysteresis value. It does not require reaching `threshold + hysteresis`.

For a 5.0 °C threshold and 0.02 °C hysteresis:

| Warming transition | New cycle? |
| --- | --- |
| 4.999 → 5.002 °C, with 4.999 as the preceding minimum | No: the rise is only 0.003 °C. |
| 4.80 → 5.00 °C | Yes: it crosses the threshold and rises 0.20 °C. |

Check the full temperature record, not only these two points. After a crossing is rejected as too small, simply continuing farther above the threshold does not create another crossing; a later below-to-above transition is needed.

For Standard, UTK, TAMU, PKU, and CSU image counts, each cell contributes at most once per cycle, using its first freeze event in that cycle. A cell needs an event in the next cycle to count there; earlier freezes do not carry forward. CSU combined mode reconciles counts separately within each cycle; recorded mode preserves the instrument values.

Cycles come from the temperature record. They are independent of the analysis intervals that control automatic freeze finding. Changing the reset threshold or warm-up hysteresis requires temperature reimport, not a new brightness measurement.

## Review and export

Before using the result, check:

1. **Groups and totals:** expected sample names, IDs, cell totals, blank groups, and any **Unassigned cells** group. If no cells have sample assignments, the unassigned group is labeled **All cells**.
2. **Matching:** parsed and in-range frame counts, or CSU picture/sample matches. Investigate omissions rather than treating them as zero freezing.
3. **Time and temperature:** beginning/end alignment, units, temperature range, and several known freeze frames.
4. **Cycles:** number and timing of resets, including events near each boundary.
5. **Corrections:** blank-adjusted totals and frozen counts; TAMU calibration coverage where used.

Choose **File → Output Results**, then **Freeze Count Timeseries CSV**. Save to a new location when preserving an earlier export, and save the session to retain the imported table and remembered import choices. Record **Cycle Warm-Up Hysteresis** separately: the session does not save that global preference.

The count table is not restricted to detected freeze frames or analysis intervals. Standard, UTK, TAMU, and PKU produce one row per loaded frame; CSU produces one row per instrument record. Missing temperatures are empty CSV fields, while `nan` has specific uses in correction and metadata fields. See [Output Reference](Output-Reference.md) before loading the table into other software.

Fraction frozen can be calculated as number frozen divided by a valid, nonzero number total. The app does not provide uncertainty estimates or calculate ice-nucleating-particle concentrations, and successful timestamp matching does not establish the accuracy of a freeze detection or temperature calibration.
