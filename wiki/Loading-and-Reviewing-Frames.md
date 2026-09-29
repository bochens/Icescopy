# Loading and Reviewing Frames

Choose **File → New Session**, then load images or videos. Check their order before placing analysis markers or running analysis.

## Load an image sequence

1. Choose **File → Add Image Files...** to select files, or **Add Image Folder...** to load a folder. These choices are also in the toolbar's **Add Source** menu.
2. Check the **Images** panel and frames across the recording.
3. If needed, choose **File → Sort Images** and check the new order.

**Natural filename order** puts `frame_2` before `frame_10`. You can also sort by filename or file time. Check against the recording order; filenames and file dates can be misleading.

## Load one video or several clips

1. Choose **File → Open Video Source...** and select the recording's clips together.
2. Check the start and end of each clip. Multiple clips appear as one sequence, initially in natural filename order.
3. Use **File → Sort Video Clips** if needed. This reorders clips without changing the frames inside each clip.

The file chooser accepts MP4, MOV, AVI, MKV, and M4V. Support also depends on how the video was encoded.

A session holds images or video, not both. Save your work and start a new session to use another source. Keep the source files available when reopening a session.

Videos support the same cell, grid, keyframe, image-edit, analysis-marker, and freeze-review tools as images. For video temperature matching, use **Standard CSV import...** to set the start time or **UTK CSV import...** to read it from the first video's filename. Other instrument importers require images. See [Temperature Import](Temperature-Import.md).

## Navigate and compare frames

- Use the frame slider or previous/next buttons to move through the recording.
- Enter a frame number in the status bar and press **Enter** to jump there. The first frame is **0**.
- Use timeline zoom to change how much of the timeline is visible; use image zoom to enlarge the image.

| View control | Frames displayed |
| --- | --- |
| **Show One Image** | Current |
| **Show Two Images** | Previous and current |
| **Show Three Images** | Previous, current, and next |

Choose **Stack Top to Bottom** or **Stack Left to Right** to fit the comparison to your window. At the start or end, a neighboring frame may be unavailable. After analysis, select a cell to view its brightness plot alongside the images.

## Decide which frames to analyze

Use **analysis start/end markers** to exclude unwanted frames from brightness measurement and automatic freeze finding. You can include several separate intervals while keeping all source frames. See [Limit analysis with start and end markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

| Timeline control | Purpose |
| --- | --- |
| **Keyframe** | Save a cell layout to follow movement. |
| **Freeze flag** | Add or remove a freeze event for selected cells at the current frame. |
| **Analysis start/end** | Set the boundaries for the next analysis run. |

Run analysis again after changing source order or analysis boundaries. See [Analysis and Results](Analysis-and-Results.md).
