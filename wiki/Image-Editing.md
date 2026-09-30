# Image Editing

[User guide](Home.md) · [Quick start](Quick-Start.md) · [Annotation workflow](Annotation-Workflow.md)

Use **Edit → Image Edit** to adjust exposure, contrast, cropping, or frame-to-frame brightness. The controls appear in **Tool Options**, with a histogram showing the image's brightness distribution.

**These adjustments affect the images used for analysis as well as the display.** They are stored in the session; the original image and video files are not rewritten. Image zoom, panning, and showing neighboring frames only change the view.

In the two- or three-image view, all panes share the same image-edit settings. Exposure and contrast update every pane; crop and Uniform Exposure control areas can be adjusted in any available pane. Pan and zoom stay synchronized. Each pane shows its own frame’s cell positions and sizes, including any movement defined by keyframes, and keeps the circles aligned after cropping. Use the **Current** pane for cell selection and editing; the histogram also describes the current frame.

## Before you adjust an image

1. Load and check the [recording order](Loading-and-Reviewing-Frames.md).
2. Choose **File → Save Session As...** if an existing analysis must be kept.
3. Find representative frames: before freezing, after freezing, and any with different illumination.
4. Open **Edit → Image Edit**. If its controls are hidden, open **Window → Tool Options**.

Use the least adjustment needed for the task. A brighter or more striking image is not by itself evidence of better freeze detection. Check cell brightness traces and visible events after the changes.

## Exposure and contrast

**Exposure** multiplies brightness. Its unit is a **stop**: +1 approximately doubles pixel values and −1 halves them, before values are clipped to the available range. The control runs from −4 to +4; **0** applies no exposure adjustment.

**Contrast** spreads values away from, or draws them toward, the middle brightness level. Positive values increase contrast; negative values reduce it; **0** applies no contrast adjustment. The control runs from −100 to +100. At −100, the image loses brightness variation, so it cannot retain a useful freeze signal.

To adjust the recording:

1. Start on a representative frame.
2. Change **Exposure** with the slider or numeric field.
3. Check both light and dark regions, then adjust **Contrast** if needed.
4. Step to the other representative frames. Confirm that droplets or wells remain visible and their brightness changes have not flattened at black or white.
5. Return a control to **0** if its adjustment is not useful.

Both controls apply to the whole recording. Sliders preview while dragged and apply when released. Numeric edits apply directly; there is no separate Apply button for exposure or contrast. Scrolling over these sliders does not change them.

Use **Edit → Undo** to reverse a committed adjustment. If you are also using Uniform Exposure, set the global exposure and contrast first, then calculate that correction.

## Read the histogram

A **histogram** counts pixels at each brightness value, from **0** (black) to **255** (white). Dark values are on the left and bright values on the right. The gray bars describe the currently displayed image, including applied image adjustments and crop.

A concentration at the darkest or brightest end can indicate **clipping**: originally different values have become the same black or white value. Clipping loses detail and can hide a freeze-related change.

To inspect the measured regions more closely:

1. Select one or more cells.
2. Open **Image Edit**, or select cells while using that tool.
3. Compare the red histogram overlay with the gray whole-image histogram.
4. Check where the selected cells lie along the dark-to-bright axis, especially before and after freezing.

The red overlay describes pixels inside the selected circles. Its vertical scale is fitted separately from the whole-image histogram, so compare the **brightness positions and shapes**, not the heights of red and gray bars as if they were equal pixel counts.

An empty histogram can mean no readable frame is loaded. If the red overlay is absent, check that cells are selected and their circles overlap the displayed image.

## Crop the view and measurement area

A crop uses one rectangular area, optionally rotated, throughout the recording. It changes the displayed image and the area available for brightness measurement. It does not remove frames.

1. In Image Edit, click **Crop**. The full image and an adjustable crop box appear in each available pane.
2. In any pane, drag inside the box to move it. Drag its resize handles to change its size, or its rotation handle to turn it. The crop boxes move together.
3. Keep every cell needed for analysis inside the box. Allow for movement later in the recording.
4. Click **Apply**. With the image viewer focused, Enter also applies the crop.
5. Inspect the first, middle, and last analyzed frames and check their cell outlines.

While the crop preview is active, the **Crop** button changes to **Cancel**. Cancel discards that draft and restores the previously committed view. Starting another crop lets you revise the existing crop.

