# Automatic cell detection

Developer-managed training for one general, example-guided droplet detector across all available labeled setups. The model under development uses a pretrained MobileNetV3-Small image encoder and predicts droplet centers and radii. It trains first on augmented synthetic fit scenes, then on augmented user-labeled training images. End-user training UI and the icescopy-train launcher have been deleted. Forest and OpenCV ANN_MLP development are stopped.

## Example-guided selection

At detection time, the user may select any number of marked cells in the current image. The network receives their image patches and radii along with the image to search. It compares image features with the examples to locate matching droplets. This uses the saved model without retraining it. Existing cells, including the examples, are excluded from new selections.

Training follows the same workflow: each view receives one or two randomly chosen labeled droplets from its source image as examples. Their appearance and size guide the predictions. Examples can come from outside the cropped training view, so background-only crops still have valid examples. All labeled centers remain positive targets, and all other valid positions are negative. Image and label transformations stay aligned; reference patches receive the same orientation and lighting changes as the search image.

With no selected cells, the app uses an average appearance descriptor and radius derived from the training labels, balanced equally across setups. This generic starting point may be less accurate. With selected cells, their learned appearance descriptors and radii are averaged. This accepts any number without retraining for each count. More examples do not guarantee better results.

## Working files

- `code/model.py`: CNN and loss for centers, offsets, and radii.
- `code/train.py`: staged synthetic and labeled-data training, shared across all selected setups.
- `code/infer.py`: single-image detection and overlays.
- `code/export.py`: export the two small app networks and the generic training reference.
- `code/check_runtime.py`: compare app inference against saved evaluation predictions.
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

The bundled model is **General droplets 1.0.0** (`general-droplets`) and has 214,332 parameters. Apple GPU training used three passes through augmented synthetic fit scenes, followed by 60 passes through augmented real views from all five setups. The final 20 passes continued the saved 40-pass model with a fresh optimizer and lower learning rates; they took 169 seconds.

With two fixed marked examples and a fixed 0.5 score threshold:

| Setup | Remaining labels | Found | Extras |
| --- | ---: | ---: | ---: |
| CSU cold stage | 48 | 47 | 0 |
| CSU IS PCR | 158 | 151 | 0 |
| PKU | 88 | 86 | 0 |
| TAMU | 14 | 14 | 0 |
| CIF | 103 | 99 | 0 |

These are training diagnostics, excluding the two supplied examples. Matches require one-to-one centers within max(3.5 pixels, 35% of labeled radius); this does not measure circle-boundary accuracy. Separate recordings produced 46, 168, 14, and 73 new selections for CSU cold stage, CSU IS PCR, TAMU, and CIF respectively, plus two supplied examples each. Those counts are not accuracy scores. Some droplets are still missed. There is no separate PKU evaluation recording.

The final trainable weights, provenance, and measurements are preserved in `results/example-guided-general-v2/`. Its `evaluation/` directory separates independent-recording overlays from training diagnostics. Earlier runs remain in their own result directories. No source image or saved session was overwritten.

The app's OpenCV 4 CPU runtime was checked on all nine images with 0, 1, 2, 3, and 5 examples. Two-example inference took 0.05–0.83 seconds per image, excluding model loading. Repeating detection with the previous results protected added no duplicates. The five training-image counts were unchanged. Independent CPU counts were 45, 170, 14, and 73: three borderline detections crossed the fixed threshold compared with the saved Apple-GPU evaluation. OpenCV versions round some reference-crop pixels differently; broad response peaks can also move slightly. Identical-input network outputs agreed with PyTorch to within 0.000032 in a checked real-image tile. Detailed comparisons are in `results/example-guided-general-v2/runtime-check/summary.json`.

## Future training and app export

PyTorch and ONNX export dependencies stay in the developer environment. The application runs the exported networks with OpenCV on the CPU; it does not require PyTorch or update model weights. The two app networks total about 1.67 MB. Splitting example encoding from image detection allows arbitrary example counts without changing the learned weights.

Keep `results/example-guided-general-v2/model.pt`, `data/datasets.json`, the labeled source files, synthetic fit scenes, and the pretrained encoder. Continue developer training into a new result directory, for example:

