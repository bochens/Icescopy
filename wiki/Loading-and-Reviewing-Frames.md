# Loading and Reviewing Frames

[User guide](Home.md) · [Quick start](Quick-Start.md) · [Interface and shortcuts](Interface-and-Shortcuts.md)

Use this page to load a recording, establish its order, and navigate it without changing the measurements. A **frame** is one image, whether it came from a separate file or a video. Frame numbers start at **0** and refer to the current source order.

## Before you load

Choose **File → New Session** and enter the session information. A session can contain an image sequence or one or more video clips. It cannot mix the two.

Keep source files in a stable location. Saving a `.icescopy` session stores their references, not a copy of the recording. If you are replacing an existing analysis, use **File → Save Session As...** first.

## Load an image sequence

1. Choose **File → Add Image Files...** to select files, or **File → Add Image Folder...** to load a folder. The toolbar's **Add Source** control offers the same choices.
2. Open **Window → Images** if the file list is hidden.
3. Check the first frame, several middle frames, and the last frame. Confirm that the recording moves forward in the intended order.
4. If needed, choose **File → Sort Images**, select a method under **Sort By**, and click **OK**.

The image chooser initially shows PNG and JPEG files; **All Files** exposes other files. Folder loading searches subfolders for JPG, JPEG, PNG, GIF, BMP, TIFF, and WebP files. It skips files and directories whose names begin with `.` or `_`.

You can add more images to an image session. Already-loaded file paths are skipped; new files are sorted within the added batch and appended to the sequence. Run **Sort Images** afterward if the combined list needs reordering. Adding or reordering frames clears analysis results that depended on the old sequence.

### Choose the right sort order

| Sort method | Use and limitation |
| --- | --- |
| **Natural Filename** | Treats digit groups as numbers: `frame_2` comes before `frame_10`. Useful for numbered image sequences. |
| **Filename (A-Z)** / **Filename (Z-A)** | Sorts text in ascending or descending order. Check names with unpadded numbers carefully. |
| **Created Time** / **Modified Time** | Uses filesystem dates. Copying or processing files can make these differ from acquisition order. Availability depends on the files and platform. |
| **EXIF Time** | Uses embedded image time information. Available only when it can be read from every selected file. |

Check the result against the experiment; no sort method can infer the intended cooling sequence from an incorrect filename or timestamp. Sorting remaps saved keyframes and analysis markers to their source images, but analysis results must be regenerated. Verify the boundaries again after any reorder.

## Load one video or several clips

1. Start with an empty session, then choose **File → Open Video Source...**.
2. Select the clip, or select **all clips for the recording together**, and open them.
3. Wait for the frames to become available. The Images panel now represents video frames rather than separate image files.
4. Check the first and last frame of each clip, especially the joins.
5. For multiple clips, use **File → Sort Video Clips** if their order is wrong.

The chooser lists MP4, MOV, AVI, MKV, and M4V. The app must also be able to decode the video's encoding; a supported filename extension alone does not guarantee that a file opens.

Multiple clips form one continuous frame sequence, initially in natural filename order. Sorting moves whole clips; it does not reorder frames within a clip. The combined video time follows the clips consecutively. It does not reconstruct real pauses between separately recorded clips, so check timing at the joins before importing temperatures.

Video supports the same cell, grid, keyframe, image-edit, analysis-marker, and freeze-review tools as images. Temperature matching is available through **Standard CSV import...** and **UTK CSV import...**; the other instrument importers require image files. See [Temperature Import](Temperature-Import.md) for the timing setup.

You cannot append another video or images to a loaded video source. To change the clip set, save the session and start a new one, or deliberately clear the current source as described below.

## Navigate and compare frames

| Task | Control |
| --- | --- |
| Step one frame | Click previous/next, or press **Left/Right** with the image viewer focused. **Comma/period** also step backward/forward. |
| Jump to a frame | Enter its number in **Frame Number** in the status bar and press **Enter**. |
| Scan the recording | Drag the timeline slider. Release it at the frame you want to inspect. |
| Jump from the file list | Click a row in **Images**. |
| Inspect a shorter section of the timeline | Adjust the timeline zoom control. This does not crop or shorten the recording. |
| Enlarge or move the displayed image | Press **Z**, scroll to zoom, and drag to pan. Press **A** to return to selection. |
| Pan temporarily while placing cells | Hold **Space**, pan or zoom, then release it to return to the previous tool. |

Image zoom and timeline zoom have different jobs. Image zoom changes the displayed size of the recording. Timeline zoom changes the range visible on the slider. Neither changes analysis values or removes frames.

### Compare neighboring images

Use the toolbar controls or their entries in the **Window** menu:

| View control | Frames displayed |
| --- | --- |
| **Show One Image** | Current frame |
| **Show Two Images** | Previous frame and current frame |
| **Show Three Images** | Previous, current, and next frame |

