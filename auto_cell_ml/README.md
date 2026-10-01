# Automatic cell detection

Developer-managed training for one general, example-guided droplet detector across all available labeled setups. The model under development uses a pretrained MobileNetV3-Small image encoder and predicts droplet centers and radii. It trains first on augmented synthetic fit scenes, then on augmented user-labeled training images. End-user training UI and the icescopy-train launcher have been deleted. Forest and OpenCV ANN_MLP development are stopped.

## Example-guided selection

At detection time, the user supplies one or two marked cells in the current image. The network receives their image patches and radii along with the image to search. It compares image features with the examples to locate matching droplets. This uses the saved model without retraining it. Existing cells, including the examples, are excluded from new selections.

Training follows the same workflow: each view receives one or two randomly chosen labeled droplets from its source image as examples. Their appearance and size guide the predictions. Examples can come from outside the cropped training view, so background-only crops still have valid examples. All labeled centers remain positive targets, and all other valid positions are negative. Image and label transformations stay aligned; reference patches receive the same orientation and lighting changes as the search image.

The model requires examples; there is no unconditioned detection fallback. Checks that predictions depend on the examples are necessary, but only results on separate recordings can demonstrate useful detection.

## Working files

- `code/model.py`: CNN and loss for centers, offsets, and radii.
- `code/train.py`: staged synthetic and labeled-data training, shared across all selected setups.
- `code/infer.py`: single-image detection and overlays.
- `code/evaluate.py`: predictions on all training images and separate evaluation recordings, using fixed example selections.
- `code/data.py`: trusted source reader, aligned image/label transforms, and training views.
- `code/image_samples.py`, `code/forest.py`, `code/opencv_nn.py`: inactive patch-classifier experiments.
- `tests/`: focused geometry, supervision, model, and storage checks.
- `data/train/<setup>/`: original images and user-labeled `.icescopy` sessions.
- `data/evaluation/<setup>/`: separate recordings for visual evaluation.
- `data/synthetic/`: preserved procedural scenes with filled and empty targets; only the fit partition may train a model.
- `data/augmented/`: earlier generated images, preserved but not required for the active in-memory pipeline.
- `pretrained/`: official MobileNetV3-Small weights and verified source/hash metadata.
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

The example-guided pretrained model has now completed two Apple-GPU runs: three synthetic passes followed by either 10 or 40 passes through newly augmented real views. The longer run took 362 seconds, has 214,332 parameters, and produces a roughly 0.93 MB model. With two fixed marked examples and a fixed 0.5 score threshold, the training-image checks were:

| Setup | Remaining labeled cells | Found after 10 passes | Found after 40 passes | Extras after 40 passes |
| --- | ---: | ---: | ---: | ---: |
| CSU cold stage | 48 | 40 | 45 | 0 |
| CSU IS PCR | 158 | 138 | 150 | 0 |
| PKU | 88 | 49 | 81 | 0 |
| TAMU | 14 | 12 | 13 | 0 |
| CIF | 103 | 52 | 78 | 0 |

Each row excludes the two supplied examples. Matches require one-to-one centers within max(3.5 pixels, 35% of labeled radius); this does not measure circle-boundary accuracy. These are training diagnostics, not independent accuracy. Separate-recording overlays still show missed droplets, especially CIF. The independent images produced 40, 167, 13, and 59 new selections respectively, plus two supplied examples each; those counts are not accuracy scores. GPU inference took 0.03–0.46 seconds per image in the longer-run evaluation, excluding model loading.

Single-example training checks also ran without retraining: CSU cold stage 45/49, PCR 150/159, PKU 81/89, TAMU 14/15, and CIF 82/104 remaining labels matched, with no extras in those checks. Results depend on the selected example; more examples do not guarantee better output.

Results are preserved in `results/example-guided-general-v1/` and `results/example-guided-general-v1-longer/`. The latter contains `evaluation/overview.jpg`, detailed overlays, `summary.json`, and `one-example-check.json`. No user source image or saved session was overwritten.

## Handoff

Current goal: improve remaining misses in the tested, developer-managed, example-guided general model. End-user training UI is removed. The official MobileNetV3-Small ImageNet weights under `pretrained/` were verified by SHA-256 and strict state loading. The image encoder, example comparison, and prediction layers train together; synthetic and real stages update the same weights. Model format is `icescopy-droplet-mobilenet-examples-v4`; no plain-detector fallback.

All five labeled training setups are selected for the general model. The 20 synthetic fit scenes contain 835 targets and 433 explicitly empty circles; synthetic validation/calibration scenes remain excluded. Synthetic source paths in old metadata are stale: use the verified adjacent scene-ID PNG contract only. Training views cover each entire source image and each marked circle per epoch, with aligned rotation, reflection, uniform scaling, and lighting changes. No extra generated image files are needed.

The real run must use `--device mps`, as requested. Apple GPU availability is verified outside the sandbox; it appears unavailable inside. PyTorch stays in the developer environment. ONNX export remains unverified because the optional dependency is absent; the app does not yet load this CNN format. Four separate real recordings are available for visual evaluation; PKU source searching is stopped. Preserve source data and previous results. No app packaging, release, or push is requested.

Evaluation examples are saved in `data/evaluation/examples.json`, chosen visually before inspecting the new predictions. They are inference inputs, not complete evaluation labels. Training checks use two fixed source-label indices and match only the remaining labels against new detections. This keeps supplied examples out of the reported detection total. The independent recordings receive overlays without accuracy claims.
