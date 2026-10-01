# Automatic cell detection

Experimental droplet detection for Icescopy. The current direction is a CPU random forest using OpenCV's built-in trainer, with one model per setup. Neural training has been stopped before fitting a model.

## Folder layout

- `code/data.py`: reusable crop generation with images and circles transformed together.
- `code/model.py`, `code/train.py`, `code/infer.py`: tested neural prototype, retained untrained. These are not the active training approach.
- `tests/`: focused checks for geometry, negative supervision, image decoding, and model operations.
- `data/train/<setup>/`: manually labeled images and their `.icescopy` sessions.
- `data/evaluation/<setup>/`: images from separate recordings. Label availability is recorded explicitly.
- `data/augmented/`: actual training PNGs, circle JSON files, padding masks, and a contact sheet per generation. CSU IS currently has 240 varied crops.
- `data/synthetic/`: preserved synthetic images, excluded from the next training run.
- `pretrained/`: the original downloaded MobileNetV3-Small weights.
- `results/`: trained weights, measurements, and detection previews; no trained model is currently retained.
- `.venv/`: local Python dependencies, excluded from Git.

Private images, labels, weights, and results are excluded from Git. Keep training data here, not in the application's `output/` directory.

## Data rules

- The private `data/datasets.json` records original sources, file hashes, relative local paths, recording assignments, and label status. `data/README.md` summarizes the available recordings.
- Only manually marked circles define training targets. Other valid image locations are negative. No separately marked negative regions are required.
- Keep every frame and transformation from a recording in the same partition. Never describe a crop of the training image as an independent evaluation image.
- Crop, rotate, flip, scale uniformly, and adjust lighting. Transform circles with the image and save the actual training PNGs with matching labels.
- Run on the separate evaluation images and show overlays for visual inspection. Evaluation labeling is not required. Do not report accuracy percentages without reference labels.
- Session image links are relative to the session directory. Resource paths in code must also be portable; do not add aliases or path-search fallbacks.
- Some CSU images are 16-bit grayscale PNGs. Decode their full intensity range; converting them directly to 8-bit RGB with clipping can turn them white.

## Handoff

PKU source searching is stopped. Four setups have separate evaluation images. `data.py --setup SETUP --output NEW_DIRECTORY` generates 240 crops by default; the default manifest is `data/datasets.json`. The generator reads training entries only. Test with `python -m pytest auto_cell_ml/tests -q` in the development environment. Torch import dependencies were repaired locally; they are not app dependencies. No neural fitting or new UI work has started. Next: connect the saved crops to OpenCV random-forest training and show predictions on separate recordings. The app's existing forest uses scikit-learn and an older labeling rule; it must not be treated as the new implementation. Previous experiments remain in Git history; do not restore their folder tree.
