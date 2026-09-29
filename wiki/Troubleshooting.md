# Troubleshooting

Start with the symptom below. Save a separate session with **File → Save Session As** before experimenting with changes you may want to discard.

## A session opens without its images

The `.icescopy` file stores source paths; it does not embed the image or video files.

For image sequences, choose **File → Relink Images Folder** and select the folder containing the original filenames. Review the relink report: missing names and duplicate filename matches are not silently replaced. Relinking normally saves the updated paths to the current session file, so use **Save Session As** first if you need to preserve that file.

For a missing video, restore the source file at its saved location and reopen the session. **Relink Images Folder** applies to image sequences, not video paths. When sharing a session, include its source media and confirm that the recipient can access the stored paths or relink the images.

## Images cannot be added to a video session

A session uses an image sequence or a video source. Images cannot be appended to a loaded video source. Save the current session, then start a new session for the other source type.

For multiple video clips, load them through the video workflow and check their order. Image-only actions, including image-folder relinking and removing individual frames, are unavailable for video. See [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md).

## Changing Preferences did not change detected freeze frames

Saving Preferences applies the settings but does not rerun analysis. Choose **Analysis → Run Analysis**, review the new detections, then reimport temperature data and export updated tables.

Changes to cell geometry, keyframes, crop, image adjustments, or detection settings can change the measurements or events. Existing results should not be interpreted as the result of new settings until analysis completes. Editing descriptive sample metadata alone does not require image analysis; changing sample assignments requires temperature reimport.

## Analysis covers only part of the recording

Check the **Analysis Start** and **Analysis End** markers. Their ranges include both endpoint frames; gaps between ranges are omitted from automatic analysis. A missing start uses the beginning of the source, and a missing end uses its end. With no markers, analysis covers the full source.

Consecutive starts use the nearest start before the next end; extra ends after a closed range are ignored. Visit each marker and remove unintended markers with the corresponding marker button. Marker triangles navigate to their frames; they are not draggable. Run analysis again after correcting the ranges.

Markers limit automatic analysis, not manual freeze annotations. A manually marked event can still exist outside those ranges. See [Limit Analysis with Start and End Markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

## Manual freeze corrections disappeared

**Run Analysis** replaces the freeze-events table with the new detection results. Make manual corrections after the final detection run, then save the session and reimport temperature data. If you need to compare corrected and rerun results, save separate sessions first.

To edit a cell's events, select it in Cursor mode and use **Freeze Frame**. Enter comma-separated, zero-based frame numbers, or `None` to clear them. Frame zero is the first loaded frame. Check the selected cell and displayed image before applying a correction.

## Freeze finding misses events or calls too many

Select a representative cell and compare its images with its grayscale plot, which shows mean image brightness inside the circle. Confirm the circle stays on the droplet throughout the recording.

Check the expected brightness-change direction, the response width in frames, and prominence—the size of a peak in the processed detection signal relative to its surroundings. Change one relevant setting, save Preferences, and rerun analysis. Check a few clear freezes and a few suspected false detections before applying the settings to a full recording.

See [Review and Tune Freeze Detection](Analysis-and-Results.md#review-and-tune-freeze-detection) for the controls and a worked tuning sequence.

## Cells drift away from droplets

Add keyframes: frames where you explicitly adjust cell positions. Icescopy interpolates cell positions between them. Check the start, end, and intermediate frames, then rerun analysis. See [Follow Movement with Keyframes](Annotation-Workflow.md#follow-movement-with-keyframes).

## Temperature import fails or temperatures look shifted

Check frame order, the temperature file's time range, and the current sample assignments. Then check the selected importer:

| Importer | First checks |
|---|---|
| Standard CSV | Timestamp is column 1 and temperature is column 2; at least two rows; no duplicate timestamps; correct unit and timestamp styles |
| CSU | Matching picture names and `Sample_...` names; original `.dat` contains `Avg_Temp` and `Picture` |
| TAMU | Matching Linkam workbook, parseable PNG filename timestamps, and correct calibration cell IDs if calibration is used |
| PKU | Matching `.iml`, identical image-record count, and the same image order |
| UTK | Exact `Time` and `PV(C)1` headers; parseable image names or a recognized start timestamp in the first video filename |

For Standard CSV, check the timestamp preview. File modification time may describe when an image was copied rather than acquired. If the image and CSV formats differ, clear **Use image style for temperature timestamps** and choose them separately. Numeric epoch timestamps require an explicit seconds or milliseconds style.

For video, Standard CSV and UTK imports are supported; CSU, TAMU, and PKU require image files. Check the first timestamp, elapsed-time method, and clip order. A successful parse does not confirm that the camera and temperature logger clocks agree.

For timestamp-based imports, no frames inside the temperature record means the import fails. If only some match, inspect the unmatched frames before using the output. See [Temperature Import](Temperature-Import.md) for formats and steps.

## A cooling cycle restarts at the wrong time

Check **Reset After Warmed To (°C)** against the warming part of the actual temperature record. The threshold identifies when counts restart for a new cycle. Leave it Off if there should be only one cycle, then reimport and inspect the boundaries.

## The temperature table disappears or looks stale

Changing freeze events or sample assignments, or rerunning analysis, clears the imported temperature/count result. Reimport the temperature file using the reviewed events and current groups.

Descriptive metadata edits do not require a detection rerun. Check the exported metadata after editing the sample catalog, particularly if fields were renamed, removed, or excluded from export in Preferences.

## Export contains `nan` or an unexpected cell total

In metadata, `nan` means the field was not supplied. Fill in the relevant session or sample-catalog values if downstream software needs them. Exported sample fields follow the metadata field settings in Preferences.

In the data table, a missing temperature can indicate an unmatched timestamp. A `nan` water blank correction can mean no blank group was selected. Inspect the column and import summary rather than replacing all missing values with zero.

For cell totals, review sample assignments and any **Unassigned cells** group. Blank correction subtracts both the blank total and blank frozen count from each non-blank output group; the resulting total can differ from the annotated cell count. Fractions and concentrations require the appropriate valid counts and experimental metadata.

## A result panel is missing

Use the **Window** menu to show the relevant panel. **Reset Panel Layout** restores the default arrangement. A Freeze Count Timeseries table becomes available after a successful temperature import; opening a session without that saved table does not create one.

## The application will not launch or open a video

Use the build for your operating system and check the exact error dialog. Platform security restrictions and missing packaged dependencies need different fixes. For a video error, first confirm that the source file exists and is readable; video decoding also requires the application's PyAV dependency, which reads video frames.

For a source installation or build failure, check the environment and instructions in [Installation and Setup](Installation-and-Setup.md). When reporting a problem, include the Icescopy version, operating system, source type, the action that failed, and the error text.
