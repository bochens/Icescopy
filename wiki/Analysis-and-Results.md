# Analysis and Results

**Analysis → Run Analysis** measures cell brightness and finds possible freeze events. Before running it, check frame order, cell placement, and image adjustments.

## Limit analysis with start and end markers

Use markers to analyze only part of a recording. Both marked frames are included. With no markers, analysis uses the whole recording.

1. Go to the first frame to include. Click the timeline button with the tooltip **Toggle analysis start marker at the current frame**.
2. Go to the last frame to include. Click **Toggle analysis end marker at the current frame**.
3. Repeat for other intervals, then choose **Analysis → Run Analysis**. Check the selected ranges in the console.

For example, starts at **20** and **150**, with ends at **100** and **220**, analyze frames **20–100** and **150–220**. Detection runs separately in each interval, so the brightness jump across the skipped gap cannot become a freeze event.

To remove a marker, click its timeline triangle to visit that frame, then click its start or end button. To move it, remove it and add it at the new frame. Markers cannot be dragged.

Prefer alternating start/end markers. If a pair is incomplete:

- If the first marker is an end, analysis starts at the recording's beginning.
- A final start without an end continues to the recording's end.
- Consecutive starts use the nearest start before the next end.
- Extra ends after a closed interval are ignored.

**Run analysis again after changing markers.** Existing results do not update automatically. Markers limit brightness measurement and automatic freeze detection; you can still add manual freeze events outside these intervals.

## Review and tune freeze detection

Select a cell and compare its neighboring images with the **Grayscale Plot**:

- The solid line shows average brightness.
- The dashed **convolution** line emphasizes brightness changes. Read it against the right-hand axis.
- The current-frame marker shows where the displayed image falls on the plot.

Open **Preferences → Analysis → Freeze Finding**. Start with the current settings and change one control at a time.

| Control | How to tune it |
| --- | --- |
| **Detect freezing from brightening** | Enable if freezing makes cells brighter; leave off if it makes them darker. Check this first when events are missed. |
| **Peak Prominence** | How much a dashed peak or dip stands out from its surroundings. Lower it to detect weaker events; raise it to reject false events. This is not the raw brightness change. |
| **Peak Width** | Minimum width of a dashed peak or dip, in frames. Raise it to reject brief noise; lower it for real, narrow responses. This is not the time a cell stays frozen. |
| **Convolution Half Window Points** | Sets the comparison span. Among positive values, increase it for a longer span or decrease it for a shorter one. **0** uses the whole analyzed interval. Recheck prominence and width after changing it. |
| **Convolution Ramp Points** | **0** looks for a sharp brightness step. Increase it gradually for a change spread over several frames. |
| **Front / Tail Extension Points** | Repeats the first or last brightness value for the calculation. Increase the relevant end if an event near the boundary is missed. This cannot recover an unrecorded transition. |

After each change:

1. **Save** preferences, then **Run Analysis**. Saving alone does not update freeze detections.
2. Compare the same clear, weak, and noisy cells, plus cells with no event.
3. Check for motion or lighting changes before lowering thresholds further.

The reported frame is refined using the original brightness changes, so it may not fall at the dashed peak or dip. Check the images before correcting it. Use the timeline flag to mark or clear events for selected cells, or edit **Freeze Frame** in Tool Options for one cell.

## Rerun, save, and export

Use **Save Session As...** before experimenting. Rerun after changing cell shapes or positions, keyframes, image adjustments, frame order, analysis intervals, or detection settings.

**Rerunning replaces manual freeze corrections and clears temperature/count results.** Finish tuning, make final corrections, then import temperature data again.

Editing sample details does not require new image analysis. If you change which sample a cell belongs to, reimport temperature data to rebuild the grouped counts.

| Result table | Contents |
| --- | --- |
| **Measurements** | Brightness and cell shape/position. Skipped frames keep their original numbering and contain `nan` (not measured). |
| **Freeze Events** | Detected or manually entered event frames for each cell. |
| **Freeze Count Timeseries** | Temperature-aligned **number total** and **number frozen** for each sample. Use these counts to calculate the fraction frozen. |

See [Temperature Import](Temperature-Import.md) for counts and [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for saving and CSV export.
