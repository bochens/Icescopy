# Output Reference

**File → Output Results** exports the result tables currently held in the session. This reference describes the CSV files emitted by v2.3.8: their rows, columns, missing values, and interpretation. For the save/export procedure, see [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md).

## Choose the table for the question

| Export choice | Default filename | One row represents |
| --- | --- | --- |
| **Grayscale Measurements CSV** | `grayscale_measurements.csv` | One frame in the loaded recording, including frames skipped by analysis markers. |
| **Freeze Events CSV** | `freeze_events.csv` | One current freeze event for one cell. A cell can have several event rows or none. |
| **Freeze Count Timeseries CSV** | `freeze_count_timeseries.csv` | One loaded frame for Standard, UTK, TAMU, or PKU import; one instrument record for CSU import. |

Only available tables appear in the export dialog. A single-table export lets you choose a filename. Exporting several tables writes the default names into the selected folder and can replace existing files with those names. Use a fresh folder to preserve earlier outputs.

Exports contain the full stored tables. Selecting cells, displaying only frozen frames in the frame list, zooming the timeline, or viewing a subset of table rows does not filter the CSV. Analysis markers determine which brightness values were measured; they do not remove source-frame rows from the measurement or temperature tables.

CSV text is UTF-8 and comma-separated. Fields containing commas or other special characters are quoted as needed; use a CSV reader rather than splitting each line at every comma.

## Grayscale measurements

The first row is the header. There are no comment rows or source-folder line in this GUI export.

| Column | Meaning and units |
| --- | --- |
| `file_name` | The image filename or generated video-frame name. |
| `cell_<ID>_grayscale` | Mean brightness inside that cell, on an 8-bit 0–255 image scale. |
| `cell_<ID>_circle_x` | Cell-center x coordinate in source-image pixels. |
| `cell_<ID>_circle_y` | Cell-center y coordinate in source-image pixels. |
| `cell_<ID>_circle_radius` | Cell radius in source-image pixels. |

The four cell columns repeat for every cell represented in the analysis. Read the ID from each column name; do not assume that a cell's numeric ID equals its column position. Geometry describes the cell at that frame, including keyframe changes. Image zoom does not change these coordinates. Crop/rotation can transform the measurement area, but these geometry columns retain the source-image coordinates.

Rows remain in loaded frame order. There is **no separate frame-index column** in this file: the first data row is frame 0, the second frame 1, and so on. Do not renumber after dropping missing rows if you need to join measurements to freeze events.

A minimal synthetic example for one cell is:

```csv
file_name,cell_0_grayscale,cell_0_circle_x,cell_0_circle_y,cell_0_circle_radius
frame_000.png,100.0,40.0,50.0,8.0
frame_001.png,65.0,40.0,50.0,8.0
frame_002.png,nan,nan,nan,nan
```

The last row could be a frame excluded by analysis markers. It is not evidence that the cell disappeared or had zero brightness.

### Missing measurements

`nan` means a value was not measured or was unavailable. Common causes are:

- A frame is outside the selected analysis intervals: all cell values in that row are `nan`.
- A cell has no geometry at a particular frame.
- Its geometry is invalid, its radius is nonpositive, or no image pixels fall in its measurement area.

A circle partly outside the image or crop can still be measured from the overlapping pixels. Check placement rather than treating every finite value as proof that the full intended cell area was measured.

The brightness values reflect exposure, contrast, Uniform Exposure, crop, and the chosen video brightness source used for that analysis. They are not necessarily the original unadjusted pixel values. The dashed convolution signal shown in the plot is **not exported as an additional measurement column**.

## Freeze events

The columns are exactly:

```csv
cell,image_index,image_name
cell_0,1,frame_001.png
cell_1,4,frame_004.png
cell_0,12,frame_012.png
```

| Column | Meaning |
| --- | --- |
| `cell` | Cell identifier written as `cell_<ID>`. It is not the sample name. |
| `image_index` | Zero-based frame number in the loaded recording. For multiple video clips, this is the combined sequence's frame number. |
| `image_name` | The corresponding image filename or generated video-frame name. |

The table contains the current event list: automatic detections with any later manual changes applied. It has no field distinguishing a manual correction from an automatic detection and no confidence score. Save separate sessions if you need to compare those stages.

