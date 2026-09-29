# Sessions, Export, and Preferences

Save a session to resume work in Icescopy. Export CSV tables to use results in other software.

## Save and resume a session

1. Choose **File → Save Session As...** to save your work in a `.icescopy` file.
2. Use **File → Save Session** to update that file as you work.
3. Use **File → Open Session** to resume it later.

Sessions store cell annotations, keyframes, freeze events, analysis markers, sample information, settings, and available result tables. They store paths to the source images and videos, **not the media files themselves**. Keep those files when copying or sharing a session.

To preserve an earlier analysis, use **Save Session As...** before making changes. Later saves update the new file.

Use **File → Edit Session Metadata...** to edit session information such as the project, user, institution, and date.

## Relink an image folder

If the images have moved:

1. Open the session. If you want to preserve its original paths, use **Save Session As...** first.
2. Choose **File → Relink Images Folder...** and select the current image folder.
3. Check the report and loaded images. Icescopy matches by filename and reports missing or duplicate matches.

Relinking updates the paths and attempts to save the current session file. If saving fails, use **Save Session**. Relinking works only for images; keep videos at their saved locations.

## Export selected results

1. Choose **File → Output Results**.
2. Check the available tables you need, or use **Select All**.
3. Click **OK**. For one selected table, choose a CSV filename. For multiple tables, choose an output folder.

| Selection | Default filename | Contents |
| --- | --- | --- |
| **Grayscale Measurements CSV** | `grayscale_measurements.csv` | Frame-by-frame brightness measurements and cell geometry. |
| **Freeze Events CSV** | `freeze_events.csv` | Detected or manually corrected freeze events. |
| **Freeze Count Timeseries CSV** | `freeze_count_timeseries.csv` | Temperature-aligned counts and sample information. |

Only available tables appear in the dialog. Exporting multiple tables can replace files with the names above. Choose a new folder to preserve earlier results.

Before exporting updated results, rerun analysis after image changes and reimport temperatures after changing freeze events or sample assignments. Editing descriptive sample fields does not require a new analysis run.

## Read the freeze-count CSV

Rows beginning with `#` contain session and sample information, including the reset temperature, sample IDs, cell counts, and fields enabled for export. The data table follows these rows.

Each sample has **number total** and **number frozen** columns. To calculate fraction frozen, divide number frozen by number total, using a valid, nonzero total. Icescopy does not export this fraction. Samples are grouped by `sample_id`; samples with the same name remain separate if their IDs differ.

The `cell_number` field records how many cells are assigned to each sample. Missing information is written as `nan`, not zero. Fill in missing sample fields if you need them for later calculations.

See [Temperature import](Temperature-Import.md) for time matching, repeated cycles, and water blank correction.

## Customize sample fields

Enter sample values in **Edit → Sample Catalog Manager**. To add or change fields, open **Preferences → Samples → Sample Metadata Fields**.

| Column | Meaning |
| --- | --- |
| **Label** | The name shown in the Sample Catalog. |
| **Key** | The field's name in saved data and exports. Start custom keys with a lowercase letter; use only lowercase letters, digits, and underscores, such as `storage_note`. |
| **Type** | Text, number, or date/time for custom fields. |
| **Export** | Include this field in the sample-information rows of the freeze-count CSV. |
| **All** | Use one shared value across every sample. |

Use **Add Field**, **Delete Field**, **Move Up**, or **Move Down** to change custom fields, then save Preferences. Changes apply to the active session and become defaults for new sessions. Existing saved sessions retain their own field definitions. Fixed identity fields cannot be removed.

Fields with **All** checked appear as **[all]** in the Sample Catalog. Editing one sample's value changes it for every sample. **Well volume (uL)** is shared by default; clear **All** to give samples different volumes.

Deleting a field can remove its saved values; the app asks for confirmation if the field contains data. Use **Save Session As...** first if you may need to recover those values.

## Other preferences

Preferences include file sorting, sample fields, drawing controls, plot appearance, and freeze detection.

On the **Analysis** page, choose whether freezing makes the image brighter and which brightness source to use for video. Converted grayscale calculates brightness from color; video luma uses the video's brightness channel when available. After changing measurement or detection settings, rerun analysis, check the results, and reimport temperatures.

Display changes, such as colors or the number of visible frames, do not require another analysis run.

## Session bundle contents

A `.icescopy` file is a ZIP-format bundle containing `session.json` and any available result tables:

- `grayscale.csv`
- `freeze.csv`
- `freeze_count_timeseries.csv`

Use **Output Results** to prepare tables for other software. The exported freeze-count table includes session and sample information that the internal table does not.
