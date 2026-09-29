# Icescopy User Guide

Use Icescopy to mark droplets or wells in images and videos, find when they freeze, and match the freeze events to temperatures.

Start with [Installation and Setup](Installation-and-Setup.md), then follow [Quick Start](Quick-Start.md).

## Find the task you need

| Task | Guide |
| --- | --- |
| Load and compare images or video frames | [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) |
| Draw cells and grids, assign samples, and follow movement | [Annotation Workflow](Annotation-Workflow.md) |
| Crop images or adjust brightness | [Image Editing](Image-Editing.md) |
| Set analysis limits, find freeze frames, and tune detection | [Analysis and Results](Analysis-and-Results.md) |
| Add temperatures to freeze events | [Temperature Import](Temperature-Import.md) |
| Save work, export tables, and customize sample fields | [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) |
| Fix common problems | [Troubleshooting](Troubleshooting.md) |

## Recommended workflow

1. Load images or video clips and check their order.
2. Mark each droplet or well with a cell circle and assign cells to samples.
3. Set **analysis start and end markers** to choose which frames to analyze.
4. Run analysis and check the detected freeze frames against the images.
5. Tune detection and rerun if needed, then make any manual corrections.
6. Import temperature records, review the counts, and export. Save the session as you work.

After changing markers or detection settings, run analysis again. After changing freeze events or sample assignments, reimport temperatures to update the counts.

## Terms used in the guide

- **Cell:** a circle defining where the app measures a droplet's or well's brightness.
- **Sample:** a group of cells from the same experimental sample.
- **Keyframe:** a frame with a saved cell layout. The app calculates cell positions between keyframes to follow movement.
- **Analysis interval:** the frames from a start marker to an end marker, including both endpoints.
- **Session:** a `.icescopy` file that saves your work. It refers to the original images or videos, so keep those files too.

To preserve earlier work, use **Save Session As...** and export to a new folder. See [saving and exporting](Sessions-Export-and-Preferences.md).

## For developers

[Architecture Overview](Architecture-Overview.md) · [Cell System](Cell-System.md) · [API Reference](API-Reference.md)