A cell with no event has no row. Therefore, counting distinct cells in this table does not give the total number of analyzed cells. Multiple rows for one cell can describe repeated cycles, separate changes, or events that still need review. They are not all counted separately within a single temperature cycle.

Row order is not a promise of globally chronological events. Sort numerically by `image_index` when needed. A header-only freeze table means the current result has no event rows; it does not establish that every cell remained unfrozen.

This CSV does not contain event temperature, sample metadata, or a frozen fraction. Join it to the appropriate frame-based temperature table or retain the session when you need those relationships. For CSU output, instrument row position is not frame index; use the picture matching described below.

## Freeze-count time series

This export has two parts:

1. Comment lines beginning with `#`, containing file, session, and sample information.
2. A regular CSV header and data rows.

The file format identifier is `icescopy_freeze_count_timeseries`, with `file_version: 1`. The file version describes this export format, not the Icescopy application version.

### Leading data columns

The first five columns are:

| Column | Meaning |
| --- | --- |
| `timestamp` | Frame time for Standard/UTK/TAMU/PKU, or instrument-record time for CSU. Normally ISO date/time text with milliseconds. No time-zone field is exported. |
| `temperature_C` | Temperature in °C, written to three decimal places when available. |
| `cycle` | Zero-based temperature-cycle number. Cycle 0 is the first cycle. |
| `image_name` | Frame name for Standard, UTK, TAMU, and PKU. |

**CSU replaces `image_name` with `picture`.** A CSU row can have an empty picture field because the temperature logger can record more often than the camera.

Standard, UTK, and TAMU obtain frame temperatures by interpolation; PKU uses tagged temperatures from embedded image records; CSU uses `Avg_Temp` or `Sample_Temp` at its instrument records. See [Temperature Import](Temperature-Import.md) for each input contract.

### Columns for each output sample

For each output group, including blank samples, the table adds:

- `<sample name> number total`
- `<sample name> number frozen`

TAMU adds `<sample name> corrected temperature_C` immediately before that group's two count columns when the calibration file yields at least one parsed entry. A header-only file or one whose rows are all skipped adds no corrected columns. The value is the mean corrected temperature of the group's cells with usable calibration entries, including cells that have not frozen. It is not the temperature of an individual freezing cell. The leading `temperature_C` remains uncorrected.

The **number total** and metadata field `cell_number` both give the number of cells assigned to that group. They are not reduced when blank cells freeze.

### Which samples appear

- Cells with sample assignments are grouped by sample ID, not just by name.
- Samples need nonempty names. Cells assigned to a sample with an empty name can be omitted from normal sample groups; fill in the name and reimport.
- Unassigned cells form an **Unassigned cells** group, including when no cells have sample assignments.
- Blank samples appear with their own total and frozen counts, like other samples.
- **Icescopy only** includes all cell groups. **Icescopy + .dat** includes named groups matching `.dat` sample columns, plus unassigned cells using Icescopy events. Check the import summary for omissions.

Separate sample IDs can share the same name, producing identical column labels. The metadata identifies the groups, but some CSV readers automatically rename duplicate headers. Distinct sample names are easier to work with; CSU rejects ambiguous duplicate names when matching an instrument column.

### Frame rows, cycles, and counts

For Standard, UTK, TAMU, and PKU, data row 0 corresponds to loaded frame 0, including frames outside automatic-analysis intervals. Counting within a cycle uses each cell's first event in that cycle. Later events for the same cell in that cycle do not add another frozen cell. A later cycle starts its counts again and needs its own events.

CSU rows follow the instrument record. **Icescopy only** holds each image's count forward from its matching picture row; **Icescopy + .dat** uses image counts as references for the intervening instrument counts. Do not join CSU rows to the event table by row number.

Analysis intervals and temperature cycles serve different purposes. Intervals restrict automatic measurement and detection; cycles reset counts based on the temperature record. Several analysis intervals can lie inside one temperature cycle, and one interval can span several cycles.

### Blank samples and older results

New imports export counts without blank correction. Blank controls keep their own total and frozen columns, and their freezing does not change another sample's counts. Apply blank correction later in your INP analysis toolkit.

