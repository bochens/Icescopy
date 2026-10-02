# Sessions, Export, and Preferences

A **session** saves working state you can reopen in Icescopy. An **export** is a result table for other software. **Preferences** are application settings stored separately in your user account. Keep these roles distinct when preserving or reproducing an analysis.

## Save and resume a session

1. Choose **File → Save Session As...** and give the analysis a new `.icescopy` filename.
2. Use **File → Save Session** as you work. After a successful Save As, later saves update the new file.
3. To resume, choose **File → Open Session** and select that file.
4. Check a few frames, cell positions, analysis markers, and result panels before continuing.

The first **Save Session** also asks for a filename if the session has not been saved before. Starting or opening another session, or closing Icescopy, prompts you to save when the document has changed since its last save or open. Browsing frames, selecting cells, and changing viewing or tool controls do not trigger this prompt. An untouched new session starts without unsaved changes; adding images, annotations, results, or editing its metadata creates changes to save.

Use **File → Edit Session Metadata...** to edit the project, user, institution, and date. These details can appear in exported metadata.

## What is saved

| Stored in a session | Kept separately |
| --- | --- |
| Image/video paths, source description, frame order, and current frame | Original images and videos |
| Cell IDs, geometry, sample assignments, and keyframes | Original temperature and calibration files |
| Analysis start/end markers and freeze events | Global analysis/detection Preferences used to produce those events |
| Sample values and that session's field definitions | User-interface defaults in your account's Preferences |
| Image-edit state and cell/grid tool settings | External CSV exports |
| Available measurement, event, and count tables | External analysis scripts or calculations |
| Session metadata, remembered import options/paths, and console history | A complete portable copy of every input and dependency |

A session does **not** embed the media or original temperature files. It can retain imported tables without making the input files available for another import. It also does not replace a record of global freeze-finding settings. Retain the application version, those settings, original inputs, and temperature-import choices when documenting an analysis.

## Preserve alternative analyses

Before changing detection settings, sample grouping, or image adjustments:

1. Save the current session.
2. Choose **Save Session As...** and use a distinct name, such as `analysis-width-8.icescopy`.
3. Make the change, repeat the affected analysis steps, and export into a new folder.
4. Note the setting changed and the result of reviewing representative cells.

Saving is not an automatic version-history system: repeated saves replace the same file. Undo/Redo is useful for supported edits during the current session, but does not replace separate saved versions.

## Relink an image folder

Use this when image files have moved but their filenames have not changed.

1. Open the session. To preserve its original paths, use **Save Session As...** first.
2. Choose **File → Relink Images Folder...** and select the current image folder.
3. Read the report: check the number relinked and any missing or ambiguous filenames.
4. Inspect frames near the beginning, middle, and end to confirm the correct images were matched.
5. Save if the report says the updated session could not be written automatically.

Matching uses filenames. Duplicate names are ambiguous; an ambiguous match is not silently chosen. Relinking attempts to save the current session path after the update. It changes references, not the image files.

This command handles image sequences only. Keep video files at their recorded locations, or restore those locations before reopening a video session. When transferring work, test that the recipient can open the media; sending the session alone is insufficient.

## Export selected results

Finish freeze review first. For temperature-based counts, complete temperature import and inspect its summary before exporting.

1. Choose **File → Output Results**.
2. Select the available tables you need. **Select All** selects the available choices.
3. Click **OK**.
4. For one table, choose a CSV filename. For several tables, choose an output folder.
5. Open the exported files and check their headers, a few records, and sample metadata.

| Choice | Default filename | Purpose |
| --- | --- | --- |
| **Grayscale Measurements CSV** | `grayscale_measurements.csv` | Per-frame measurements and geometry |
| **Freeze Events CSV** | `freeze_events.csv` | Reviewed freeze-event frame indices |
| **Freeze Count Timeseries CSV** | `freeze_count_timeseries.csv` | Temperature-aligned sample counts and metadata |

Only available tables can be selected. Multiple-file export uses the default filenames above and can replace existing files. Choose a **new folder** to preserve earlier results. If a multi-file export stops with an error, some earlier files may already have been written; inspect the folder before retrying.

