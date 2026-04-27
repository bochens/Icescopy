# Annotation Workflow

This page explains how to annotate cells, manage keyframes, and assign samples.

## Choose the right mode

Use the cursor tool when you need to:

- select cells
- inspect cells
- edit freeze frames
- assign samples
- create a simple sample assignment during annotation

Use the add or grid tools when you need to:

- place one cell at a time
- lay out many cells quickly in a regular pattern

Use edit modes when you need to:

- correct an existing placement
- refine a group
- update a keyframed layout

## Add one cell

Use single-cell placement when:

- the layout is irregular
- the number of cells is small
- you need exact manual control

Typical workflow:

1. Activate the single-cell tool.
2. Set the radius in the tool options or status bar.
3. Click the center of the droplet or well.
4. Repeat for the remaining cells.

## Add a grid

Use grid placement when:

- droplets or wells follow a regular pattern
- row and column counts are known
- you want faster initial placement

Typical workflow:

1. Activate the grid tool.
2. Set rows, columns, horizontal pitch, vertical pitch, and rotation.
3. Position the preview over the image.
4. Commit the grid once it matches the array.

## Edit existing cells

Use edit mode to correct:

- position
- radius
- grid pitch
- grid rotation

The main rule is to edit the minimum number of frames necessary.
If the layout only changes at certain points in the run, use keyframes instead of manually fixing every frame.

## Use keyframes when cells move

Keyframes are the main way to manage motion across a sequence.

Use them when:

- the field drifts
- the camera or stage shifts
- the array geometry changes across time

The intended workflow is:

1. mark a keyframe at a frame with a known good layout
2. adjust cells there
3. add another keyframe later if the layout changes again

Icescopy interpolates between keyframes.

This is why the app uses a global keyframe model instead of per-cell tracks.
The motion source is usually global drift, not an independent animation per cell.

## Use flags during review

Flags are review markers.
They are useful when:

- you want to revisit a frame
- you see an ambiguous event
- you want to compare a frame during QC

Flags do not change analysis by themselves.

## Delete cells

Delete only when the ROI is truly wrong or no longer needed.

If you only need to correct a position:

- edit it
- do not delete and recreate it unless the ID continuity no longer matters

## Edit freeze frames

Freeze frames can be corrected manually from the cursor/inspection workflow.

Use that when:

- the automatic detector missed a real event
- the automatic detector chose the wrong frame
- a special case needs a manual override

## Assign samples

Assign samples when the array contains multiple experimental groups.

Sample assignment affects:

- grouped output summaries
- temperature import grouping
- interpretation of results tables

Sample assignment is done on cells.
Sample metadata is edited in the sample catalog.
Do not use the cursor tool as the main metadata editor.

## Use the sample catalog

The sample catalog is the canonical place to edit sample metadata.
It uses stable sample IDs internally and shows each sample as an expandable tree entry.

Use it to keep exports readable and to avoid treating numeric sample IDs as the only user-facing identifiers.

Editable fields are:

- sample name
- sample long name
- sampling site
- collection start
- collection end
- sample type
- dilution factor
- air volume
- filter fraction used
- suspension volume
- dry mass

Collection start and collection end use `YYYY-MM-DD HH:MM:SS`.
The sample type can be `air`, `soil`, or `other`.
Type-specific fields that do not apply are disabled in the tree.

For export:

- `sample_id` is the stable grouping key
- `sample_name` is the displayed name
- `cell_number` is the number of cells assigned to that sample
- missing metadata is written as `nan`

Changing sample names, long names, sample type, collection times, or numeric sample metadata does not rerun grayscale analysis.
Changing which cells belong to a sample changes grouped temperature output, so reimport temperature data after sample assignment changes.

Sample IDs are reused from the lowest available deleted sample number.
For example, if sample `0` is deleted, the next new sample can use `0` again.

## Use the cells panel

The cells panel is the structural summary of current annotation state.

Use it to review:

- which cells exist
- which sample each cell belongs to
- which freeze frames are assigned

## Recommended order

Use this order for the least rework:

1. place cells
2. correct geometry
3. add keyframes if the layout moves
4. assign samples
5. edit sample catalog metadata
6. run analysis
7. review freeze frames
8. import temperature data if needed
