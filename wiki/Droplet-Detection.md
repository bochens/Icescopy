# Detect droplets with marked examples

This experimental feature is available in the development source. It finds cells in one image or video frame. Freeze-frame analysis remains a separate step.

## Detect cells in the current frame

1. Open the recording and navigate to the image or video frame to use.
2. Mark and select representative droplets or filled wells to guide the detector's appearance and size. Any number of selected cells can serve as examples. Leave empty wells and unwanted objects unselected.
3. Click the **circle with a star** in the toolbar, or choose **Analysis → Droplet Detection (Experimental) → Detect Droplets (Current Frame)**.

The bundled model loads automatically when detection starts. Without selected cells, it uses a general reference learned from the training data, which may be less accurate for the current image. Selecting examples guides detection without training a new model.

When detection finishes, a dialog reports the model name and version, the number of selected guidance cells, the number found, and the number added inside the current crop.

Detections become ordinary editable cells. Existing cells are protected from duplicate selection, and one **Undo** removes the whole detection batch. Review the circles, delete unwanted ones and add any missed cells before running freeze analysis. Adding cells requires rerunning analysis.

Detection uses the underlying frame and its image coordinates, so display zoom, pan and crop do not change the model's input. Only circles fully inside the current crop are added. It does not scan the recording or generate motion tracking; new cells follow the same keyframe rules as manually added cells.

## Choose a model

Open **Preferences → ML**. Use **Bundled model** for the included **General droplets 1.0.0**, or choose **Model file** and browse to an `.icescopy-model` file. Save to apply the choice. Cancel leaves the previous choice in place.

Model versions are independent of Icescopy versions. A compatible replacement can be loaded without reinstalling the app. Keep the selected file in its location; if it is moved, select it again. An unreadable or incompatible custom model produces an error instead of silently switching to the bundled model.

Model files contain the networks and their version information. They do not contain the training program. Developers can train or fine-tune a model outside Icescopy, export a compatible `.icescopy-model` file, and distribute it separately. See [developer training and export](../auto_cell_ml/README.md#future-training-and-app-export). The application itself does not need PyTorch.
