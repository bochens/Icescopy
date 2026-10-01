# Automatic cell detection

Experimental droplet detection for Icescopy. The current task is preparing separate training and evaluation recordings before rebuilding one small model per setup. Training has not restarted.

## Folder layout

- `code/`: implementation files; currently empty after the experimental code was removed.
- `data/train/<setup>/`: manually labeled images and their `.icescopy` sessions.
- `data/evaluation/<setup>/`: images from separate recordings. Label availability is recorded explicitly.
- `data/augmented/`: future training crops and their transformed labels; currently empty.
- `data/synthetic/`: preserved synthetic images, excluded from the next training run.
- `pretrained/`: the original downloaded MobileNetV3-Small weights.
- `results/`: trained weights, measurements, and detection previews; currently empty.
- `.venv/`: local Python dependencies, excluded from Git.

Private images, labels, weights, and results are excluded from Git. Keep training data here, not in the application's `output/` directory.

## Data rules

- The private `data/datasets.json` records original sources, file hashes, relative local paths, recording assignments, and label status. `data/README.md` summarizes the available recordings.
- Only manually marked circles define training targets. Other valid image locations are negative. No separately marked negative regions are required.
- Keep every frame and transformation from a recording in the same partition. Never describe a crop of the training image as an independent evaluation image.
- Crop, rotate, flip, scale uniformly, and adjust lighting. Transform circles with the image and save the actual training PNGs with matching labels.
- An unlabeled evaluation image is not a labeled accuracy test. Do not invent labels or copy them between timestamps without checking them.
- Session image links are relative to the session directory. Resource paths in code must also be portable; do not add aliases or path-search fallbacks.
- Some CSU images are 16-bit grayscale PNGs. Decode their full intensity range; converting them directly to 8-bit RGB with clipping can turn them white.

## Handoff

The evaluation inventory is being completed before augmentation or fitting. The local Python environment needs repair after an interrupted Torch installation. No new detector has been trained, and existing app trainer code does not establish neural detection quality. The next implementation should remain small and demonstrate results before further UI work. Previous experiments remain in Git history; do not restore their folder tree.
