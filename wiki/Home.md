# Icescopy User Guide

Icescopy helps you mark droplets or wells in images and videos, find when they freeze, review the detections, and match them to temperature records.

New to the app? Follow [Quick Start](Quick-Start.md). For installation, see [Installation and Setup](Installation-and-Setup.md).

## Find the task you need

| Task | Guide |
| --- | --- |
| Load images or video clips, check their order, and compare nearby frames | [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) |
| Add individual cells or grids, follow movement, and assign samples | [Annotation Workflow](Annotation-Workflow.md) |
| Crop the view or adjust brightness across frames | [Image Editing](Image-Editing.md) |
| Limit analysis with start/end markers, tune freeze detection, and review results | [Analysis and Results](Analysis-and-Results.md) |
| Match freeze events to temperature records | [Temperature Import](Temperature-Import.md) |
| Save separate sessions, customize sample fields, and export selected tables | [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) |
| Resolve missing events, stale results, missing files, or import problems | [Troubleshooting](Troubleshooting.md) |

## Recommended workflow

1. Start a session, load an image sequence or video clips, and check the order.
2. Adjust the images if needed, then mark each droplet or well with a cell circle. Assign sample groups.
3. Set **analysis start and end markers** to include only the parts of the recording you want measured. You can define several separate intervals.
4. Run analysis. Compare detected freeze frames with the images and grayscale plot, which shows brightness over time.
5. Tune detection settings and rerun if needed. Make manual freeze corrections after the final run.
6. Import temperature records, review the counts, and export the tables you need. Save the session throughout your work.

See [limiting analysis with markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers) for step-by-step instructions. Changing markers or detection settings does not recalculate existing freeze events; run analysis again. After changing events or sample assignments, reimport temperature data to rebuild the counts.

## Terms used in the guide

- **Cell:** a circle marking the part of a droplet or well whose brightness is measured.
- **Sample:** a group of cells belonging to the same experimental sample, together with information such as its name and dilution.
- **Keyframe:** a frame with a saved cell layout. The app calculates intermediate positions between keyframes when the image moves.
- **Analysis interval:** the frames between a start marker and an end marker, including both endpoints. It limits automatic measurement and freeze finding.
- **Session:** a `.icescopy` file storing annotations, settings, sample information, and results. Keep the original media available: the session refers to those files.

Use **Save Session As...** and a fresh export folder when preserving an earlier result. [Save and export guidance](Sessions-Export-and-Preferences.md) explains the difference between a resumable session and CSV result tables.

## For developers

[Architecture Overview](Architecture-Overview.md) · [Cell System](Cell-System.md) · [API Reference](API-Reference.md)
