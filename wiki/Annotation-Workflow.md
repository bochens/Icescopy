# Annotation Workflow

[User guide](Home.md) · [Quick start](Quick-Start.md) · [Sample metadata](Sample-Metadata.md)

A **cell** is a numbered circle defining the part of a droplet or well to measure. Icescopy measures the average brightness inside each circle. Draw cells, check their positions through the recording, assign them to samples, and then run analysis.

## Before you draw

Load and order the [recording](Loading-and-Reviewing-Frames.md). Choose a frame where the droplets or wells are clear. Complete any [crop or image adjustments](Image-Editing.md) you need, then open **Window → Tool Options** and **Window → Cells**.

Use **File → Save Session As...** before changing a layout you need to preserve. Keep each circle within the area you intend to measure; a well edge, reflection, or neighboring droplet can change its brightness signal.

## Choose a tool

Click the image viewer before using a letter shortcut, so you do not type into a field. The same tools are in the **Edit** menu and toolbar.

| Key | Tool | Use |
| --- | --- | --- |
| **A** | Cursor Tool | Select existing cells, inspect their results, edit freeze frames, and assign samples. |
| **S** | Add Cell | Draw one measurement circle. |
| **G** | Grid Tool | Draw rows and columns of circles. |
| **E** | Edit Cell | Adjust an existing circle or selected group. |
| **D** | Delete Cells | Delete selected cells, or enter the tool for clicking cells to remove. |
| **Z** | Pan and Zoom | Move around the image and inspect placement. |

Hold **Space** to pan or zoom temporarily, then release it to return to the current tool. This is useful while positioning a preview. See [Interface and Shortcuts](Interface-and-Shortcuts.md) for the complete shortcut list.

## Select cells

Selection chooses which existing cells an action affects. It does not create a cell or change its position.

1. Press **A** to enter Cursor mode.
2. Select cells on the **current image**, using one of the methods below.
3. Check **Tool Options** before editing, deleting, assigning a sample, or applying a freeze flag.

| Selection | How |
| --- | --- |
| One cell | Click its circle. An ordinary click replaces the earlier selection. |
| A group in one area | Start on empty image space and drag a selection box across the circles. Circles intersecting the box are selected. |
| Separate cells | Hold **Ctrl** on Windows or **Command** on macOS while clicking circles to add or remove them from the selection. |
| Cells by ID | Open **Window → Cells** and select the top-level **Cell** rows. Use Ctrl/Command-click for separate rows or Shift-click for a range. |
| Clear the image selection | Click empty image space in Cursor mode. |

The Cells panel and image selection stay in sync. Expand a Cell row to read its sample assignment and freeze frames; these detail rows are not separate cells. Tool Options shows one cell's properties or the IDs of a multiple selection. The **Freeze Frame** field is editable only when exactly one cell is selected.

If clicking draws a preview instead of selecting, you are in Add Cell or Grid Tool; press **A**. Use **E** to move existing circles. Dragging a selection box does not move or resize cells.

### Center the selection

Select one or more cells, then click **Center on selection** at the top of **Cells**, or under **Cell Info** in the Cursor Tool Options. Both buttons center the same selection. They are disabled when there is no selected cell with a position on the current image, or no current image is loaded.

Centering moves the view without changing zoom. For a group, it centers the smallest rectangle enclosing the complete selected circles at the **current frame**. A widely spread group may still extend beyond the view; zoom out if needed. In two- or three-image view, the neighboring panes follow the Current pane's center.

To center after each selection change, enable **Auto-center** at the top of **Cells**. It starts unchecked each time you open the app. In Cursor mode, it responds to selection changes in the Cells list or current image after you release the mouse, or after a keyboard selection in the list. Turning it on does not move the view until you change the selection.

Auto-center does not follow frame changes, editing, drawing, deletion, cropping, panning, or Undo/Redo. Use **Center on selection** whenever you want to center the current selection again.

## Add one cell

1. Press **S** and move the circle preview over the desired droplet or well.
2. Click once to **pin** it: the preview stops following the pointer. The cell has not been created yet.
3. In Tool Options, set **Radius** and adjust **X** and **Y**, or drag the preview handle to position it.
4. Click **Apply** or press **Enter**.
5. Move to the next location and repeat. Press **A** when finished.

A successfully added cell has a number and appears in the Cells panel. Radius and position use image pixels; image zoom does not change those values.

**Float** makes the preview follow the pointer again. **Cancel**, Escape, or a right-click discards the preview without creating a cell. Double-clicking a floating preview, or pressing Enter while it is floating over the current image, pins and applies it in one action.

If Apply is disabled, move over the current image and click to pin a valid preview. If you added a cell accidentally, use **Edit → Undo**.

## Add a grid

