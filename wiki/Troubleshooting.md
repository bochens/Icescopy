# Troubleshooting

Find your symptom below. Use **File → Save Session As...** first if you want to preserve the current result.

## A session opens without its images

Sessions store paths to images and videos, not the files themselves.

For images, choose **File → Relink Images Folder...** and select their new folder. Filenames must match the originals. Check the report for missing files or duplicate matches. Relinking attempts to save the updated paths, so use **Save Session As...** first to preserve the original session.

For video, restore the file at its saved location and reopen the session. **Relink Images Folder...** works only for images. When sharing a session, include the source media and check that the recipient can open it.

## Images cannot be added to a video session

A session can use images or video, but cannot mix them. Save the current session, then start a new one for the other source type.

For multiple clips, use the video loading workflow and check their order. Image-folder relinking and removing individual frames are unavailable for video. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md).

## Changing Preferences did not change detected freeze frames

Saving Preferences does not rerun analysis. Choose **Analysis → Run Analysis**, check the new detections, then reimport temperatures and export updated tables.

Rerun analysis after changing circles, keyframes, crop, image adjustments, or detection settings. Descriptive sample fields do not need a new analysis run; changing sample assignments requires temperature reimport.

## Analysis covers only part of the recording

Check **Analysis Start** and **Analysis End** markers. Analysis includes both endpoint frames and skips gaps between ranges. A missing start uses the first frame; a missing end uses the last. With no markers, analysis covers the full recording.

If there are several starts in a row, the last one before the next end is used. Extra ends after a closed range are ignored. Click a marker triangle to visit its frame, then use the corresponding marker button to remove it. Markers cannot be dragged. Run analysis after correcting the ranges.

Manually marked freeze events can still exist outside these ranges. See [Limit Analysis with Start and End Markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

## Manual freeze corrections disappeared

**Run Analysis** replaces freeze events with new detections. Make manual corrections after the final run, then save the session and reimport temperatures. Save separate sessions if you need to compare results before and after a rerun.

To edit events, select a cell in Cursor mode and use **Freeze Frame**. Enter frame numbers separated by commas, or `None` to clear them. Numbering starts at zero. Check the selected cell and image before applying a correction.

## Freeze finding misses events or calls too many

Select a cell and compare its images with the grayscale plot, which shows average brightness inside the circle. Check that the circle stays on the droplet throughout the recording.

Check whether freezing brightens or darkens the droplet. Then adjust peak width (the width of a peak in the detection signal, measured in frames) or prominence (the peak's height relative to its surroundings). Change one setting at a time, save Preferences, and rerun analysis. Check several clear freezes and suspected false detections.

See [Review and Tune Freeze Detection](Analysis-and-Results.md#review-and-tune-freeze-detection) for the controls and tuning steps.

## Cells drift away from droplets

Add keyframes: frames where you save a cell layout. Icescopy calculates cell positions between them. Check the start, end, and frames in between, then rerun analysis. See [Follow Movement with Keyframes](Annotation-Workflow.md#follow-movement-with-keyframes).

## Temperature import fails or temperatures look shifted

Check frame order, the temperature record's time range, and sample assignments. Then check the importer:

| Importer | First checks |
|---|---|
| Standard CSV | Timestamp is column 1 and temperature is column 2; at least two rows; no duplicate timestamps; correct unit and timestamp styles |
| CSU | Matching picture names and `Sample_...` names; original `.dat` contains `Avg_Temp` and `Picture` |
| TAMU | Matching Linkam workbook, parseable PNG filename timestamps, and correct calibration cell IDs if calibration is used |
| PKU | Matching `.iml`, identical image-record count, and the same image order |
| UTK | Exact `Time` and `PV(C)1` headers; parseable image names or a recognized start timestamp in the first video filename |

For Standard CSV, check the timestamp preview. File modification times may record when images were copied, not taken. If the image and CSV formats differ, clear **Use image style for temperature timestamps** and choose each format. For Unix epoch timestamps (time since `1970-01-01 00:00:00 UTC`), select seconds or milliseconds explicitly.

For video, use Standard CSV or UTK; the other importers require images. Check the start time, timing method, clip order, and whether the camera and temperature logger clocks agree.

For imports that match timestamps, at least one frame must fall within the temperature record. If only some match, inspect the unmatched frames before using the output. See [Temperature Import](Temperature-Import.md) for formats and steps.

## A cooling cycle restarts at the wrong time

Check **Reset After Warmed To (°C)** against the warming stage in the temperature record. Counts restart when the temperature warms back to this threshold. Leave it **Off** for a single cycle. Reimport and check the cycle boundaries.

## The temperature table disappears or looks stale

Changing freeze events or sample assignments, or rerunning analysis, clears the imported temperature/count table. Reimport temperatures after reviewing the new events and groups.

Descriptive sample-field edits do not require a detection rerun. Check exported sample information after renaming, removing, or excluding fields in Preferences.

## Export contains `nan` or an unexpected cell total

In the session and sample information, `nan` means a value was not supplied. Fill in missing values if you need them for later calculations. Preferences control which sample fields are exported.

In the data table, a missing temperature can mean an unmatched timestamp. A `nan` water blank correction can mean no blank group was selected. Check the column and import summary; do not replace all missing values with zero.

For unexpected totals, check sample assignments and any **Unassigned cells** group. Blank correction subtracts the blank's total and frozen counts from each non-blank group, so corrected totals can differ from the number of annotated cells.

## A result panel is missing

Use the **Window** menu to show the panel, or **Reset Panel Layout** to restore the default arrangement. **Freeze Count Timeseries** appears only after a successful temperature import or when opening a session that contains the saved table.

## The application will not launch or open a video

Check that you installed the build for your operating system, then note the exact error message. For video, confirm that the file exists and is readable. Source installations also need PyAV, the package that reads video frames.

For installation or build failures, see [Installation and Setup](Installation-and-Setup.md). When reporting a problem, include the Icescopy version, operating system, whether you used images or video, the action that failed, and the error text.
