# Troubleshooting

Start with the symptom below. If the session is open, preserve it with **File → Save Session As...** before trying changes that replace measurements or events. Keep source recordings unchanged.

## Choose the right check

| Symptom | First check |
| --- | --- |
| Missing or moved images | [Source paths](#a-session-opens-without-its-images) |
| Save fails or a file is locked | [Save recovery](#cannot-save-a-session-preferences-or-csv) |
| Wrong, missing, or excessive freeze events | [Detection review](#freeze-finding-misses-events-or-calls-too-many) |
| Only part of the recording is analyzed | [Analysis markers](#analysis-covers-only-part-of-the-recording) |
| Temperatures or counts look wrong | [Temperature checks](#temperature-import-fails-or-temperatures-look-shifted) |
| A panel or control is unavailable | [Panel and selection checks](#a-result-panel-is-missing) |
| Startup or video loading fails | [Installation and video checks](#the-application-will-not-launch-or-open-a-video) |

## Cannot save a session, Preferences, or CSV

Read the dialog and its **Details** before closing anything.

1. If the file is open in a spreadsheet editor or another program, close that file there.
2. Check that the destination folder exists and is writable. A read-only external drive or protected application folder is not a suitable output location.
3. Choose **Retry** after resolving the cause.
4. For a session, choose **Save As** when offered to save into another writable folder.
5. If you must postpone saving, choose **Cancel** and keep Icescopy open. Cancel does not save the work.

On Windows, a permission dialog can offer **Allow App in Windows...**. This opens the Controlled folder access settings; Icescopy does not silently change Windows security policy. Review the blocked application and the path in **Details** before granting access. Save somewhere usable before any restart that a permission change requires.

For Preferences, a failed save leaves the dialog available for review/retry. If it reports invalid saved values, defaults may be shown; inspect them before saving. For multiple CSV exports, inspect the folder afterward: a failure does not imply that none of the selected files were written.

Related: [Sessions and saving](Sessions-Export-and-Preferences.md) and the dated [Windows save-recovery record](Windows-Save-Recovery.md).

## A session opens without its images

Sessions contain file references, not the recordings.

1. Confirm the original media still exists.
2. For an image sequence, use **File → Save Session As...** first if you need to retain the old paths.
3. Choose **File → Relink Images Folder...**.
4. Read the missing/ambiguous-file report and inspect several matched frames.
5. Save if the relink report says the updated session was not written.

Filenames must match. Duplicate filenames are not safe substitutes for a unique match. Relinking attempts to save updated paths automatically.

Image-folder relinking does not handle video. Restore the video at its recorded location before reopening the session. When transferring a session, send its media too and check the destination can open it.

## Images cannot be added to a video session

A session uses images or video; it cannot mix both source types. Save the current session and start a new one for the other type.

Select multiple video clips together through the video-loading workflow. You cannot append clips to an already loaded source or remove individual video frames as image-list entries. Review clip order and joins. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md).

## Changing Preferences did not change detected freeze frames

Saving Preferences does not rerun analysis.

1. Save a separate session if you want to retain the old result.
2. Choose **Analysis → Run Analysis**.
3. Check detections against the images.
4. Reimport temperatures and export new tables after final review.

Rerun after changing geometry, keyframes, crop, image adjustments, or detector settings. Display styling alone does not need a rerun. See [result dependencies](Concepts-and-Data-Flow.md#what-to-repeat-after-an-edit).

## Analysis covers only part of the recording

Inspect the analysis start/end markers. No markers means the full recording. Both endpoints of an interval are included.

Repeated starts use the last start before an end. Extra ends after a closed interval are ignored. Incomplete marker sets also have defined boundary behavior; read the [full pairing rules](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

Click a marker to navigate to its frame, then use the corresponding start/end toggle to remove it. Markers cannot be dragged. Rerun analysis after correcting intervals.

Manual freeze events can still exist outside the automatic-analysis intervals. An interval selects where automatic analysis works; it is not a filter that deletes every manually entered event.

## Manual freeze corrections disappeared

**Run Analysis** replaces freeze events with new detections. Make final manual corrections after tuning and the last automatic run, then save and reimport temperatures.

In Cursor mode, select one cell and use **Freeze Frame** to inspect/edit its events. Frame indices start at zero; comma-separated indices represent several events, and `None` clears them. Check the selected Cell ID before applying a correction.

Use separate session filenames if comparing automatic and manually reviewed results.

## Freeze finding misses events or calls too many

1. Select an affected cell and inspect it before, during, and after the suspected event.
2. Confirm the circle stays on the droplet. A change in background or a moving well can produce an apparent event.
3. Check whether freezing makes the image brighter or darker.
4. Open the Grayscale Plot and compare brightness with the dashed detection signal.
5. Adjust one detector setting, save Preferences, rerun, and inspect both a clear event and a suspected false event.

Peak prominence measures how strongly a signal peak stands above its surroundings; width measures its extent in frames. Neither is a temperature cutoff. Start with the [tuning sequence and symptom table](Analysis-and-Results.md#review-and-tune-freeze-detection), rather than changing several controls at once.

## Cells drift away from droplets

Use keyframes: frames where you save a corrected cell layout. The app calculates intermediate geometry; it does not recognize and track the droplet automatically.

Check the beginning, end, keyframes, and frames between them. Add corrections where the interpolation no longer fits, then rerun analysis. See [keyframe editing](Annotation-Workflow.md#follow-movement-with-keyframes).

## The flag and plot markers seem inconsistent

Check which cell is selected and which frame is displayed. The current-frame line follows navigation; freeze-event lines remain at that cell's assigned events. They should coincide only when you visit an event frame.

With multiple selected cells, inspect one cell at a time to remove ambiguity. Release 2.3.8 fixes marker alignment during plot rescaling and toolbar selection through accessibility controls. See [installation versions](Installation-and-Setup.md#download-the-app) if using an older build.

## Temperature import fails or temperatures look shifted

First check frame order, sample assignments, and the temperature record's time range.

| Importer | First checks |
| --- | --- |
| Standard CSV | First two columns are timestamp and temperature; correct units and formats; adequate unique timestamps |
| CSU | Expected `.dat` structure, picture names, and matching sample names |
| TAMU | Matching Linkam workbook and parseable image filename timestamps; valid calibration cell IDs if used |
| PKU | Original matching `.iml`, identical image-record count, and matching order |
| UTK | Exact `Time` and `PV(C)1` headers and a supported image/video timestamp source |

For Standard CSV, inspect the timestamp preview. Modification times can describe when files were copied instead of when images were captured. If image and logger timestamp styles differ, clear **Use image style for temperature timestamps** and choose each format.

Unix epoch timestamps count from `1970-01-01 00:00:00 UTC`; seconds and milliseconds are different units. Do not fix a time mismatch by guessing a temperature correction.

For video, use Standard CSV or UTK. Check start time, timing method, clip order, and clock agreement. Variable-frame-rate timing is not guaranteed exact by the current video implementation; verify timing against known events if precision matters.

For timestamp-based matching, inspect both matched and unmatched frames. A successful import is not proof that every frame has a valid temperature. See [Temperature Import](Temperature-Import.md).

## A cooling cycle restarts at the wrong time

Check **Reset After Warmed To (°C)** and **Cycle Warm-Up Hysteresis** against the actual warming stage. Hysteresis is the required warming rise used to avoid small fluctuations being treated as a new cycle.

Leave reset **Off** for a single-cycle analysis when no reset is intended. Reimport and inspect the cycle boundaries using the [implemented reset rules](Temperature-Import.md), rather than assuming the threshold alone specifies all behavior.

## The temperature table disappears or looks stale

Rerunning analysis or changing freeze events/sample assignments clears dependent imported counts. Reimport after reviewing the new events or groups.

Editing descriptive fields does not require brightness reanalysis. Save and export again, then check metadata and column labels. Global Preferences are separate from saved result tables; opening an old session does not prove its results were generated with the current detector settings.

## Export contains missing values or an unexpected cell total

Do not replace every `nan` with zero.

- In metadata, it usually means information was not supplied.
- In a temperature column, it can mean a frame could not be matched.
- In correction columns, it can mean that correction was not used.
- In the current reset-temperature metadata field, an exact numeric **0 °C** is exported as `nan`; cycle calculation still uses zero. Keep a separate record of that import choice.

Check Sample IDs, nonempty sample names, and the **Unassigned cells** group. In normal temperature-count grouping, samples with blank names can be omitted.

Blank correction subtracts the selected blanks' **frozen count at that row** from both the non-blank sample total and its frozen count, with bounds applied. It does not simply subtract the blanks' total number of cells. The `cell_number` metadata still describes the annotated sample group. See [Output Reference](Output-Reference.md) before comparing these quantities.

## A result panel is missing

Use **Window** to show the required panel, or **Reset Panel Layout** to restore the arrangement. Temperature-count results are available only after a successful import or when a loaded session contains that table.

If a tool is disabled, check that a session is active, frames are loaded, and the required cells/results exist. Only one editing tool and one comparison-image count should be selected at a time. See [Interface and Shortcuts](Interface-and-Shortcuts.md).

## The application will not launch or open a video

1. Confirm the download matches the operating system and processor.
2. Record the exact error message.
3. For a media failure, confirm the file exists, is readable, and can be opened by its normal video player.
4. For a source installation, run `icescopy-validate` and `icescopy --check-video-dependencies` in the intended environment.

A successful dependency import checks availability, not every codec or recording. Do not assume renaming a video's extension changes its format. See [Installation and Setup](Installation-and-Setup.md) and [Developer Guide](Developer-Guide.md).

## Report a problem

Include:

- Icescopy version and whether it is a packaged app or source checkout.
- Operating system and processor type.
- Images or video, file format, and approximate sequence size.
- Exact steps, expected behavior, and what happened.
- Error text or a short relevant Console excerpt.
- Whether it repeats in a new session and whether your original session is still intact.

For an analysis issue, include the affected frame indices, detector settings, and a description of the visible change. Review screenshots/logs before sharing: they can contain file paths, sample names, or session metadata. A small synthetic example is preferable when the original recording is private.

Open a [GitHub issue](https://github.com/bochens/Icescopy/issues). Keep the original files and a separate session copy so the report can be investigated without replacing your results.
