# Quick Start

Follow these steps to mark cells, find freeze events, and export results. Have your images or video clips and an output folder ready. You can add temperature records later.

## 1. Start a session and load the recording

1. Choose **File → New Session** and enter the session information.
2. Load images with **File → Add Image Files...** or **Add Image Folder...**. For video, use **File → Open Video Source...** and select the clips together.
3. Check the beginning, middle, and end of the recording. Use **File → Sort Images** or **Sort Video Clips** if the order is wrong.
4. Choose **File → Save Session As...** and use a new filename to preserve any earlier session.

A session contains images or video, not both. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) for details.

## 2. Prepare the view and mark the cells

Use **Edit → Image Edit** for any crop or brightness adjustments. Then:

1. Press **S** for **Add Cell** or **G** for **Grid Tool**.
2. Click to hold the preview in place. Adjust its size and position in **Tool Options**. For a grid, also set rows, columns, spacing, and rotation.
3. Click **Apply** or press **Enter** to create the cells.
4. Press **A** for the cursor. Select cells and choose their **Sample ID**, or click **New Sample**.

Keep circles inside the droplets or wells. If the recording moves, use **keyframes** to save corrected cell positions at different frames. See [Annotation Workflow](Annotation-Workflow.md) and [Image Editing](Image-Editing.md).

Enter sample details in **Edit → Sample Catalog Manager**. Customize the fields in **Preferences → Samples**; fields marked **[all]** share one value across all samples.

## 3. Limit where analysis runs

To skip setup, warming, or other unwanted frames:

1. Go to the first frame to include. Click the timeline button with the tooltip **Toggle analysis start marker at the current frame**.
2. Go to the last frame to include. Click **Toggle analysis end marker at the current frame**.
3. Add another start/end pair if you need another interval.

Both marked frames are included. With no markers, analysis uses the whole recording. To remove a marker, return to its frame and click the same button. You can still view frames outside the marked intervals.

See [the marker guide](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers) for multiple intervals and unpaired markers. The freeze **flag** edits freeze events; use the separate start/end buttons for analysis limits.

## 4. Run analysis and review freezing

1. Choose **Analysis → Run Analysis**.
2. Select a cell to show its **Grayscale Plot** (brightness over time).
3. Use **Show Two Images** or **Show Three Images** to inspect the frames around its detected event.
4. If events are missed or incorrect, open **Preferences → Analysis → Freeze Finding**. Check whether freezing makes the cell brighter or darker, then tune **Peak Prominence** and **Peak Width** using the [tuning guide](Analysis-and-Results.md#review-and-tune-freeze-detection).
5. Save any setting changes and run analysis again. Also rerun after changing analysis markers.

Rerunning replaces manual freeze corrections. Finish tuning first, then select cells and use the freeze flag, or edit a single cell's **Freeze Frame** in **Tool Options**.

## 5. Add temperature and export

1. Choose **Analysis → Import Temperature Data** and the importer for your record.
2. Check the time alignment, sample assignments, and **Freeze Count Timeseries** table. See [Temperature Import](Temperature-Import.md).
3. Save the session.
4. Choose **File → Output Results** and select the tables to export. Use a fresh folder to preserve earlier exports.

If you change freeze events or sample assignments, import temperature data again to rebuild the counts. Counts include **number total** and **number frozen**; use these to calculate the fraction frozen. Missing sample information is exported as `nan`.

See [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) to resume work or change export fields, and [Troubleshooting](Troubleshooting.md) for help.
