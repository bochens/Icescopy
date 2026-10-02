# Analysis and Results

**Analysis → Run Analysis** measures brightness inside each cell circle and finds candidate freeze events. It analyzes the cells in the session, not just the cell selected for inspection. Check detections against the images before using them to calculate freeze counts.

This page covers [analysis limits](#limit-analysis-with-start-and-end-markers), [the brightness plot](#understand-the-brightness-plot), [detector settings](#freeze-finding-controls), and [a tuning workflow](#review-and-tune-freeze-detection). For exported columns, see [Output Reference](Output-Reference.md).

## Prepare and run an analysis

1. Check that the recording is in acquisition order. Frame numbering starts at **0**.
2. Place each cell circle inside the droplet or well. Check its position at the beginning, middle, and end. Use [keyframes](Annotation-Workflow.md#follow-movement-with-keyframes) if cells move.
3. Finish any [image adjustments](Image-Editing.md). Exposure, contrast, Uniform Exposure, and crop affect the measured values; zoom and comparison layout do not.
4. Set start/end markers if only part of the recording should be analyzed.
5. Use **File → Save Session As...** if this run should remain separate from an earlier result.
6. Choose **Analysis → Run Analysis**. When it finishes, open the results tables and select cells to review their plots and freeze frames.

Analysis produces brightness measurements and freeze-event rows. Temperature matching is a later step: [import temperatures](Temperature-Import.md) after finishing detection review and manual corrections.

## Limit analysis with start and end markers

An **analysis interval** is a range of frames to measure and search for freezing. Both endpoints are included. Markers retain the recording and annotations; they do not delete excluded frames.

### Set an interval

1. Go to the first frame to include. Click the timeline button with the tooltip **Toggle analysis start marker at the current frame**.
2. Go to the last frame to include. Click **Toggle analysis end marker at the current frame**.
3. Repeat for other intervals if needed.
4. Choose **Analysis → Run Analysis** and check the ranges reported in the console.

Click a marker triangle to visit its frame. To remove a marker, click its start or end button again at that frame. To move a marker, remove it and add it at the new frame; marker triangles cannot be dragged.

**Changing markers does not recalculate existing results.** Run analysis again to apply the new ranges. The freeze flag is a different control: it changes freeze-event annotations rather than analysis limits.

### How markers pair

Prefer alternating starts and ends. The rules below apply after markers are put in frame order. Here, a 300-frame recording has frames 0–299.

| Markers | Frames analyzed |
| --- | --- |
| None | 0–299: the whole recording. |
| Start 20; end 100 | 20–100, including both frames. |
| Starts 20 and 150; ends 100 and 220 | 20–100 and 150–220: 152 frames in total. |
| End 100 only | 0–100: a missing first start uses frame 0. |
| Start 150 only | 150–299: a missing final end uses the last frame. |
| Starts 20 and 40; end 100 | 40–100: the nearest start before the end is used. |
| Start 20; ends 100 and 120 | 20–100: the extra end after the closed interval is ignored. |
| Start and end both at 50 | Frame 50 only. One brightness value cannot show a transition between frames. |

The start marker is processed before an end marker at the same frame. Out-of-range markers are ignored. If no valid markers remain, analysis uses the whole recording.

### What happens at boundaries and gaps

Automatic freeze detection runs separately in each interval. It does not compare the last measured frame before a skipped gap with the first frame after it. Within an interval, missing cell measurements also split detection into separate stretches; the app does not invent values across those gaps.

Choose boundaries that retain the before-and-after images of an event you want to detect. Front and tail extension repeat endpoint values for the calculation; they cannot reconstruct a transition that was not recorded or was excluded by a marker.

The measurement table retains one row per original frame. Excluded frames contain `nan` in their cell measurement columns. Temperature/count output can still contain those frames, because temperature import uses the full recording and the current event list. A manually added freeze event can also lie outside the automatic-analysis intervals.

At a boundary between adjacent intervals, such as 20–100 and 101–150, automatic detection still treats them separately. The plot can draw a continuous processed line because there is no missing frame between them. Inspect the images and event markers at such boundaries; do not interpret that line as a detection across the boundary.

## Understand the brightness plot

After analysis, press **A**, select a cell, and open **Window → Grayscale Plot** if needed. Use **Show Two Images** for the previous/current pair or **Show Three Images** for previous/current/next.

| Plot element | Meaning |
| --- | --- |
| Solid brightness line; left axis | Average brightness inside the cell circle at each measured frame. |
| Dashed convolution line; right axis | A processed signal that emphasizes changes in brightness. |
| Freeze-event lines | Frames currently marked as freeze events, including manual corrections. |
| Current-frame line | The frame displayed in the image viewer. |

### Brightness measurements

Brightness is measured on an 8-bit scale, from 0 to 255. It is an image value, not a temperature or a calibrated light measurement. The app uses the cell's position and radius at that frame, including changes between keyframes, and applies the image-edit settings before measuring.

For video, **Preferences → Analysis → Video Grayscale Source** offers **Converted grayscale** and **Video luma plane**. Converted grayscale derives brightness from color. Luma uses the video's stored brightness channel when available, with a fallback to converted grayscale. These choices can give different brightness values. Keep the choice consistent when comparing runs, and rerun analysis after changing it.

### The processed detection signal

**Convolution** here means comparing nearby brightness values with a pattern that has a positive side and a negative side. A steady level produces little response; a change produces a peak or dip. The comparison window and its ramp shape affect the response's height and width.

Darkening normally produces a dip, and brightening a peak. **Detect freezing from brightening** chooses which sign the detector accepts. The dashed line uses its own axis: a prominence of 60 is not a 60-level fall in the solid brightness line.

Once a peak or dip passes the detector settings, the app examines the original frame-to-frame brightness changes nearby to refine the event frame. It reports the frame after the selected change. This is why an event line need not lie at the exact center of the dashed peak or dip. Visual review is still needed to distinguish freezing from motion, lighting changes, or another cause.

## Freeze-finding controls

Open **Preferences → Analysis → Freeze Finding**. The table gives the defaults shipped in `resources/preferences.xml` with v2.3.8 and the ranges accepted by the dialog. Existing saved preferences can differ, so check the values shown in your installation. These are software defaults, not settings validated for every experiment.

| Control | Bundled default | Allowed input | Meaning |
| --- | --- | --- | --- |
| **Detect freezing from brightening** | Off | On or off | Off accepts darkening dips; on accepts brightening peaks. |
| **Peak Prominence** | 60.0 | 0.1–1,000,000.0 | Minimum height of an accepted peak or dip relative to its surroundings in the processed signal. |
| **Peak Width** | 5.0 | 0.1–100,000.0 frames | Minimum width of the processed peak or dip, measured at half its prominence. Fractional widths are allowed. |
| **Convolution Half Window Points** | 10 | 0–100,000 points | Sets half the comparison-pattern length. Positive values use a finite window; 0 uses the full processed stretch, including endpoint extension. |
| **Convolution Ramp Points** | 2 | 0–1,000 points | Number of transition points that soften the center of the comparison pattern. 0 gives a sharp step. |
| **Front Extension Points** | 20 | 0–1,000 points | Repeats the first measured brightness value before processing. |
| **Tail Extension Points** | 20 | 0–1,000 points | Repeats the last measured brightness value after processing. |

One point corresponds to one frame measurement. These controls use frames, not seconds: at a different frame rate, the same values describe a different duration. The peak width is the width of the processed response, not how long the cell remains frozen.

The half-window is limited internally to the length of the processed stretch. If that effective half-window is `N`, the pattern has `2N` points, and the ramp is limited to at most `2N − 2` points. A large entered ramp therefore may have no further effect on a short window. Changing the window or ramp can change both prominence and width; review those thresholds again afterward.

The same page includes **Cycle Warm-Up Hysteresis (°C)**, default **0.02**, range **0.00–10.00**. That setting affects cycle identification during temperature import, not freeze detection. See [repeated cycles](Temperature-Import.md#repeated-cooling-cycles).

## Review and tune freeze detection

Use the same representative cells after every change: a clear freeze, a weak freeze, a noisy cell, and a cell with no visible freeze. Selecting a cell changes the plot you inspect; it does not restrict the next analysis run to that cell.

1. **Check placement and images first.** Follow each circle through the recording. Correct movement, background inclusion, crop, or illumination problems before lowering detection thresholds.
2. **Check the direction of the change.** Compare before-and-after images. Set **Detect freezing from brightening** accordingly.
3. **Check the current processed response.** A clear image transition should have a recognizable dashed peak or dip of the expected sign. If it does, tune prominence and width before changing the comparison pattern.
4. **Adjust prominence.** Lower it for a visible but weak response; raise it when small fluctuations are being accepted. Keep checking the no-event cells.
5. **Adjust width.** Lower it if a real response is too narrow to pass. Raise it to reject brief noise, while checking that clear, rapid freezes remain detected.
6. **Adjust the half-window or ramp only when the response shape needs it.** Among positive half-window values, a larger value compares a longer span. A larger ramp softens the comparison pattern for gradual changes. Then revisit prominence and width.
7. **Check interval boundaries.** If a recorded event near the first or last frame is missed, examine the interval and corresponding extension value. Retain visible evidence on both sides of the event where available.
8. **Save Preferences and run analysis again after each change.** Saving can redraw the dashed line, but existing freeze-event markers remain from the previous run until analysis finishes.

Record the settings and the cells you checked so you can compare runs. Do not choose settings solely to obtain an expected number of frozen cells.

### Tuning by symptom

| Symptom | Action to try after checking the images | What to check in the next run |
| --- | --- | --- |
| Clear freezes are missed in most cells | Check brightening/darkening first; then check whether prominence or width excludes the visible response. | Clear events appear at the visible transitions, without many detections in stable cells. |
| A weak but visible transition is missed | Lower **Peak Prominence** in a small step. | The weak event appears and stable/noisy cells remain acceptable. |
| A real, rapid transition is missed | Lower **Peak Width**. | The narrow event appears; isolated image noise is not accepted. |
| Many small false events appear | Raise prominence; raise width if the unwanted responses are brief. | False events fall away while known true transitions remain. |
| A slow transition gives a poor response | Try a longer positive half-window or more ramp points, one at a time. | The response matches the visible change; recheck width and prominence. |
| Events cluster near a setup, movement, or warming segment | Fix cell placement or use analysis markers to exclude the unwanted segment. | Retained intervals still include the full transitions of interest. |
| A recorded event near an interval boundary is missed | Retain more neighboring frames if available; inspect front or tail extension. | A real before-and-after change is present; padding alone has not been mistaken for evidence. |
| Event frame differs from the dashed peak center | Compare neighboring images and the solid line; the app refines the event using brightness changes. | The reported frame is consistent with the visible onset; correct it manually if necessary. |

## Make final manual corrections

Finish automatic tuning first: another analysis run replaces manual freeze events.

- For the current frame, select one or more cells with **Cursor**, then click the timeline **flag**. It adds an event, or removes it if all selected cells already have an event at that frame.
- For one cell's complete list, edit **Freeze Frame** in Tool Options and click **Set**. Use zero-based frame numbers separated by commas, or `None` to clear the list.

These changes update the event table without recalculating brightness. They clear the temperature/count result, so reimport temperatures afterward. See [annotation controls](Annotation-Workflow.md#correct-freeze-frames) for the full procedure.

## Rerun, save, and export

| Change | Work needed before using updated counts |
| --- | --- |
| Cell position, radius, keyframes, image adjustments, or source order | Run analysis, review events, make final corrections, then reimport temperatures. |
| Analysis markers or freeze-finding settings | Run analysis, review events, make final corrections, then reimport temperatures. |
| Manual freeze events or cell-to-sample assignments | Reimport temperatures. New brightness measurements are not required. |
| Descriptive sample fields | Check the updated export information; no new image analysis is needed. |
| Zoom, number of displayed images, or plot colors | No new measurements are needed. |

**Rerunning replaces manual freeze corrections and clears temperature/count results.** Use separate session files when comparing an earlier reviewed result with a new run.

Save the session to retain annotations and result tables. Freeze-finding parameters are global Preferences; the session does not store a separate detector-settings snapshot. Record the detector values, video brightness source, and app version alongside the run if you need to reproduce it later.

Use **File → Output Results** to export the tables you need. See [Output Reference](Output-Reference.md) for exact columns, missing values, and the difference between frame rows, freeze events, and temperature cycles.
