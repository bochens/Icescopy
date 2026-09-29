# Analysis and Results

**Analysis → Run Analysis** measures cell brightness and finds possible freeze events. First check frame order, cell placement, and image adjustments.

## Limit analysis with start and end markers

Start and end markers define inclusive ranges: both marked frames are measured. Without markers, analysis uses the entire recording.

1. Navigate to the first frame you want measured. Click the timeline button whose tooltip says **Toggle analysis start marker at the current frame**.
2. Navigate to the last frame and click **Toggle analysis end marker at the current frame**.
3. Repeat for additional ranges, then choose **Analysis → Run Analysis**. The console reports the selected ranges.

For example, starts at **20** and **150**, with ends at **100** and **220**, analyze frames **20–100** and **150–220**. The gap is skipped. Detection runs separately within each range; the brightness jump across the gap is not treated as freezing.

Click a timeline triangle to visit its frame, then its corresponding button to remove it. To move a marker, remove it and add one at the new frame. Markers cannot be dragged.

If the first marker is an end, analysis starts at the recording's beginning; a final start continues to its end. Consecutive starts use the nearest start before the next end. Extra ends after a closed range are ignored. Prefer alternating start/end markers.

Changing markers does not recalculate existing results. Run analysis again. These ranges limit automatic measurement and detection; they do not prevent manual freeze annotations elsewhere.

## Review and tune freeze detection

Select a cell and compare neighboring images with its **Grayscale Plot**. The solid line shows average brightness. The dashed **convolution** line is a calculated response that emphasizes brightness changes, read against the right-hand axis. The current-frame marker connects the plot to the displayed image.

Open **Preferences → Analysis → Freeze Finding**. Start with the current settings and change one control at a time:

| Control | How to tune it |
| --- | --- |
| **Detect freezing from brightening** | Enable for brightening; leave off for darkening. Check this first for missed events. |
| **Peak Prominence** | How strongly the dashed peak or dip stands out. Lower for weaker real events; raise to reject false detections. Not the raw brightness change. |
| **Peak Width** | Minimum dashed-signal width in frames. Raise to reject brief noise; lower for real narrow responses. Not how long a cell stays frozen. |
| **Convolution Half Window Points** | Positive values set a shorter or longer comparison span; **0** uses the whole analyzed segment. Recheck prominence and width after changing it. |
| **Convolution Ramp Points** | **0** uses a sharp brightness step. Increase gradually for a sloped change across several frames. |
| **Front / Tail Extension Points** | Repeat the first or last brightness value during calculation. Increase the relevant end for missed boundary events. This cannot recover an unrecorded transition. |

**Save** preferences, then **Run Analysis**. Saving preferences alone does not update detected freeze frames. Compare the same clear, weak, and noisy cells, including cells with no event. Check image motion and lighting changes before lowering thresholds further.

The reported frame is refined from the original brightness changes; it need not match the dashed peak or dip. Use the timeline flag button to mark or clear events for selected cells, or edit **Freeze Frame** in Tool Options for one selected cell.

## Rerun, save, and export

Use **Save Session As...** before experimenting. Rerun after changing cell geometry, cell positions saved at specific frames (keyframes), image adjustments, frame order, analysis ranges, or detection settings. Rerunning replaces manual freeze corrections and clears temperature/count results. Make final corrections after tuning, then reimport temperature data.

Sample metadata edits do not require image analysis. Changing cell-to-sample assignments requires temperature reimport to rebuild grouped counts.

The result tables contain:

- **Measurements:** brightness and cell geometry; excluded frames keep their original numbering with `nan` (not measured).
- **Freeze Events:** detected or manually edited event frames for each cell.
- **Freeze Count Timeseries:** temperature-aligned `number total` and `number frozen` for each sample. Calculate fraction frozen downstream.

See [Temperature Import](Temperature-Import.md) for counts and corrections, and [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for saving and CSV export.