```sh
.venv/bin/python code/train.py \
  --manifest data/datasets.json --all-setups \
  --pretrained pretrained/mobilenet_v3_small-047dcff4.pth \
  --synthetic-manifest data/synthetic/labels.json \
  --initial-model results/example-guided-general-v2/model.pt \
  --synthetic-epochs 0 --epochs 20 \
  --encoder-learning-rate .0001 --head-learning-rate .0005 \
  --synthetic-views 64 --views 240 --size 256 --batch-size 8 \
  --threads 4 --device mps --output results/NEW-RUN
```

Commands in this section run from `auto_cell_ml/`. This starts a fresh optimizer from the saved weights. Source hashes and training settings are checked before continuing. Preserve the separate evaluation recordings; do not use them for training.

After evaluating a new model, export to a new directory:

```sh
.venv/bin/python code/export.py \
  --model-path results/NEW-RUN/model.pt \
  --manifest data/datasets.json --output results/NEW-RUN/app-model \
  --model-id general-droplets --name "General droplets" --version 1.1.0 \
  --archive results/NEW-RUN/general-droplets-1.1.0.icescopy-model \
  --trainable results/NEW-RUN/general-droplets-1.1.0.pt
```

The exporter verifies source provenance and records model hashes. Verify exported predictions with `code/check_runtime.py` with its `--model` option before distributing the new model file. The bundled default can be updated separately when building a later app release. Model files contain learned weights and descriptors, without source images or private file paths. User training controls remain removed.

### Fine-tune with a new labeled dataset

Install the training dependencies in a separate Python environment from the repository root:

```sh
python -m pip install -e ".[training]"
```

The training source can be distributed independently from the desktop build. It uses the repository's session readers; keep the `src/`, `auto_cell_ml/code/`, `pyproject.toml`, and `resources/models/TORCHVISION-LICENSE.txt` layout when distributing source. Use the exporter's `--trainable` option to produce a shareable checkpoint with private source names, paths, and labels removed. Publish this trainable `.pt` file separately from the inference-only `.icescopy-model` file if others should be able to continue training. Do not include private images, sessions, or the original dataset manifest in either release.

Create a new dataset manifest with paths relative to that manifest. Each saved `.icescopy` file must point to the corresponding image, be saved on the labeled frame, and mark **every droplet to keep**. Unmarked valid image areas are background. A minimal entry is:

```json
{
  "setups": [{
    "setup": "my-stage",
    "train": {
      "recording_id": "my-training-recording",
      "image": "train/image.png",
      "session": "train/labels.icescopy",
      "sha256": "SHA-256 of image.png",
      "label_status": "user_marked",
      "circle_count": 40
    },
    "evaluation": {}
  }]
}
```

Use separate recordings for evaluation. Crop, rotate, reflect, scale uniformly, and vary lighting during training; the code transforms the circle labels with the image. All augmented views of the training recording remain training data.

From `auto_cell_ml/`, fine-tune the trainable checkpoint on the new manifest:

```sh
python code/train.py --manifest data/my-dataset.json --all-setups \
  --finetune-model /path/to/model.pt --synthetic-epochs 0 \
  --epochs 20 --size 256 --views 240 --batch-size 8 --threads 4 \
  --encoder-learning-rate .0001 --head-learning-rate .0005 \
  --device mps --output results/MY-NEW-RUN
```

Use `mps` on a supported Apple GPU, `cuda` in a CUDA-enabled PyTorch environment, or `cpu`. This command does not need the parent model's private images, synthetic scenes, or original pretrained download. It retains parent-model provenance and records the new data separately. `--initial-model` remains the stricter option for continuing with exactly the same verified sources. Both options create a fresh optimizer and preserve the parent checkpoint.

Export with a new model version after evaluation. The current app contract is `icescopy-droplet-onnx-v2`: a 64×64 RGB example encoder produces a 32-value descriptor; a 256×256 RGB detector accepts that averaged descriptor and a mean radius, and outputs a 4×64×64 map of center scores, x/y offsets, and log radii. RGB inputs use 0–1 values. The model includes its own image normalization. The fixed acceptance threshold is 0.5. Different network implementations must retain this contract; incompatible formats require an app change and are rejected by the loader.
