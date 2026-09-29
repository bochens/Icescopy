# Quick Start

This walkthrough takes you from a recording to reviewed freeze events and exported counts. Have the source images or video clips, a sample map if needed, and a writable output folder ready. Temperature records can be added later.

## 1. Start a session and load the recording

Choose **File → New Session** and enter the session information. Load either:

- **File → Add Image Files...** or **Add Image Folder...** for an image sequence.
- **File → Open Video Source...** for one video or several clips selected together.

A session uses images or video clips, not a mixture. Check the beginning, middle, and end of the sequence. Use **File → Sort Images** or **Sort Video Clips** if necessary. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md).

Choose **File → Save Session As...** with a new filename when you want to preserve an earlier session.

## 2. Prepare the view and mark the cells

Use **Image Edit** if the view needs cropping or brightness adjustment. Then:

1. Press **S** for **Add Cell** or **G** for **Grid Tool**.
2. Click to hold the preview in place. Adjust its size and position in **Tool Options**; for a grid, also set rows, columns, spacing, and rotation.
3. Click **Apply** or press **Enter** to create the cells.
4. Press **A** to return to the cursor. Select cells and assign their **Sample ID**, or use **New Sample**.

Keep circles inside the droplets or wells. If they drift out of place later in the recording, use keyframes to save corrected layouts at different frames. See [Annotation Workflow](Annotation-Workflow.md) and [Image Editing](Image-Editing.md).

Open **Edit → Sample Catalog Manager** to enter sample information. Customize the available fields in **Preferences → Samples**. Fields marked **[all]** share one value across all samples.

## 3. Limit where analysis runs

To skip setup, warming, or other unwanted parts of the recording:

1. Navigate to the first frame you want included.
2. Click the timeline button whose tooltip says **Toggle analysis start marker at the current frame**.
3. Navigate to the last frame you want included and click **Toggle analysis end marker at the current frame**.
4. Add another start/end pair if you need a second interval.

Both boundary frames are included. With no markers, the whole recording is analyzed. To remove a marker, return to its frame and click the same button again. These markers do not remove source frames; you can still view the rest of the recording.

See [the marker guide](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers) for multiple intervals and unpaired markers. The freeze **flag** button edits freeze events; it does not set analysis boundaries.

## 4. Run analysis and review freezing

Choose **Analysis → Run Analysis**. Select a cell with the cursor to show its **Grayscale Plot**, then use **Show Two Images** or **Show Three Images** to compare the images around the detected event.

If detections are missed or incorrect, open **Preferences → Analysis → Freeze Finding**. Check whether freezing makes the cell brighter or darker, then adjust **Peak Prominence** and **Peak Width**. Follow the [tuning instructions](Analysis-and-Results.md#review-and-tune-freeze-detection) to change one setting at a time.

After saving a setting change or changing analysis markers, run analysis again. Existing detections do not update automatically. Rerunning replaces manual freeze corrections, so make those corrections after tuning: select cells and use the freeze flag at the current frame, or edit a single cell's **Freeze Frame** in **Tool Options**.

## 5. Add temperature and export

Choose **Analysis → Import Temperature Data** and the importer for your record. Review time alignment, sample assignments, and the resulting **Freeze Count Timeseries** table. See [Temperature Import](Temperature-Import.md) for supported formats and setup.

If you later change freeze events or sample assignments, import temperature data again to rebuild the counts.

Save the session, then use **File → Output Results** to choose the grayscale measurements, freeze events, or freeze-count tables. Use a fresh folder to preserve earlier exports. Counts include **number total** and **number frozen**; calculate a fraction frozen from those counts in your downstream analysis. Missing sample information is written as `nan`.

See [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) to resume work or change the export fields. For problems, start with [Troubleshooting](Troubleshooting.md).
