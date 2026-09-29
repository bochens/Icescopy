# Image Editing

Open **Edit → Image Edit** to adjust exposure, contrast, cropping, or frame-to-frame brightness. These settings affect both the display and the brightness measurements. They are saved in the session; source images and videos stay unchanged.

Use **File → Save Session As...** before experimenting with an existing analysis.

## Exposure and contrast

1. Choose a representative frame and open **Image Edit**.
2. Adjust **Exposure** (overall brightness) or **Contrast** (the difference between light and dark values).
3. Check several frames, including before and after a freeze event.

Both settings apply to the whole recording. Sliders preview while dragged and apply when released. Numeric edits apply directly; there is no separate Apply button. Scrolling over a slider does not change it.

Set a control to zero to remove its adjustment, or use **Edit → Undo**.

## Read the histogram

The histogram counts pixels at each brightness value in the displayed image. A pile-up at the black or white end can indicate **clipping**: different brightness values have become the same black or white, losing detail.

Check the image as well as the histogram. Higher contrast can reveal a feature while hiding detail elsewhere. Always review freeze results after making image adjustments.

## Crop the view and measurement area

1. Click **Crop** in Image Edit to show the full image and crop box.
2. Drag the box to move it. Drag its resize handles to change its size, or its rotation handle to turn it.
3. Keep all cells needed for analysis inside the box.
4. Click **Apply** to use the crop, or **Cancel** to discard the preview.
5. Check the cell outlines again.

The crop affects the viewer, histogram, and brightness measurements. To restore the full image, finish or cancel any crop preview, then click **Reset**.

## Correct changes in illumination

**Uniform Exposure** adjusts each frame using the average brightness of a control area. It compares that area throughout the recording with the same area in your chosen reference frame.

1. Set exposure and contrast first.
2. Go to the frame to use as the brightness reference.
3. Under **Uniform Exposure**, click **Set Area**.
4. Move and resize the rectangle over a stable area that does not freeze or move out of view.
5. Click **Done**, then **Run**.
6. Check several frames and, after analysis, their brightness plots.

Choose the area carefully: its brightness controls the correction for the whole frame. A very dark area produces an error. This calculation reads the whole recording, including frames outside analysis markers.

If exposure, contrast, or the control area changes, run Uniform Exposure again. Its **Reset** button removes the correction and control area.

## Recalculate after image edits

Exposure, contrast, Uniform Exposure, and crop changes make existing analysis results out of date. After applying them:

1. Check cell placement and analysis intervals.
2. Choose **Analysis → Run Analysis**.
3. Review freeze events and repeat any manual corrections.
4. Import temperature data again to rebuild counts.
5. Save the session and export the tables. Use a new name or folder to preserve earlier results.

Zoom and the number of displayed frames do not affect measurements. See [Annotation Workflow](Annotation-Workflow.md) and [Analysis and Results](Analysis-and-Results.md) for next steps.