Use Grid Tool for a regular array of wells or droplets. A grid uses the layout you specify; it does not detect wells automatically.

1. Press **G**, move the preview over the current image, and click to pin it.
2. Set **Rows** and **Cols** to the number of circles to create.
3. Set **Radius** so each circle stays inside the area to measure.
4. Set **H Pitch** and **V Pitch**, the horizontal and vertical distances between circle centers. Use **Tilt** to rotate the whole grid.
5. Adjust **X** and **Y**, or drag the handle, to align the grid.
6. Inspect circles at the edges and center. Click **Apply** or press **Enter** only when the layout fits.
7. Press **A** and check the resulting numbered cells.

![Pinned grid preview with placement controls and Apply button](../resources/readme/2026-09-29/grid-annotation-native.png)

Pitch and radius use image pixels; tilt uses degrees. Changing **Rows** or **Cols** changes how many cells will be created. A grid with 4 rows and 6 columns creates 24 cells when applied.

Use **Float** to reposition the preview with the pointer, or **Cancel** to discard it. If spacing varies across the image, start with the closest grid fit, then edit individual cells or selected groups. Do not leave badly placed circles simply to keep a rectangular pattern.

## Edit existing cells

Editing changes the existing cells. Their IDs and sample assignments stay connected to them unless you deliberately rename an ID or change an assignment.

### Edit one cell

1. Press **A**, select one circle, then press **E**.
2. Check that Tool Options says **Edit Cell** and shows the intended **Cell ID**.
3. Set **Radius Delta**, **X Offset**, and **Y Offset**, or drag the preview handle.
4. Inspect the preview and click **Apply** or press **Enter**.

These controls describe **changes from the existing circle**, not replacement dimensions. Zero leaves that value unchanged. For example, a cell with radius 20 pixels and **Radius Delta = 2** becomes a radius-22 cell. A radius delta of zero does not shrink it to zero.

Use **Cancel** to keep the original position and size and return to choosing a cell to edit. If no cell was selected before pressing E, click one in the image to begin.

### Edit a group

1. Press **A** and select the group.
2. Press **E**. Tool Options should show **Edit Group**.
3. Adjust **X Offset** and **Y Offset** to move the group.
4. Adjust **Radius Delta**, **X Pitch**, **Y Pitch**, or **Rotation** if needed.
5. Check the whole preview, then click **Apply**.

The group starts from the selected cells' existing arrangement. These controls apply changes relative to that arrangement; they do not replace it with the last grid you drew. Radius Delta changes each selected cell's radius by the same amount. Group editing keeps the same cells, so it has no Rows or Cols control.

A pinned preview can be dragged by its handle. **Float** returns to pointer placement; **Cancel** discards the position and size changes. After applying either a single or group edit, inspect the cells at other frames and rerun analysis.

### Rename a cell ID

Cell IDs identify cells in the image, saved layouts, and result tables. They are separate from Sample IDs.

1. Select one cell and press **E**.
2. Enter an unused, nonnegative integer in **Cell ID**.
3. Finish editing the field, for example by pressing Tab.
4. Check the new number in the image and Cells panel.

The rename updates that cell's saved keyframes and result labels. An ID already used by another cell is rejected. **Renaming takes effect when the field edit finishes**, separately from the circle's Apply button. Canceling the placement preview does not undo a completed rename; use **Edit → Undo**.

## Delete cells

For several cells, select them in Cursor mode and press **Delete** or **Backspace** while the image viewer has focus. Clicking **Delete Cells** with a selection also deletes that selection. With no selection, **D** enters Delete Cells mode; click each circle to remove it, then press **A** to finish.

Deleting a cell removes it from saved keyframes and its cell-specific measurement/event records. It does not remove image files. Use **Edit → Undo** immediately if you delete the wrong cells, then check the selection before continuing.