Previously saved tables are preserved as stored. Older tables may contain a `water blank correction count` column and corrected counts, with selected blank groups omitted. Loading such a session does not undo that correction. Reimport temperatures to create an uncorrected table, then save to a new file if you need to preserve both versions.

## Comment metadata

The leading key/value lines are:

| Key | Value |
| --- | --- |
| `format_name` | `icescopy_freeze_count_timeseries`. |
| `file_version` | `1`. |
| `project_name` | Session project name, or `nan`. |
| `user_name` | Session user name, or `nan`. |
| `institution` | Session institution, or `nan`. |
| `analysis_date` | Session date, or `nan`; not a frame timestamp. |
| `reset_temperature_C` | Temperature reset setting, or `nan` when off; see the zero-degree caveat below. |

The following comment rows are comma-separated. The first value is a field key, followed by one value per output sample group, in the same order as the groups in the data table:

```csv
# sample_id,0,1
# cell_number,20,20
# sample_name,Sample_A,Sample_B
```

These are three illustrative rows, not a complete file. They describe two sample groups, even though the data table contains two count columns per group, or three columns with TAMU calibration. `sample_id` and `cell_number` are included independently of the sample fields chosen for export. Remaining rows use the field keys enabled by **Export** in the active sample-field definitions. See [Sample Metadata](Sample-Metadata.md).

Missing metadata is written as `nan`. Field labels shown in the app can differ from their saved keys; custom export keys remain the reference for other software. Fields shared across all samples are still repeated once for each output group.

**v2.3.8 caveat:** an exact numeric reset setting of **0 °C** is also written as `nan` in the preamble. The cycle calculation still uses 0 °C. Keep the session/import setting or a separate run note when distinguishing a zero-degree reset from **Off**; the preamble alone cannot distinguish them.

## Missing values and zeroes

For TAMU calibration, check that slopes and intercepts are finite and slopes are nonzero. The parser can accept `nan` and infinity, which can propagate into corrected temperatures; a non-finite result is not necessarily just an absent calibration entry.

| Location | Empty field or `nan` means |
| --- | --- |
| Measurement cell columns: `nan` | Not measured or unavailable; see the reasons above. |
| Count-table `timestamp`: empty | No usable frame timestamp; a CSU record may instead retain unparsed date/time text. |
| Count-table `temperature_C`: empty | No temperature was assigned, such as a frame outside the interpolation range. |
| Count-table `cycle`: empty | No usable time position from which to assign that frame to a cycle. |
| TAMU corrected temperature: empty | No raw temperature or no usable calibration entries for that group. |
| Comment metadata: `nan` | Missing information, with the 0 °C reset caveat above. |

A numeric **0** is a real output value: zero accepted frozen cells, zero correction, or a count clamped to zero. Do not turn all empty fields or `nan` values into zero. A row can have counts while lacking a temperature, so test the temperature field explicitly before constructing a temperature-dependent result.

## Read and reuse the files

For the count table, separate only the metadata lines that **start** with `#`. Do not use pandas' `comment="#"` option: it can truncate a valid header such as `Sample #1 number total`. For example:

```python
from io import StringIO
from pathlib import Path
import pandas as pd

lines = Path("freeze_count_timeseries.csv").read_text(encoding="utf-8").splitlines(keepends=True)
metadata_lines = [line for line in lines if line.startswith("#")]
table_text = "".join(line for line in lines if not line.startswith("#"))
counts = pd.read_csv(StringIO(table_text))
measurements = pd.read_csv("grayscale_measurements.csv")
events = pd.read_csv("freeze_events.csv")
```

This keeps the comment text in `metadata_lines` and reads the table into `counts`. Interpret the retained metadata separately when you need sample IDs, assigned cell counts, or custom fields. Also check how your reader handles duplicate sample names and missing values.

To calculate fraction frozen, divide **number frozen** by a valid, nonzero **number total**. Apply any blank correction in downstream analysis; new imports export counts without blank correction. A count table alone does not supply concentration, confidence intervals, detection accuracy, or calibration uncertainty.

Exports are a snapshot of the current stored results. Changing settings does not update an already written CSV. Recalculate or reimport as needed, then export to a new file or folder. A saved `.icescopy` session retains working state and internal result tables; the external count CSV additionally carries the comment metadata described here.
