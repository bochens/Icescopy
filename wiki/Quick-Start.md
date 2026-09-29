# Quick Start

[User guide](Home.md) · [Interface and shortcuts](Interface-and-Shortcuts.md)

Follow this tutorial to turn a recording into reviewed freeze events and exported results. A **frame** is one image in the recording. A **cell** is a numbered circle marking the part of a droplet or well whose brightness will be measured.

## Before you start

- [Install Icescopy](Installation-and-Setup.md) and open the app.
- Have your own image sequence or video clips ready. Choose a recording where you can recognize freezing by eye. The screenshots illustrate the controls; they are not a downloadable example dataset.
- Know which droplets or wells belong to each sample.
- Create an output folder for this analysis. Keep the original recording available: a saved session refers to its source files.
- Have a temperature record ready if you want temperature-based counts. You can complete brightness analysis and freeze review without one.

For your first pass, mark a few clear cells and check their results before drawing the whole array. This helps you learn the controls and choose suitable detection settings.

## 1. Start a session and load the recording

1. Choose **File → New Session**, enter the session information, and accept the dialog.
2. Load one source type:
   - Images: choose **File → Add Image Files...** or **File → Add Image Folder...**.
   - Video: choose **File → Open Video Source...** and select all clips for this recording together.
3. Check the beginning, middle, and end of the recording. For several video clips, also inspect each join. Use **File → Sort Images** or **Sort Video Clips** if the order is wrong.
4. Choose **File → Save Session As...** and save a new `.icescopy` file in your output folder.

You should now see the recording, a timeline below it, and a **Frame Number** field in the status bar. The first frame is **0**. Click the image viewer, then use the left/right arrow keys to step through frames, or enter a frame number to jump there.

A session contains images or video, not both. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) for supported inputs, sorting, and source changes.

## 2. Prepare the view and mark the cells

Choose a frame where the droplets or wells are easy to locate. Use **Z** for pan and zoom; return to the cursor with **A**. If you need to change the image itself, use **Edit → Image Edit** before analysis. Cropping, exposure, and contrast affect measurements as well as appearance; see [Image Editing](Image-Editing.md).

### Draw the measurement circles

1. Click the image viewer, then press **S** for **Add Cell** or **G** for **Grid Tool**.
2. Move the preview over the current image and click once to hold it in place.
3. Adjust **Radius**, **X**, and **Y** in **Tool Options**. For a grid, also set **Rows**, **Cols**, **H Pitch**, **V Pitch**, and **Tilt**. Pitch means the distance between circle centers.
4. Keep each circle inside its droplet or well, then click **Apply** or press **Enter**.
5. Press **A** and check the numbered circles. A preview is not a saved cell until you apply it.

To correct a circle, select it and press **E**, adjust the edit preview, then **Apply**. To edit a group, drag a selection box across the cells in Cursor mode before pressing **E**. The [annotation guide](Annotation-Workflow.md) covers precise placement and group controls.

Check the circles at several later frames. If the recording moves, use **keyframes** to save corrected layouts at different frames; see [Follow movement with keyframes](Annotation-Workflow.md#follow-movement-with-keyframes).

### Assign samples

1. In Cursor mode (**A**), select the cells belonging to one sample.
2. Choose their **Sample ID** in Tool Options, or click **New Sample** to create and assign one.
3. Open **Edit → Sample Catalog Manager** and enter that sample's details.
4. Repeat for the other samples. Use **Window → Cells** to check assignments.

Fields marked **[all]** share one value across all samples. See [Sample Metadata](Sample-Metadata.md) before entering shared quantities such as well volume.

## 3. Limit where analysis runs

Skip this step to analyze the whole recording. To exclude setup, warming, or other unwanted sections:

1. Go to the first frame to include. Click the timeline button with the tooltip **Toggle analysis start marker at the current frame**.
2. Go to the last frame to include. Click **Toggle analysis end marker at the current frame**.
3. Add another start/end pair if you need another interval.

Both marked frames are included. To remove a marker, return to its frame and click the same button. These markers leave all source frames available for viewing.

The **freeze flag** has a different purpose: it adds or removes freeze events for selected cells. Use the separate start/end controls for analysis limits. See [the marker guide](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers) for multiple intervals and incomplete pairs.

## 4. Run analysis and review freezing

1. Choose **Analysis → Run Analysis** and wait for it to finish.
2. Press **A** and select one cell. Open **Window → Grayscale Plot** if needed.
3. Find its detected event, then use **Show Two Images** or **Show Three Images** to compare the surrounding frames.
4. Check several cells: a clear freeze event, a weak event, and a cell with no event.

The plot's solid line shows average brightness. The dashed line emphasizes brightness changes. The **Current Frame** marker follows the displayed frame; **Freeze Event** marks the cell's recorded event. Check the images to decide whether a detected change is freezing.

If detections need adjustment, open **Preferences → Analysis → Freeze Finding**:

- Enable **Detect freezing from brightening** if freezing makes cells brighter; leave it off for darkening.
- Lower **Peak Prominence** for weak real events; raise it to reject false detections.
- Increase **Peak Width** to reject brief noise; lower it for a real narrow response.

Change one setting at a time, **Save** preferences, then **Run Analysis** again. Saving settings or changing analysis markers does not update existing detections. Follow the [full tuning guide](Analysis-and-Results.md#review-and-tune-freeze-detection) for the other controls.

Make manual corrections **after** the final rerun, because rerunning replaces them. Select cells, go to the correct frame, and use the freeze flag; or select one cell and enter its **Freeze Frame** in Tool Options. See [Correct freeze frames](Annotation-Workflow.md#correct-freeze-frames).

## 5. Add temperature and export

If you do not have a temperature record yet, skip to saving and exporting **Measurements** and **Freeze Events**. You can add temperature later.

1. Choose **Analysis → Import Temperature Data** and the importer for your record.
2. Follow [Temperature Import](Temperature-Import.md) to match times and units. Check the resulting **Freeze Count Timeseries** in **Window → Results Tables**.
3. Save the session.
4. Choose **File → Output Results** and select the tables you need. Use a new filename or a fresh folder to keep earlier exports.

With temperature imported, counts include **number total** and **number frozen** for each sample. See [Output Reference](Output-Reference.md) for column meanings.

If you change freeze events or sample assignments after temperature import, import temperature again to rebuild the counts.

At the end, you should have a saved `.icescopy` session, reviewed freeze events, and the selected CSV (comma-separated values) exports. Keep the source images or videos with your project. See [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for reopening and sharing a session, or [Troubleshooting](Troubleshooting.md) if a step did not produce the expected result.