Each frame has its own labeled pane. Choose **Stack Top to Bottom** or **Stack Left to Right** to fit the comparison to your window. In Pan mode (**Z**), pan or zoom in any pane; all panes follow the same image position and zoom, so you can inspect the same cell across neighboring frames. Holding **Space** also lets you pan or zoom temporarily.

Each pane shows the cell positions and sizes for its own frame. If you use [keyframes](Annotation-Workflow.md#follow-movement-with-keyframes), neighboring panes show the corresponding stored or interpolated layout. Without keyframes, all frames use the same cell layout.

Use the **Current** pane to select, add, or edit cells; neighboring panes show their cell outlines and labels for comparison. [Image Edit](Image-Editing.md) adjustments apply across the recording and update every pane. You can move or resize a crop box or Uniform Exposure control area in any available pane; the same area appears in the others.

To bring selected cells to the middle of the view, use **Center on selection** under **Cell Info** in the Cursor Tool Options. All panes follow the Current pane's center without changing zoom. For automatic centering from the **Cells list**, enable **Auto-center**. It also responds when you click the same Cell row again after panning or zooming. Selecting circles in the image or changing frames does not trigger it. See [Center the selection](Annotation-Workflow.md#center-the-selection) for group behavior and controls.

At the beginning or end of the recording, the unavailable pane stays blank and its label says **no earlier frame** or **no later frame**. While dragging the video timeline, neighboring panes may be blank with **updates after seeking** labels; they reload when you finish seeking. Each pane always represents the previous, current, or next frame, rather than a separately chosen frame.

After analysis, select a cell and open **Window → Grayscale Plot** to compare its brightness changes with these images. If the plot has been panned or zoomed into an unhelpful range, selecting a different cell and then returning to the original cell fits its data again.

### Review only detected events

1. Press **A** and select the cells to review.
2. Open **Window → Images**.
3. Enable **Freeze frame only** above the list.
4. Click the listed frames and compare the images around each event.

The list contains freeze frames for the **current cell selection**, including manual corrections. With no cells selected, it shows events from all cells. It keeps the original frame numbers. If the list is empty, check whether the selected cells have recorded events. Turn the filter off to return to all frames. Filtering the list does not limit analysis.

To review cells one at a time, enable **Show freeze frame** in **Cells** and select individual Cell rows with **Up/Down** or a click. This opens each cell's earliest available recorded freeze frame. Enable **Auto-center** as well to center the cell at that frame without changing zoom. Checking either option immediately applies all enabled options to the current selection. Both options work with Cursor or Pan and Zoom active. See [Show a selected cell's first freeze frame](Annotation-Workflow.md#show-a-selected-cells-first-freeze-frame) for behavior with groups, repeated clicks, and missing events.

## Decide which frames to analyze

Use **analysis start/end markers** to exclude unwanted sections from brightness measurement and automatic freeze finding. You can include several intervals while keeping all source frames.

1. Go to the first frame to include and toggle **analysis start**.
2. Go to the last frame to include and toggle **analysis end**.
3. Repeat for other intervals, then run analysis.

Both boundary frames are included. With no markers, analysis uses the whole recording. See [Limit analysis with start and end markers](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers) for incomplete pairs and moving markers.

| Timeline control | Purpose |
| --- | --- |
| **Keyframe** (diamond) | Save cell positions and sizes at a frame so the layout can follow movement. |
| **Freeze flag** | Add or remove a freeze event for selected cells at the current frame. |
| **Analysis start/end** | Set the intervals used by the next analysis run. |

## Remove or replace a source

To exclude a section from analysis, use start/end markers. Removing images is appropriate when files were loaded by mistake or should no longer belong to the session.

For **image files**, select rows in the Images panel and choose **File → Remove Selected**, or press Delete/Backspace while that panel has focus. Removal changes the session list and frame numbering; it does not delete the files from disk. Check markers afterward and rerun analysis. Use **Edit → Undo** to recover an accidental removal while it is in the undo history. Individual frame removal is unavailable for video; use analysis markers to skip unwanted sections.

Keyboard focus matters: Delete/Backspace in the image viewer's Cursor mode deletes **selected cells**, while those keys in the Images panel remove **image entries**. Click the intended panel first.

**File → Clear Images** clears the loaded source and its keyframes, analysis markers, and results. It keeps cells and sample assignments so a layout can be reused. Save the old session first, then verify the retained circles against the replacement recording. Start a **New Session** instead when you want a separate experiment without the retained layout.

Keep original source files available when reopening a session. See [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) for missing-image recovery, and [Troubleshooting](Troubleshooting.md) for videos that fail to open.

**Next:** [Draw and assign cells](Annotation-Workflow.md), [prepare image brightness and crop](Image-Editing.md), or [run and review analysis](Analysis-and-Results.md).