To restore the full image, finish or cancel the preview, then click the Crop section's **Reset**. Reset is disabled while a crop preview is active. Use **Edit → Undo** if you want to recover the previous committed crop.

Cell coordinates continue to refer to the source image; Icescopy maps their outlines into the cropped view. Still check the outlines after applying or resetting a crop. A circle partly outside the measurement area is not the same measurement region as before.

## Correct changes in illumination

**Uniform Exposure** uses a stable **control area** to estimate a brightness correction for each frame. It compares the average brightness in that same area with its brightness in the frame selected when you click **Run**. The resulting correction applies to the whole frame.

Use it for changes shared across the image, such as gradual illumination drift. It cannot distinguish illumination changes from real changes inside the chosen control area.

### Choose a control area

Choose a region that stays visible and should not change during the recording. Avoid a droplet or well that freezes, moving objects, changing reflections, and regions that become nearly black. Otherwise, the correction can transfer the control area's own changes to every measured cell.

Check the area across the full recording, including frames outside your analysis start/end markers. Uniform Exposure reads all frames.

### Calculate and inspect the correction

1. Set the global **Exposure** and **Contrast**.
2. Go to a frame whose brightness you want to use as the reference. This is the frame shown in the **Current** pane.
3. Under **Uniform Exposure**, click **Set Area**.
4. Move and resize the rectangle over the control area in any available pane. The same area appears in the other panes.
5. Click **Done**.
6. Confirm that the **Current** frame is still the intended reference, then click **Run**. Adjusting the area in a neighboring pane does not change the reference frame.
7. Wait for the calculation. The app visits frames during processing and returns to the reference frame afterward.
8. Inspect several frames, then run analysis and compare the cell brightness traces with the visible freeze events.

The correction is based on a ratio of control-area brightness values and is limited to four exposure stops in either direction. It does not recover detail already lost through clipping. If the reference area or that area in any other frame is too dark, the app reports an error instead of applying a newly calculated correction.

### Revise or remove the correction

- To change the control area, use **Set Area**, adjust it, click **Done**, and **Run** again.
- To change the reference frame, navigate to the new frame and **Run** again.
- After changing global exposure or contrast, **Run** again so the correction matches those settings.
- To remove the correction and its control area, use **Reset** in the **Uniform Exposure** section.

Changing the area alone does not calculate a new correction. Use the Uniform Exposure Run button, then rerun image analysis. The separate **Analysis → Run Analysis** command measures cells and finds freezing; it does not choose a new illumination reference for you.

## Recalculate after image edits

Applying exposure, contrast, Uniform Exposure, or crop changes makes existing analysis results out of date. To finish:

1. Check cell placement, [keyframes](Annotation-Workflow.md#follow-movement-with-keyframes), and analysis start/end markers.
2. Choose **Analysis → Run Analysis**.
3. Review the detected events against the images and tune detection if needed.
4. Make manual freeze corrections after the final rerun.
5. Import temperature data again to rebuild counts.
6. Save the session and export to a new filename or folder when keeping earlier results.

Rerunning analysis replaces manual freeze corrections. Save the earlier session first if you need to compare two image-preparation choices.

## If the result looks wrong

| Symptom | What to check |
| --- | --- |
| Many regions become solid black or white | Reduce exposure or contrast and inspect the histogram for clipping. |
| The crop cuts off cells later in the recording | Enlarge or reset the crop, inspect cell movement, and rerun analysis. |
| Uniform Exposure creates a jump across all cells | Check whether the control area itself freezes, moves, or changes reflection. Reset the correction or choose a stable area and calculate it again. |
| Uniform Exposure reports a dark area | Inspect that area at the reported frame. Choose a brighter stable area; changing analysis markers will not exclude it from this calculation. |
| Circles drift while brightness remains reasonable | Correct their positions with keyframes. An illumination correction does not track cell movement. |
| The image looks better but detections look worse | Compare the same cells and visible events. Remove unnecessary adjustments and follow the [freeze-finding tuning guide](Analysis-and-Results.md#review-and-tune-freeze-detection). |

Continue with [Annotation Workflow](Annotation-Workflow.md) for cell placement, [Analysis and Results](Analysis-and-Results.md) for detection, or [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for saving the completed analysis.