CSV means comma-separated values: a text table. See [Output Reference](Output-Reference.md) for column names, units, row structure, and missing values. Renaming a CSV file does not turn it into a session.

## Read the freeze-count CSV

Rows beginning with `#` describe the file, session, and samples. The numeric table follows. Sample fields are controlled by the session's field definitions and **Export** settings.

The application exports counts, not a final particle concentration. Fraction frozen can be calculated from a valid, nonzero **number total** and its corresponding **number frozen**. Blank samples retain their own counts. Apply blank correction in downstream analysis. See [Output Reference](Output-Reference.md) for count definitions and older saved results.

Missing values are not zero. Missing sample information, unmatched temperature, and an unused correction field are different situations.

## Customize sample fields

Open **Preferences → Samples → Sample Metadata Fields** to define fields, choose which are exported, or share a value across samples. Enter values in **Edit → Sample Catalog Manager**.

[Sample Metadata](Sample-Metadata.md) explains built-in units, the **All** setting, custom keys, renaming, deletion, and current-session fields versus defaults for new sessions.

## Other preferences

Open **Preferences** from the application menu or toolbar. Choose a category, change the required values, and click **Save**. Before Save, **Cancel** discards the dialog's edits.

If **Apply Preferences Failed** appears, the file was already saved but could not be fully applied to the current session; some settings may already have changed. Cancel does not undo that saved file. Review the error and retry Save, or preserve the session and reopen the app before relying on the settings. A write failure is different: resolve its cause and retry. Do not infer success merely because a dialog closed.

| Category | Purpose | Effect on analysis |
| --- | --- | --- |
| **General** | File sorting and history defaults | Review frame order when sorting an existing sequence |
| **Samples** | Naming pattern and field definitions | Check assignments and exported metadata |
| **Viewer** | Viewing and comparison defaults | Display-only changes do not require analysis |
| **Drawing** | Cell/grid defaults and annotation appearance | Actual geometry changes require analysis; line/label appearance alone does not |
| **Analysis** | Brightness source and freeze-finding controls | Rerun, review detections, then reimport temperatures |
| **Timeseries** | Plot appearance | Appearance alone does not require analysis |
| **Timeline** | Timeline appearance and sizing | Appearance alone does not require analysis |

Saving Preferences does **not** run analysis. It does not turn old measurements into results produced by new settings. See [what to repeat after an edit](Concepts-and-Data-Flow.md#what-to-repeat-after-an-edit).

## Preference file location

The app reads `preferences.xml` from the user configuration directory when it exists; otherwise it uses bundled `resources/preferences.xml` defaults. Qt, the application's interface library, chooses the platform's configuration location. It is separate from the installed application.

For controlled development checks, `ICESCOPY_CONFIG_DIR` selects a different configuration directory. See [Developer Guide](Developer-Guide.md). Do not edit bundled files inside an installed app to change ordinary preferences.

If a saved preference file cannot be read, the dialog shows a warning and defaults. Opening the dialog does not automatically overwrite the unreadable file. Review the warning before choosing **Save**.

## Recover from a save failure

- **File in use:** close the file in other applications, then choose **Retry**.
- **Read-only or denied location:** use a writable folder. Session saving offers **Save As** when available.
- **Need to keep working:** **Cancel** leaves unsaved work open; it does not mean the save succeeded.

Keep the app open until you have saved somewhere usable. A new session bundle is written to a temporary file and verified before replacing the destination. This protects against a failed write, but does not create a separate backup of every successful save. See [save troubleshooting](Troubleshooting.md#cannot-save-a-session-preferences-or-csv).

## Session bundle contents

For maintainers, a `.icescopy` file is a ZIP-format bundle with `session.json` and available tables named `grayscale.csv`, `freeze.csv`, and `freeze_count_timeseries.csv`. The current JSON schema version is `6`: the saved-data format version, not the application release number.

Treat these members as implementation details. Use **Output Results** for external tables: the public freeze-count CSV adds metadata rows that the internal table does not contain. See [Architecture Overview](Architecture-Overview.md) before changing serialization code.

Related: [Output Reference](Output-Reference.md) · [Sample Metadata](Sample-Metadata.md) · [Troubleshooting](Troubleshooting.md)
