# Automatic cell detection

Experimental detector development, separate from the Icescopy app. The active direction is a small convolutional neural network (CNN), which learns spatial image patterns. Forest and OpenCV ANN_MLP development are stopped. The downloaded pretrained weights were deleted; the CNN trains from scratch.

## Working files

- `code/model.py`: CNN and loss for centers, offsets, and radii.
- `code/train.py`: training for one setup, using the original image and its saved circles.
- `code/infer.py`: single-image detection and overlays.
- `code/data.py`: trusted source reader, aligned image/label transforms, and training views.
- `code/image_samples.py`, `code/forest.py`, `code/opencv_nn.py`: inactive patch-classifier experiments.
- `tests/`: focused geometry, supervision, model, and storage checks.
- `data/train/<setup>/`: original images and user-labeled `.icescopy` sessions.
- `data/evaluation/<setup>/`: separate recordings for visual evaluation.
- `data/synthetic/`: preserved procedural scenes with filled and empty targets; only the fit partition may train a model.
- `data/augmented/`: earlier generated images, preserved but not required for the active in-memory pipeline.
- `results/`: models, measurements, and overlays, separated by experiment.
- `.venv/`: local neural development environment, excluded from Git.

Private data, weights, and results are excluded from Git. Keep all experimental artifacts here, not in the app's `output/` directory. Never overwrite an existing result directory.

## Training rules

The private `data/datasets.json` records source identity, hashes, relative paths, and recording assignments. Only the user's saved circles define positive targets. Other valid locations are background; padding alone is ignored. No manual negative labels are required.

Every training view transforms pixels, circles, and padding together. Whole-image coverage includes outer background; random crops around marked droplets alone are insufficient. Use rotations, reflections, uniform scale changes, and lighting changes without distorting the aspect ratio. Augmented views may be constructed in memory rather than saved as more image files.

Every view of a recording stays in its training partition. Evaluation uses separate recordings, never crops or other frames from the training recording. Show predictions without requiring evaluation labels; do not report independent accuracy without reference labels. Model errors on a training image are useful diagnostics, not evidence of generalization.

Resource paths remain portable and relative. Do not add aliases, stale absolute-path fallbacks, or source searches. Decode the full range of 16-bit source images before converting to 8-bit RGB.

## Current evidence

On the same PCR training image with 160 labels, using one-to-one center matches within 3.5 pixels:

| Earlier experiment | Matched | Missed | Extra or misplaced |
| --- | ---: | ---: | ---: |
| Forest | 138 | 22 | 105 |
| ANN_MLP, 100 iterations | 140 | 20 | 236 |
| ANN_MLP, 1,000 iterations | 160 | 0 | 52 |

These runs used different training procedures. They do not establish an intrinsic ranking of model types. The ANN_MLP remains inadequate despite the longer fit. Its model is about 226 KB; fitting took 9.6 or 94.9 seconds, respectively. Baseline artifacts remain in `results/random-forest-v1/` and `results/opencv-nn-v1/`.

## Handoff

Paused for a feasibility assessment before any real CNN training. The from-scratch CNN has 92,788 parameters. Fifteen data checks and ten model checks passed, including controlled filled-versus-empty learning; these do not establish real-image performance. The new training views cover every source pixel and every marked circle each epoch, without saving generated images. Synthetic fit inputs are verified, but synthetic-first training is not implemented.

Next, only if continued: run one fixed PCR CNN experiment, compare centered matches and unwanted detections on its training image, then inspect the separate recording. The intended command is `auto_cell_ml/.venv/bin/python auto_cell_ml/code/train.py --manifest auto_cell_ml/data/datasets.json --setup 02-CSU-IS-PCR-filled-and-empty --output auto_cell_ml/results/cnn-v1/02-CSU-IS-PCR-filled-and-empty --epochs 10 --device mps`. GPU availability was verified outside the sandbox; inside it MPS appears unavailable. CPU is supported. No real CNN run has been launched.

ONNX export is unverified because its optional dependency is absent; do not claim the CNN runs in the app or through OpenCV yet. PKU source searching is stopped; four setups have separate evaluation images. No UI integration, packaging, release, or push is part of this experiment. Do not reread the old forest/ANN code unless investigating its recorded baseline; the active source files are listed above.
