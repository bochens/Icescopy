# Edit Images

Use `Image Edit` to change the image data used for both display and analysis.

These edits apply to the whole image, not to individual cells.

## Available Controls

`Image Edit` includes:
- histogram
- exposure
- contrast
- crop
- uniform exposure

## Review The Histogram

Use the histogram to inspect grayscale distribution before or after editing.

Behavior:
- the full-image histogram is shown in gray
- if cells are selected, their histogram is overlaid separately
- if no cells are selected, no red overlay is shown

The histogram is a review tool. It does not change the image by itself.

Use it to answer:
- whether the full image is clipped too dark or too bright
- whether selected cells occupy a narrower grayscale range than the full image
- whether exposure or contrast changes are separating droplet signal from background

## Adjust Exposure

1. Switch to `Image Edit`.
2. Move the `Exposure` slider or edit the numeric value.

Use exposure when the full sequence is too dark or too bright.

Behavior:
- exposure changes are applied to display and analysis
- each committed change is undoable

## Adjust Contrast

1. Switch to `Image Edit`.
2. Move the `Contrast` slider or edit the numeric value.

Use contrast when wells or droplets are difficult to distinguish.

Behavior:
- contrast changes are applied to display and analysis
- each committed change is undoable

## Crop The Image

1. Switch to `Image Edit`.
2. Click `Crop`.
3. Adjust the crop box.
4. Click `Apply` or press `Enter`.

To discard the current crop draft:
1. Click `Cancel`.

To remove the committed crop:
1. Click `Reset`.

Behavior:
- crop does not start automatically when you enter `Image Edit`
- crop is committed only when you apply it
- crop changes are logged individually for undo and redo

## Run Uniform Exposure

Use uniform exposure when brightness drifts from frame to frame.

1. Switch to `Image Edit`.
2. Set the uniform-exposure area on a stable reference region.
3. Run uniform exposure.

Choose an area that is:
- stable across frames
- representative of the illumination you want to normalize
- not dominated by changing ice or fluid behavior

Behavior:
- correction is per image
- correction affects display and grayscale analysis
- the current frame is used as the reference frame
- `Run` and `Reset` are both undoable

Use a control area that is:
- stable across the sequence
- representative of the illumination drift
- not dominated by changing freezing behavior

## Select Cells During Image Edit

You can still select cells while `Image Edit` is active.

Use that when you want to:
- compare histograms for selected cells
- inspect a subset of the image while staying in image-edit mode

Exception:
- while you are actively manipulating a crop draft, crop takes priority and selection is suppressed

## What Image Edit Affects

Image-edit settings affect:
- image display
- grayscale analysis
- temperature-sync outputs that depend on the current freeze results

Image Edit does not move cells. Cell geometry still belongs to the annotation tools and keyframe workflow.

Practical rule:
- use `Image Edit` to improve signal quality
- use annotation tools and keyframes to improve geometric tracking
- these are separate workflows and should stay separate

## Undo And Redo

These image-edit actions are tracked individually:
- exposure changes
- contrast changes
- run uniform exposure
- crop apply
- crop reset
- uniform exposure reset

Current behavior:
- image-edit undo and redo preserve the existing results tables in the session state
- preserved tables are not automatically recomputed
- if the edits change the interpretation of freezing, run analysis again

## Next Step

After image edits are in place, continue with [Run analysis, review the Grayscale Plot, and inspect results](</Users/C832577250/Project/Icescopy/manual/04-analysis-and-results.md>).
