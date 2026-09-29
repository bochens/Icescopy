# Annotation Workflow

A **cell** is a numbered circle marking the area of a droplet or well to measure. Draw the cells, check their positions through the recording, assign samples, then run analysis.

## Choose a tool

Click the image viewer before using a letter shortcut, so you do not type into a field. These tools are also in the **Edit** menu and toolbar.

| Key | Tool | Use |
| --- | --- | --- |
| **A** | Cursor Tool | Select cells, inspect results, edit freeze frames, and assign samples. |
| **S** | Add Cell | Draw one circle. |
| **G** | Grid Tool | Draw rows and columns of circles. |
| **E** | Edit Cell | Adjust an existing circle or group. |
| **D** | Delete Cells | Remove cells. |
| **Z** | Pan and Zoom | Move around the image and inspect placement. |

## Add one cell

1. Press **S** and move the circle preview over a droplet or well.
2. Click once to **pin** the preview: it stops following the pointer. This does not add the cell yet.
3. Adjust **Radius**, **X**, and **Y** in Tool Options, or drag the handle to move it.
4. Click **Apply** or press **Enter** to add the cell. Repeat for other locations.

**Float** makes the preview follow the pointer again. **Cancel** discards it. Double-clicking, or pressing Enter while the preview follows the pointer, pins and adds the cell in one action.

## Add a grid

1. Press **G**, move the grid over the array, and click to pin it.
2. Set **Rows**, **Cols**, and **Radius**. Keep each circle inside its well.
3. Set **H Pitch** and **V Pitch**, the horizontal and vertical distances between circle centers. Use **Tilt** to rotate the grid.
4. Adjust **X** and **Y**, or drag the handle. Check the edges as well as the center.
5. Click **Apply** or press **Enter**. Press **A** to inspect the numbered cells.

![Pinned grid preview with placement controls and Apply button](../resources/readme/2026-09-29/grid-annotation.png)

**Float** returns to pointer placement; **Cancel** discards the preview. Check every circle: the grid uses the spacing you set and does not find wells automatically.

## Edit existing cells

1. Press **A** and click a cell, or drag a selection box across a group.
2. Press **E**. If nothing is selected, choose the cells to edit.
3. Adjust size and position. For a group, you can also adjust spacing and rotation.
4. Click **Apply** or press **Enter**. **Cancel** keeps the original placement.

Edits preserve cell IDs and their connection to results. Group edits use the cells' existing arrangement. To remove cells, use **D**, or select them with the cursor and press Delete or Backspace. Use **Edit → Undo** to undo annotation changes.

## Assign cells to samples

1. Press **A** and select the cells belonging to a sample.
2. Choose a **Sample ID** in Tool Options, or click **New Sample** to create and assign one.
3. Open **Edit → Sample Catalog Manager**, expand the sample, and edit its details.

Sample assignments determine the grouped freeze counts. The **Cells** panel lists cell IDs, samples, and freeze frames. Samples with identical names still count separately if they have different sample IDs.

## Enter sample information

In the Sample Catalog, double-click a value to edit it. Default fields include:

- Name, long name, and sampling site.
- Collection start and end, in `YYYY-MM-DD HH:MM:SS` format.
- Sample type: `air`, `soil`, or `other`.
- Well volume, dilution factor, air volume, filter fraction, suspension volume, and dry mass.

Fields that do not apply to the sample type are disabled. Fields marked **[all]** share one value across all samples: editing one changes every sample. Well volume is shared by default.

Use **Preferences → Samples** to add fields, choose export fields, or make a field shared. See [Customize sample fields](Sessions-Export-and-Preferences.md#customize-sample-fields).

Editing sample details does not require new brightness measurements. If you reassign cells to samples, repeat temperature import to rebuild the counts. Missing sample information is exported as `nan`.

## Follow movement with keyframes

A **keyframe** stores cell positions and sizes at one frame. Between keyframes, Icescopy gradually changes one saved layout into the next.

1. Go to a frame where the layout is clear and place the circles.
2. Click the timeline's diamond button to make it a keyframe.
3. Go to a later frame where the cells have moved. Make it a keyframe **before** editing the circles.
4. Press **E**, align the cells, and apply the changes. Check the frames between the two keyframes.

Once keyframes exist, lasting layout edits must be made at a keyframe. Add or select one before correcting alignment. Rerun analysis after changing cell placement or keyframes.

## Choose the analysis interval

Go to the first frame to include and toggle the timeline's **analysis start** marker. At the last frame, toggle **analysis end**. Then choose **Analysis → Run Analysis**.

Both marked frames are included. The markers limit measurement and automatic freeze finding without deleting source frames. Changing them does not rerun analysis. See [Analysis and Results](Analysis-and-Results.md) for multiple intervals and detection settings.

## Compare images and inspect a cell

Use **Show Two Images** for the previous/current pair, or **Show Three Images** for previous/current/next. **Show One Image** returns to the current frame. Select and edit cells on the current frame.

After analysis, press **A** and select a cell. Open **Window → Grayscale Plot** if needed. Compare its brightness line and current-frame marker with the visible freeze event.

![Frame comparison with cell inspection and the grayscale plot](../resources/readme/2026-09-29/droplet-frame-comparison-clear-labels.jpg)

See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) for navigation and viewer controls.

## Correct freeze frames

Finish tuning and rerunning analysis before making manual corrections: **a rerun replaces them**.

To mark an event at the displayed frame:

1. Press **A** and select the cell or cells.
2. Go to the frame where they freeze.
3. Click the timeline's **flag**. This adds a freeze event; if all selected cells already have an event there, it removes it instead.

To replace a cell's event list:

1. Select one cell with the cursor.
2. Enter a frame number in **Freeze Frame** under Tool Options, then click **Set**. Use the application's frame numbers, which start at **0**.
3. For multiple events, enter comma-separated numbers. Enter **None** to clear the list.

The flag edits freeze events; it is not a bookmark. These edits update the event results without measuring brightness again. Reimport temperature data afterward to rebuild freeze counts.

## Finish in this order

1. Prepare the images, place cells, add any keyframes, and set analysis markers.
2. Assign samples and enter their details.
3. Run analysis, review the images, and tune detection if needed.
4. Correct freeze frames, then import temperature data.
5. Check the counts, save the session, and export the tables.

Use **File → Save Session As...** before trying a different analysis to preserve the earlier session.
