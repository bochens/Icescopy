# Detect droplets with a saved model

This experimental feature is available in the development source. It finds cells in one image or video frame. Freeze-frame analysis remains a separate step.

## Detect cells in the current frame

1. Open the recording and navigate to the image or video frame to use.
2. Choose **Analysis → Droplet Detection (Experimental) → Load Model...** and select the saved model.
3. If needed, mark and select one or two representative cells to provide the current droplet size.
4. Choose **Detect Droplets (Current Frame)**.

Detections become ordinary editable cells. Existing cells are protected from duplicate selection, and one **Undo** removes the whole detection batch. Review the circles, delete unwanted ones and add any missed cells before running freeze analysis. Adding cells requires rerunning analysis.

Detection uses the underlying frame and its image coordinates, so display zoom, pan and crop do not change the model's input. Only circles fully inside the current crop are added. It does not scan the recording or generate motion tracking; new cells follow the same keyframe rules as manually added cells.

## Model files

The model is a versioned `.icescopy-model.json` file containing numeric tree data. It does not contain the source images. Loading a saved model and detecting cells do not require scikit-learn, a neural-network library or a GPU.
