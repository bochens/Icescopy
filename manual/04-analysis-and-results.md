# Run Analysis, Review The Grayscale Plot, And Inspect Results

Use this page to run grayscale analysis, inspect result tables, and export data.

## Run Analysis

1. Load images.
2. Annotate cells.
3. Apply any required image edits.
4. Open `Analysis -> Run Analysis`.

Result:
- the app processes the loaded image sequence frame by frame
- result tables are refreshed from the current session state

Analysis uses:
- cell positions
- sample assignments
- image-edit adjustments

If cells move across the sequence:
1. Add keyframes before running analysis.
2. Adjust cell geometry at the key frames.
3. Let the app interpolate between them.

If keyframes are not used, analysis uses the current static cell geometry for all frames.

Before you run:
- confirm image order
- confirm circles are centered
- add keyframes if the layout drifts
- apply any exposure, contrast, crop, or uniform-exposure edits first
- save the session if the run represents a major milestone

## Know What Invalidates Analysis

These operations invalidate analysis results:
- adding images
- removing images
- sorting or reordering images

These operations can preserve existing tables in session state, but do not recompute them automatically:
- cell edits
- image edits
- sample edits

Practical rule:
- if the interpretation of the data changed, run analysis again

## Review Result Tables

The `Results Tables` dock contains three tabs:
- `Measurements`
- `Freeze Events`
- `Temperature Sync`

Use them by purpose:
- `Measurements` for frame-by-frame grayscale and geometry output
- `Freeze Events` for per-cell event indexing
- `Temperature Sync` for time and temperature alignment after external import

## Measurements

Use `Measurements` in `Results Tables` for per-frame grayscale values.

This table is the main frame-based output from analysis.

Current column structure:
- `file_name`
- `flag_state`
- `cell_<id>_grayscale`
- `cell_<id>_circle_x`
- `cell_<id>_circle_y`
- `cell_<id>_circle_radius`

Typical uses:
- inspect grayscale values by frame
- review flagged frames
- export frame-based data to CSV

Important:
- this table does not depend on EXIF time
- time and temperature are added later through temperature import

## Freeze Events

Use `Freeze Events` to review the image index where freezing was recorded.

Current columns:
- `cell`
- `image_index`
- `image_name`

This table is intentionally image-based. It does not mix in external time or temperature assumptions.

Manual freeze-frame edits also update this table.

## Temperature Sync

Use `Temperature Sync` after a successful temperature import.

This table combines:
- image-derived freeze information
- external time and temperature data

Do not expect this tab to appear before temperature import.

## Review The Grayscale Plot

Use the separate `Grayscale Plot` dock to inspect traces across frames.

Typical checks:
- confirm that the grayscale trace looks reasonable
- compare selected cells
- inspect the convolution trace against the raw trace
- verify freeze events against the image sequence

Use the plot for two different tasks:
- checking whether the grayscale signal itself is sensible
- checking whether the detector is calling the right freezing frames

Read the traces this way:
- the solid trace is the raw mean grayscale through time
- the dashed trace is the convolution-based edge-enhanced signal used to find sudden drops
- a strong freezing event usually looks like a clear grayscale drop with a corresponding response in the dashed trace

Use the plot together with the image viewer:
1. Find a suspicious dip or peak in the plot.
2. Scrub to the corresponding image frames.
3. Decide whether the detector is responding to real freezing, noise, blur, or drift.

## Tune Freeze Finding

Freeze-finding parameters live in:
- `Preferences -> Analysis -> Freeze Finding`

Use the `Grayscale Plot` and the `Freeze Events` table together when tuning.

Recommended order:
1. Start with `Peak Width`.
2. Then adjust `Peak Prominence`.
3. Only after that, adjust the convolution settings if needed.

Parameter guide:
- `Peak Width`
  Increase it to reject narrow noisy dips.
  Decrease it if real freezing events are being missed because the detected dip is too narrow.
- `Peak Prominence`
  Increase it to require a stronger event.
  Decrease it if obvious freezing dips are not being accepted.
- `Tail Extension Points`
  Increase it if freezing happens near the end of the run and end-of-trace events are being missed.
- `Convolution Half Window Points`
  Controls the width of the step kernel used to build the dashed convolution trace.
  Larger values make the detector respond to broader changes.
  `0` keeps the original whole-trace window behavior.
- `Convolution Ramp Points`
  Softens the step kernel near the center.
  Increase it if the real grayscale drop is gradual or sloped rather than abrupt.

Tune by failure mode:
- too many false events:
  increase `Peak Prominence` first, then increase `Peak Width`
- real freezing missed:
  decrease `Peak Prominence` first, then decrease `Peak Width`
- late-run events missed near the end:
  increase `Tail Extension Points`
- dashed trace reacts to very broad trends instead of sharp drops:
  reduce `Convolution Half Window Points`
- dashed trace is too sharp for a gradual freeze transition:
  increase `Convolution Ramp Points`

Practical workflow:
1. Run analysis with the current settings.
2. Inspect the raw trace and dashed convolution trace in `Grayscale Plot`.
3. Compare reported freeze events with the image sequence.
4. Adjust one parameter at a time.
5. Run analysis again and compare the result.

Do not tune by table output alone. The plot is the faster way to see whether the convolution trace is reacting to real freezing or to noise.

Use a controlled tuning process:
1. Pick one representative cell that behaves clearly.
2. Tune one parameter at a time.
3. Re-run analysis after each change.
4. Check a few easy cells and a few difficult cells before accepting the new settings.

## Export Result Tables

1. Open `File -> Output Results`.
2. Choose `Grayscale CSV...`, `Freeze CSV...`, `Temperature CSV...`, or `All CSVs...`.
3. Save the CSV file.

Available exports depend on the current session contents.

## Interpretation Notes

Use these assumptions when reading the tables:
- grayscale analysis is frame-based
- image-edit settings affect analysis, not just display
- temperature-aware interpretation belongs in the `Temperature Sync` table, not in the core frame table

## Next Step

If you need time and temperature alignment, continue with [Import temperature data](</Users/C832577250/Project/Icescopy/manual/05-temperature-import.md>).
