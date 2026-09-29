# Image Editing

Open **Edit → Image Edit** to inspect the histogram and change exposure, contrast, crop, or frame-to-frame brightness correction. These settings affect the images used for grayscale measurements as well as the display. They are stored in the session; the source image and video files are not rewritten.

Use **File → Save Session As...** before trying different image preparation on an existing analysis.

## Exposure and contrast

1. Choose a representative frame and open **Image Edit**.
2. Adjust **Exposure** or **Contrast** with the slider or numeric field.
3. Check several frames, including frames before and after a freezing event.

Exposure changes overall brightness; contrast changes the separation between light and dark values. Both settings apply across the recording. A slider previews the change while dragged and commits it when released; numeric edits apply directly. There is no separate Apply button for these two controls.

Set a control back to zero to remove its adjustment, or use **Edit → Undo**. Mouse-wheel changes on the exposure and contrast sliders are blocked to avoid accidental edits while scrolling the panel.

## Read the histogram

The histogram shows how many pixels have each brightness value in the current displayed image. A concentration at the darkest or brightest end can indicate clipping: different original values have been pushed to the same black or white value, losing detail.

Use the histogram together with the image and cell outlines. Increasing contrast can make a feature easier to see while also losing information elsewhere. A clearer-looking image alone does not establish a better freeze result.

## Crop the view and measurement area

1. In **Image Edit**, click **Crop**. The full image and an adjustable crop box are shown.
2. Drag the box to move it, its resize handles to change its size, or its rotation handle to turn it.
3. Check that all cells needed for analysis remain inside the box.
4. Click **Apply** to commit the crop. Click **Cancel** to discard the current crop preview.

The committed crop affects the viewer, histogram, and grayscale sampling. Check the cell outlines again after applying it.

**Reset** restores the full image when no crop preview is active. Finish or cancel the preview before using Reset.

## Correct changes in illumination

**Uniform Exposure** calculates a brightness correction for each frame from a selected control area. It uses the current frame as the reference and measures the mean brightness in that same area throughout the recording.

1. Navigate to the frame to use as the brightness reference.
2. Under **Uniform Exposure**, click **Set Area**.
3. Move and resize the control rectangle over an area expected to remain stable. Avoid an area whose brightness changes because it freezes or moves out of view.
4. Click **Done**, then **Run**.
5. Inspect several frames and the grayscale traces after analysis. Use the Uniform Exposure **Reset** button to remove this correction and its control area.

Run reads the whole recording, including frames outside any marked analysis interval. A very dark control area cannot provide a usable correction and produces an error. The reference area determines the correction applied to the whole frame, so its choice matters.

Set exposure and contrast before running Uniform Exposure. If those settings or the control area change, run Uniform Exposure again to calculate corrections for the new choices.

## Recalculate after image edits

Committed exposure, contrast, uniform exposure, and crop changes invalidate existing image-analysis results. To update the results:

1. Confirm the cell placement and analysis interval.
2. Choose **Analysis → Run Analysis**.
3. Review the new freeze events and repeat any needed manual corrections.
4. Import temperature data again to rebuild freeze counts.
5. Save the session and export the updated tables under a new name or into a new folder if earlier outputs must be kept.

Changing only zoom or the number of displayed frames does not change the measurements. See [Annotation workflow](Annotation-Workflow.md) and [Analysis and results](Analysis-and-Results.md) for the next steps.
