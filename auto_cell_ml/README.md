# Automatic cell detection

Experimental droplet detection for Icescopy. The active approach is a CPU random forest using OpenCV's built-in trainer, with one model per setup trained directly from its original labeled image. It is not integrated into the app. Neural training is stopped and the downloaded neural weights have been deleted.

## Folder layout

- `code/forest.py`: active OpenCV training, model loading, and single-image prediction.
- `code/data.py`: trusted original-image/session reader and inactive crop generator.
- `code/model.py`, `code/train.py`, `code/infer.py`: tested neural prototype, retained untrained. These are not the active training approach.
- `tests/`: focused checks for geometry, negative supervision, image decoding, and model operations.
- `data/train/<setup>/`: manually labeled images and their `.icescopy` sessions.
- `data/evaluation/<setup>/`: images from separate recordings. Label availability is recorded explicitly.
- `data/augmented/`: earlier generated crops, retained but excluded from current training.
- `data/synthetic/`: preserved synthetic images, excluded from the next training run.
- `results/`: experimental forest models, measurements, and detection previews.
- `.venv/`: local Python dependencies, excluded from Git.

Private images, labels, weights, and results are excluded from Git. Keep training data here, not in the application's `output/` directory.

## Data rules

- The private `data/datasets.json` records original sources, file hashes, relative local paths, recording assignments, and label status. `data/README.md` summarizes the available recordings.
- Only manually marked circles define training targets. Other valid image locations are negative. No separately marked negative regions are required.
- Keep every frame and transformation from a recording in the same partition. Never describe a crop of the training image as an independent evaluation image.
- Train on the original labeled image only. Do not generate or consume augmented training images.
- Run on the separate evaluation images and show overlays for visual inspection. Evaluation labeling is not required. Do not report accuracy percentages without reference labels.
- Session image links are relative to the session directory. Resource paths in code must also be portable; do not add aliases or path-search fallbacks.
- Some CSU images are 16-bit grayscale PNGs. Decode their full intensity range; converting them directly to 8-bit RGB with clipping can turn them white.

## Handoff

PKU source searching is stopped. Four setups have separate evaluation images. The first forest run used generated crops and produced unacceptable PCR edge detections and duplicate circles; its results are retained under `results/random-forest-v1/`. The next run uses original labeled images only. Check the active path with `python -m pytest auto_cell_ml/tests/test_data.py auto_cell_ml/tests/test_forest.py -q` in the Icescopy environment; inactive neural tests require the separate Torch environment. No UI work has started. The app's existing forest uses scikit-learn and an older labeling rule; it must not be treated as the new implementation. Previous experiments remain in Git history; do not restore their folder tree.

## Original-image experiment

From the repository root, using a Python environment with the app's dependencies:

```sh
python auto_cell_ml/code/forest.py train --manifest auto_cell_ml/data/datasets.json --setup 02-CSU-IS-PCR-filled-and-empty --output auto_cell_ml/results/original-image-forest-v1/02-CSU-IS-PCR-filled-and-empty/model
python auto_cell_ml/code/forest.py infer --model auto_cell_ml/results/original-image-forest-v1/02-CSU-IS-PCR-filled-and-empty/model --image auto_cell_ml/data/evaluation/02-CSU-IS-PCR-filled-and-empty/image.png --output auto_cell_ml/results/original-image-forest-v1/02-CSU-IS-PCR-filled-and-empty/evaluation
```

Outputs must not already exist. The forest learns center scores from local brightness, color, and edge measurements. It samples negative examples from unmarked circular features, strong edges, the whole image, and positions around marked centers. This does not mean every possible negative location is used. Circle finding supplies training examples only; prediction scores image locations directly. Predicted circles use the median labeled radius, and weaker centers closer than that radius are suppressed. The vote score is not a calibrated probability. Selection of one or two examples in a new image is not implemented.
