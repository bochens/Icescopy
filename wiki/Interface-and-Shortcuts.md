# Interface and Shortcuts

Use this reference to find controls. For the first complete workflow, follow [Quick Start](Quick-Start.md).

Menu names below follow the application labels. macOS can place **About** and **Preferences** in its standard application menu. A disabled action usually needs a session, loaded frames, a selection, or existing results.

## Menus and main controls

| Menu | Main tasks |
| --- | --- |
| **Icescopy / IceScopy** | About and Preferences |
| **File** | New/open/save session, metadata, outputs, image/video sources, relink, remove/clear, sort |
| **Edit** | Undo/Redo, drawing and image-edit tools, Sample Catalog Manager |
| **Analysis** | Run Analysis and Import Temperature Data |
| **Window** | Window size, one/two/three-image views, layout, and panel visibility |

The toolbar provides shortcuts to these actions. Hover over an icon for its tooltip. Tool selection and comparison-view selection are separate: one active editing tool can coexist with one active image-count button.

**Show One Image** displays the current image. **Show Two Images** shows previous/current frames; **Show Three Images** adds the next frame where available. **Stack Top to Bottom** switches the comparison arrangement; the action changes to **Stack Left to Right** in the vertical arrangement. These controls change presentation, not loaded data.

## Panels

Show or hide panels through **Window**. Closing a panel hides it rather than deleting its data.

| Panel | Use |
| --- | --- |
| **Images** | Browse the loaded images/frames, select image entries, and use **Freeze frame only** |
| **Tool Options** | Controls for the current tool; in Cursor mode, selected-cell information, freeze frames, and sample assignment |
| **Cells** | Find and select cells by their listed identity rather than locating a small circle in the image |
| **Sample Catalog** | Expand samples and edit their descriptive fields |
| **Grayscale Plot** | Compare selected-cell brightness, the processed detection signal, events, and the current frame |
| **Results Tables** | Inspect available measurement, freeze-event, and temperature-count tables |
| **Console** | Read operation messages and errors |

Use **Window → Reset Panel Layout** if a needed panel is hidden, floating off-screen, or too small. Drag panel boundaries to give image review and the plot enough space. **Zoom Window** and **Restore Window** control the main window size.

**Freeze frame only** filters the frame list to marked freeze frames for selected cells. With no selected cells, it uses all cells' recorded events. It does not set analysis limits or remove other frames from the session.

## Editing tools

| Tool | Key | Purpose |
| --- | --- | --- |
| Cursor Tool | **A** | Select and inspect cells; assign samples and edit freeze events |
| Pan and Zoom | **Z** | Move and zoom the image view |
| Add Cell | **S** | Place individual circles |
| Grid Tool | **G** | Preview and apply an array of circles |
| Delete Cells | **D** | Delete selected cells; with no selection, click cells to remove them |
| Edit Cell | **E** | Edit a selected circle or group |
| Image Edit | Use menu/toolbar | Exposure, contrast, crop, and illumination correction |

Click the image/viewer before using a letter shortcut. In a text field, that letter may enter text instead. **D** deletes selected cells immediately, or enters Delete Cells mode when nothing is selected. See [Annotation Workflow](Annotation-Workflow.md) for selection modifiers and preview controls.

## Timeline and status controls

| Control | Meaning |
| --- | --- |
| Previous / next buttons | Move one frame backward or forward |
| Frame slider | Navigate the loaded sequence |
| Timeline zoom control | Change how much of the frame sequence is visible on the slider |
| Keyframe button | Save/remove a geometry keyframe at the current frame |
| Freeze flag | Mark/clear the current frame as a freeze event for selected cells |
| Analysis start button | Toggle a start marker at the current frame |
| Analysis end button | Toggle an end marker at the current frame |
| **Frame Number** field | Enter a zero-based frame index and press Enter to navigate |
| **Zoom Level** field | Control image magnification |
| **Circle Radius** field | Set the current drawing radius; it is not the image zoom |

Timeline markers have different jobs: geometry keyframes, freeze events, and analysis intervals are independent. Click an analysis marker to visit its frame, then use its corresponding toggle to remove it; analysis markers are not dragged to reposition them. See [Analysis and Results](Analysis-and-Results.md#limit-analysis-with-start-and-end-markers).

The plot's current-frame line moves as you navigate. Event lines stay at the assigned freeze frames. A visible event line elsewhere does not mean the current frame is also frozen.

## Keyboard reference

| Action | Shortcut | Context |
| --- | --- | --- |
| Save session | **Ctrl+S** on Windows; **Cmd+S** on macOS | Active session |
| Save Session As | Use the shortcut displayed beside the menu item | Platform-defined |
| Undo | **Ctrl+Z** / **Cmd+Z** | A supported edit is available in history |
| Redo | **Ctrl+Y** or **Ctrl+Shift+Z** on Windows; **Cmd+Shift+Z** on macOS | A supported edit has been undone |
| Previous / next frame | **,** / **.** | Viewer/window navigation |
| Previous / next frame | **Left** / **Right** | Frame/zoom sliders or plot navigation; a focused text field can use these keys for editing |
| Temporary pan | Hold **Space**, then release | Loaded frames; restores the prior tool on release |
| Apply a tool preview | **Enter** | Active placement/edit preview |
| Cancel a tool preview | **Escape** | Active preview |
| Remove selected cells | **Delete** or **Backspace** | Cursor mode in the image viewer |
| Remove selected image entries | **Delete** or **Backspace** | Images list; image sequences only |

Deletion depends on focus: image-list removal and cell removal are different operations. Use the explicit menu or tool controls if focus is unclear. A key pressed in a dialog or text editor can have a local meaning.

## Find settings by purpose

- **Preferences → Drawing:** annotation appearance and placement defaults.
- **Preferences → Analysis:** brightness source and detection controls.
- **Preferences → Samples:** sample naming and metadata definitions.
- **Preferences → Timeseries:** plot appearance.
- **Preferences → Timeline:** timeline appearance.
- **Preferences → Viewer:** viewer defaults.
- **Preferences → General:** general defaults and history settings.

Changing the appearance of circles or a plot is different from changing geometry, image adjustments, or detector settings. See [result dependencies](Concepts-and-Data-Flow.md#what-to-repeat-after-an-edit).

Related: [Loading and Reviewing Frames](Loading-and-Reviewing-Frames.md) | [Annotation Workflow](Annotation-Workflow.md) | [Troubleshooting](Troubleshooting.md)
