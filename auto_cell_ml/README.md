# Automatic cell detection

Experimental, setup-specific droplet detection for Icescopy. No trained model is currently retained. Training is paused.

## Folder layout

- `code/`: the current untrained neural prototype and its required modules.
- `data/train/<setup>/`: your labeled images and `.icescopy` sessions. These are the only authoritative training labels.
- `data/evaluation/`: separate recordings reserved for evaluation. Never use crops from a training recording as independent evaluation.
- `data/augmented/`: visible cropped, rotated, flipped, and lighting-adjusted training images with matching transformed labels. Currently empty.
- `data/synthetic/`: preserved synthetic images, excluded from the next training run.
- `data/archive/`: previous input collections and obsolete image-region splits; not active training inputs.
- `pretrained/`: the original downloaded MobileNetV3-Small weights.
- `results/`: current experiment outputs and the cleanup record. No app builds, environments, or training images belong here.
- `archive/`: superseded experiments and saved workflow scripts, kept as reference because the user requested retaining the code.

## Current code

`code/per_setup_neural.py` contains the new direct-supervision prototype. `joint_model.py`, `neural_model.py`, and `detector.py` are its current dependencies. Their reuse does not imply that previous model weights or accuracy results were acceptable. This prototype has not been trained or validated.

The intended workflow trains one small model for one setup. User circles define the desired positions and sizes; unmarked valid image locations are negative. No manually marked negatives and no circle-finding gate are required. Transform the image and labels together. Only padding is unknown.

Use separate source recordings for training and evaluation. The NC/CIF data contain Experiment 1 and Experiment 2. CSU IS has another recording in the isothermal data folder. Keep every frame and transformation from a recording in the same partition.

The old top-level `training-data/` path has been removed. Paths in the five relocated sessions were updated directly; their circles and other saved analysis content were preserved. No aliases or fallback path logic were added.
