# Sessions, Export, and Preferences

Use a session file to continue working in Icescopy and CSV exports to use the results in other software.

## Save and resume a session

1. Start with **File → New Session** and enter any session information you need.
2. Load images or video, annotate cells, and choose **File → Save Session As...** to create a `.icescopy` file.
3. Use **File → Save Session** for later updates to that file.
4. Use **File → Open Session** to resume it. **File → Edit Session Metadata...** changes the project, user, institution, and date fields.

Sessions save the source paths, cell annotations, keyframes, freeze events, analysis markers, sample catalog and field definitions, image-edit settings, and available result tables. The source images and videos are **not embedded** in the session. Keep them available when copying or sharing a session.

**Save Session As...** gives an experiment or trial a separate file. Save a copy before changing an existing analysis if you want to retain the original. After Save As, subsequent Save Session commands update the new file.

## Relink an image folder

If the images have moved:

1. Open the session. If you want to preserve its original paths, use **Save Session As...** first.
2. Choose **File → Relink Images Folder...** and select the current image folder.
3. Read the result message and inspect the loaded images. Matching is by filename; missing files and ambiguous duplicate names are reported.

Relinking updates the active session's paths and attempts to save them into its current session file. If saving fails, the message asks you to use Save Session. Relink is for image folders; it does not relocate video files. Keep video files at their recorded locations when reopening a video session.

## Export selected results

1. Choose **File → Output Results**.
2. Check the available tables you need, or use **Select All**.
3. Click **OK**. For one selected table, choose a CSV filename. For multiple tables, choose an output folder.

| Selection | Default filename | Contents |
| --- | --- | --- |
| **Grayscale Measurements CSV** | `grayscale_measurements.csv` | Frame-by-frame brightness measurements and cell geometry. |
| **Freeze Events CSV** | `freeze_events.csv` | Detected or manually corrected freeze events. |
| **Freeze Count Timeseries CSV** | `freeze_count_timeseries.csv` | Temperature-aligned counts and sample information. |

Only tables currently available in the session appear in the export dialog. Multiple-table export uses the fixed filenames above and can replace files with those names. Choose a new output folder to retain earlier results.

Image changes require another analysis run. Changes to freeze events or sample assignments require temperature import to be repeated before exporting updated grouped counts. Descriptive sample-field changes update export information without rerunning grayscale measurements.

## Read the freeze-count CSV

The file begins with comment rows marked `#`, followed by the data table. Comments include session information, the reset temperature, sample IDs, cell counts, and sample fields enabled for export.

For each sample, the table contains **number total** and **number frozen**. Calculate fraction frozen from those counts in downstream analysis if required; Icescopy does not export a fraction-frozen column. Grouping uses `sample_id`, so distinct samples with identical names remain separate.

The sample field `cell_number` records the number of cells assigned to the sample. Missing information is written as `nan`. An export notice can report missing sample information; it does not supply those values.

See [Temperature import](Temperature-Import.md) for time matching, repeated cycles, and water blank correction.

## Customize sample fields

Use **Edit → Sample Catalog Manager** to enter values for each sample. To change which fields are available, open **Preferences → Samples → Sample Metadata Fields**.

| Column | Meaning |
| --- | --- |
| **Label** | The name shown in the Sample Catalog. |
| **Key** | The field's identifier in saved data and exports. Custom keys use lowercase letters, digits, and underscores, starting with a letter; for example, `storage_note`. |
| **Type** | Text, number, or date/time for custom fields. |
| **Export** | Include this field in the sample-information rows of the freeze-count CSV. |
| **All** | Use one shared value across every sample. |

Use **Add Field**, **Delete Field**, **Move Up**, or **Move Down** to change custom fields. Fixed identity fields remain available. Save the preferences to apply the changes; while a session is active, the fields apply to that session and become defaults for new sessions. A saved session retains its own field definitions.

Fields with **All** checked appear as **[all]** in the Sample Catalog. Editing their value for one sample updates it for every sample. **Well volume (uL)** uses this setting by default. Clear All when different samples need different values.

Deleting a field can remove its stored sample values. The app asks for confirmation when saving preferences would drop populated fields. Use Save Session As before changing a field layout you may need to recover.

## Other preferences

Preferences are organized into **General**, **Samples**, **Viewer**, **Drawing**, **Analysis**, **Timeseries**, and **Timeline** pages. They include default sorting, sample naming, grid controls, plot appearance, and freeze-finding settings.

**Analysis** includes detection from brightening and the video grayscale source. The converted grayscale option retains the usual color-to-grayscale conversion; the video luma option uses the video's brightness channel when available. If you change measurement or detection settings, rerun analysis and review the new results before reimporting temperature data.

Display preferences such as colors or the number of visible frames do not require new measurements. Save the session after choosing the settings and fields needed for the experiment.

## Session bundle contents

A `.icescopy` file is a ZIP-format bundle. It contains `session.json` for the working state and any available result tables:

- `grayscale.csv`
- `freeze.csv`
- `freeze_count_timeseries.csv`

These internal tables are plain CSV members. The external freeze-count export adds the commented session and sample-information rows described above. Use **Output Results** when preparing files for other software.