Do not press Delete while the **Images** list has focus when you intend to delete cells: there it removes image entries from the session. See [Remove or replace a source](Loading-and-Reviewing-Frames.md#remove-or-replace-a-source).

## Assign cells to samples

A **sample** groups cells that should contribute to the same sample's freeze counts.

1. Press **A** and select the cells belonging to a sample.
2. Choose an existing **Sample ID** in Tool Options, or click **New Sample** to create a sample and assign the selected cells.
3. Open **Edit → Sample Catalog Manager** to enter that sample's details.
4. Repeat for the remaining groups.
5. Check **Window → Cells** to confirm assignments.

Changing the Sample ID applies to the whole current selection. Samples with identical displayed names still remain separate if their Sample IDs differ. If counts appear in the wrong group, inspect these assignments before changing detection settings.

## Enter sample information

In Sample Catalog Manager, expand a sample and double-click a value to edit it. Enter the name, sample type, collection details, and any quantities needed for the experiment.

Fields marked **[all]** share one value across every sample. Well volume is shared by default. Fields that do not apply to the selected sample type are disabled. Use **Preferences → Samples** to add fields, choose export fields, or change whether a field is shared.

See [Sample Metadata](Sample-Metadata.md) for field meanings, units, sample types, and shared-field examples. Missing sample information is exported as `nan`.

Editing descriptive sample details does not require new brightness measurements. Changing which sample a cell belongs to requires temperature import again to rebuild the grouped counts.

## Follow movement with keyframes

A **keyframe** stores cell positions and sizes at one frame. Between two keyframes, Icescopy gradually changes each cell's position and size from the first saved layout to the second. Before the first keyframe and after the last, it uses the nearest saved layout.

Use keyframes when droplets, wells, or the camera move enough that a fixed circle would measure a different area.

1. Choose an early frame where the layout is clear. Draw and check the cells.
2. Click the timeline's **diamond** button to save that frame as a keyframe.
3. Go to a later frame where the layout needs correction.
4. **Mark the later frame as a keyframe before editing there.**
5. Select the affected cells, press **E**, align them, and **Apply**.
6. Inspect several frames between the two keyframes. Add another keyframe where the calculated layout misses the target.
7. Check the beginning and end of every interval you intend to analyze, then rerun analysis.

For example, save the initial layout at frame 0 and a shifted layout at frame 100. Check frame 50. If the motion was not gradual, add a keyframe near the change and align it there instead of relying on the two distant layouts.

Once any keyframes exist, a lasting position or size correction must be made **at a keyframe**. An edit on another frame is not registered in a saved layout and can disappear when you navigate. Return to the intended frame, add its keyframe, and repeat the edit.

Adding a new cell adds it to the saved layouts; it is not a way to make a cell exist only after a particular frame. Deleting a cell removes it from those layouts. Recheck new cells throughout the recording.

To remove a keyframe, return to its frame and toggle the diamond off. This removes that saved layout, which can change calculated cell positions on nearby frames. Review placement and rerun analysis afterward.

## Choose the analysis interval

Go to the first frame to measure and toggle the timeline's **analysis start** marker. Go to the last frame and toggle **analysis end**. Both marked frames are included; with no markers, the whole recording is analyzed.

These boundaries control where measurement and automatic freeze finding run. They do not replace keyframes or delete source frames. Changing them does not update existing results; choose **Analysis → Run Analysis** again.

See [Analysis and Results](Analysis-and-Results.md) for multiple intervals, incomplete start/end pairs, and detection settings.

## Compare images and inspect a cell

After analysis:

1. Press **A** and select a cell.
2. Open **Window → Grayscale Plot**.
3. Go to its freeze frame and use **Show Two Images** for the previous/current pair, or **Show Three Images** for previous/current/next.
4. Compare the solid brightness line and the images. The dashed line emphasizes brightness changes; it is not a second raw brightness measurement.

![Frame comparison with cell inspection and the grayscale plot](../resources/readme/2026-09-29/droplet-frame-comparison-native.png)

Use **Show One Image** to return to a single frame. Selection and editing stay on the current image. For navigation and the **Freeze frame only** list filter, see [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md).

## Correct freeze frames

Finish tuning and rerunning analysis before making manual corrections: **a rerun replaces them**.

### Add or remove an event at the current frame

1. Press **A** and select the cell or cells.
2. Go to the frame where they freeze.
3. Click the timeline's **flag**.

The flag adds an event at that frame to the selected cells. If all selected cells already have an event there, it removes that event instead. If only some have it, clicking adds it for the remaining cells. This changes freeze results; it is not a bookmark.

### Replace one cell's event list

1. Select exactly one cell in Cursor mode.
2. Enter its event frame in **Freeze Frame** under Tool Options and click **Set**.
3. For several events, enter comma-separated frame numbers, such as `40, 120`. Enter **None** to clear the list.
4. Check the event markers and images again.

Use the application's frame numbers, which start at **0**, rather than numbers embedded in filenames. The field replaces the selected cell's complete event list, so include every event you want to retain.

Manual edits update event results without measuring brightness again. Reimport temperature data afterward to rebuild the counts. Use **Edit → Undo** to recover an accidental correction.

## Finish in this order

1. Prepare the images, place cells, add any keyframes, and set analysis markers.
2. Assign samples and enter their details.
3. Run analysis, inspect the images, and tune detection.
4. Make final manual freeze corrections.
5. Import temperature data and check the grouped counts.
6. Save the session and export the tables.

Use **Save Session As...** and a new export filename or folder when keeping an earlier analysis. Continue with [Analysis and Results](Analysis-and-Results.md), [Temperature Import](Temperature-Import.md), or [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md).
