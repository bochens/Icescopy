# Train a droplet detector

This experimental feature is available in the development source. It finds cells in one image or video frame. Freeze-frame analysis remains a separate step.

## Prepare labeled sessions

1. Open a representative image in Icescopy.
2. Mark **every droplet or filled well you want the detector to find**. Leave empty wells and unwanted objects unmarked.
3. Check circle centers and sizes, then save a `.icescopy` session. Keep its linked images or videos available.
4. Repeat for other lighting conditions or setups you want the model to recognize.

The marked circles supply positive examples. Other image regions supply background examples automatically; there is no separate negative-labeling step. An unmarked droplet may therefore teach the model to reject that appearance. Use complete labels on the frames selected for training.

## Train and save a model

Open **Analysis → Droplet Detection (Experimental) → Train Model...**, or run `icescopy-train` from a development environment.

Add the labeled sessions and choose their training frames. The saved current frame is the starting choice; use saved keyframes only when their labels are complete. The trainer does not assume that labels apply to every frame of a recording.

If a linked file has moved, relink its folder in the trainer. This changes the training input only; it does not rewrite the original session.

Choose **Train**, then save the result as an `.icescopy-model.json` file. The trainer creates rotated, cropped, uniformly scaled and lighting-adjusted examples while keeping their labels aligned. Training can be canceled.

## Detect cells in the current frame

1. Open the recording and navigate to the image or video frame to use.
2. Choose **Analysis → Droplet Detection (Experimental) → Load Model...** and select the saved model.
3. If the droplet size differs from the training images, mark and select one or two representative cells to provide the current size.
4. Choose **Detect Droplets (Current Frame)**.

Detections become ordinary editable cells. Existing cells are protected from duplicate selection, and one **Undo** removes the whole detection batch. Review the circles, delete unwanted ones and add any missed cells before running freeze analysis. Adding cells requires rerunning analysis.

Detection uses the underlying frame and its image coordinates, so display zoom, pan and crop do not change the model's input. Only circles fully inside the current crop are added. It does not scan the recording or generate motion tracking; new cells follow the same keyframe rules as manually added cells.

## What the model learns

A random forest is a collection of small decision trees. Here it learns brightness, contrast, edges and texture around the marked droplets. It examines the image directly and groups matching regions into cell selections; a preliminary circle finder cannot prevent it from examining a droplet.

Training examples should represent the images where the model will be used. Check it on another labeled image before relying on it for a different recording or setup. More variations of one photograph do not substitute for independent images.

## Run the trainer from source

The conda development environment includes training support. For an existing environment, install it from the repository root:

```bash
python -m pip install -e ".[training]"
icescopy-train
```

Training uses scikit-learn. Loading a saved model and detecting cells do not require scikit-learn, a neural-network library or a GPU. The model is a versioned JSON file containing numeric tree data; it does not contain the source images.
