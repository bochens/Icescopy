# Detect droplets with marked examples

This experimental feature is available in the development source. It finds cells in one image or video frame. Freeze-frame analysis remains a separate step.

## Detect cells in the current frame

1. Open the recording and navigate to the image or video frame to use.
2. Mark and select representative droplets or filled wells to guide the detector's appearance and size. Any number of selected cells can serve as examples. Leave empty wells and unwanted objects unselected.
3. Click the **circle with a star** in the toolbar, or choose **Analysis → Droplet Detection (Experimental) → Detect Droplets (Current Frame)**.

The bundled model loads automatically when detection starts. Without selected cells, it uses a general reference learned from the training data, which may be less accurate for the current image. Selecting examples guides detection without training a new model.

Detections become ordinary editable cells. Existing cells are protected from duplicate selection, and one **Undo** removes the whole detection batch. Review the circles, delete unwanted ones and add any missed cells before running freeze analysis. Adding cells requires rerunning analysis.

Detection uses the underlying frame and its image coordinates, so display zoom, pan and crop do not change the model's input. Only circles fully inside the current crop are added. It does not scan the recording or generate motion tracking; new cells follow the same keyframe rules as manually added cells.
