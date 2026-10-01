# Automatic cell detection

Experimental droplet detection for Icescopy. The active approach is a small neural network trained locally with OpenCV ANN_MLP, one model per setup, directly from its original labeled image. It is not integrated into the app. Random-forest development is stopped. The downloaded neural weights have been deleted; this network trains from scratch without PyTorch.

## Folder layout

- `code/opencv_nn.py`: active OpenCV neural training, model loading, and single-image prediction.
- `code/image_samples.py`: shared image reading, labeled-center/background sampling, and duplicate removal.
- `code/forest.py`: abandoned forest experiment, retained as source history.
- `code/data.py`: trusted original-image/session reader and inactive crop generator.
- `code/model.py`, `code/train.py`, `code/infer.py`: earlier PyTorch prototype, retained untrained. These are not the active training approach.
- `tests/`: focused checks for geometry, negative supervision, image decoding, and model operations.
- `data/train/<setup>/`: manually labeled images and their `.icescopy` sessions.
- `data/evaluation/<setup>/`: images from separate recordings. Label availability is recorded explicitly.
- `data/augmented/`: earlier generated crops, retained but excluded from current training.
- `data/synthetic/`: preserved synthetic images, excluded from the next training run.
- `results/`: experimental models, measurements, and detection previews.
- `.venv/`: local Python dependencies, excluded from Git.

Private images, labels, weights, and results are excluded from Git. Keep training data here, not in the application's `output/` directory.

## Data rules

- The private `data/datasets.json` records original sources, file hashes, relative local paths, recording assignments, and label status. `data/README.md` summarizes the available recordings.
- Only manually marked circles define training targets. Other valid image locations are negative. No separately marked negative regions are required.
- Keep every frame and transformation from a recording in the same partition. Never describe a crop of the training image as an independent evaluation image.
- Establish that the network can learn the original labeled image first. Neural augmentation is authorized: transform pixels and labels together and cover background as well as marked centers. Synthetic-first training is a separate experiment, not evidence that real-image detection works.
- Run on the separate evaluation images and show overlays for visual inspection. Evaluation labeling is not required. Do not report accuracy percentages without reference labels.
- Session image links are relative to the session directory. Resource paths in code must also be portable; do not add aliases or path-search fallbacks.
- Some CSU images are 16-bit grayscale PNGs. Decode their full intensity range; converting them directly to 8-bit RGB with clipping can turn them white.

## Handoff

PKU source searching is stopped. Four setups have separate evaluation images. Earlier forest results remain under `results/random-forest-v1/`; no further forest fits are planned. The current neural baseline uses original labeled images only; augmented training and synthetic-first initialization are requested next, after checking whether the model can fit the original labels. No new UI is being built. Check it with `python -m pytest auto_cell_ml/tests/test_data.py auto_cell_ml/tests/test_opencv_nn.py -q` in the Icescopy environment. Inactive PyTorch tests require the separate development environment. The app's existing detector is not this experimental implementation. Previous experiments remain in Git history; do not restore their folder tree.

## Original-image experiment

From the repository root, using a Python environment with the app's dependencies:

```sh
python auto_cell_ml/code/opencv_nn.py train --manifest auto_cell_ml/data/datasets.json --setup 02-CSU-IS-PCR-filled-and-empty --output auto_cell_ml/results/opencv-nn-v1/02-CSU-IS-PCR-filled-and-empty/model
python auto_cell_ml/code/opencv_nn.py infer --model auto_cell_ml/results/opencv-nn-v1/02-CSU-IS-PCR-filled-and-empty/model --image auto_cell_ml/data/evaluation/02-CSU-IS-PCR-filled-and-empty/image.png --output auto_cell_ml/results/opencv-nn-v1/02-CSU-IS-PCR-filled-and-empty/evaluation
```

Outputs must not already exist. The network learns from 15×15 RGB pixel neighborhoods scaled to the median marked radius. These patches are read in memory from the original image, not saved as generated training images. Unmarked circular features, strong edges, spatial background, and positions around marked centers supply sampled negatives; not every possible location is used. Circle finding supplies training negatives only; prediction scores image locations directly. Predicted circles use the median labeled radius, and weaker centers closer than that radius are suppressed. The signed network score is not a probability. Selection of one or two examples in a new image is not implemented.
