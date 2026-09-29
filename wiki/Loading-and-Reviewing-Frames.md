# Loading and Reviewing Frames

Start with **File → New Session**, then load images or videos. Finish checking the source order before placing analysis markers and running analysis.

## Load an image sequence

Use **File → Add Image Files...** to select files, or **File → Add Image Folder...** to load a folder. The toolbar's **Add Source** menu provides the same choices.

Review the **Images** panel and several frames across the recording. If needed, use **File → Sort Images**. Natural filename order treats numbers as numbers, so `frame_2` comes before `frame_10`. Other available choices include filename and file-time ordering. Check the result against the actual acquisition order rather than assuming a filename or file date is correct.

## Load one video or several clips

Choose **File → Open Video Source...** and select all clips for the recording together. The file chooser includes MP4, MOV, AVI, MKV, and M4V; whether a file can be opened also depends on its video encoding.

Several clips appear as one frame sequence, initially in natural filename order. Use **File → Sort Video Clips** to change the clip order, and inspect frames at the joins. Sorting changes clip order, not the order of frames within each clip.

A session contains either image files or video clips. Start a new session for another source when preserving your current work. Keep the original files available when reopening a saved session.

Video uses the same cell, grid, keyframe, image-edit, analysis-marker, and freeze-review tools as images. For video temperature matching, **Standard CSV import...** lets you set the start time; **UTK CSV import...** derives it from the first video's filename. The other instrument importers require image files. See [Temperature Import](Temperature-Import.md) for setup.

## Navigate and compare frames

- Use the frame slider or previous/next buttons to move through the recording.
- Enter a frame number in the status bar and press **Enter** to jump directly. The first frame is **0**.
- The timeline zoom control changes how much of the timeline is visible; image zoom changes the size of the displayed image.

The numbered view controls show:

| View | Frames displayed |
| --- | --- |
| **Show One Image** | Current frame |
| **Show Two Images** | Previous frame and current frame |
| **Show Three Images** | Previous, current, and next frame |

Use **Stack Top to Bottom** or **Stack Left to Right** to fit the comparison to your window. At the beginning or end, a neighboring frame may be unavailable. After analysis, select a cell to connect the displayed images with its brightness plot.

## Decide which frames to analyze

Use **analysis start/end markers** to keep unwanted parts of the recording out of automatic measurement and freeze finding. You can include one interval or several separate intervals without deleting any source frames. Follow [Limit analysis with start and end markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

The timeline controls have different jobs:

- **Keyframe:** saves a cell layout for following movement.
- **Freeze flag:** marks or clears freezing for the selected cells at the current frame.
- **Analysis start/end:** sets the boundaries used by the next analysis run.

After source order or analysis boundaries change, run analysis again before accepting the results. See [Analysis and Results](Analysis-and-Results.md).
