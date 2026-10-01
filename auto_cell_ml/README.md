# Example-guided droplet detection

Train, evaluate, and export Icescopy's **General droplets** neural network. It finds water droplets, including water in PCR wells, using marked cells as examples. Freezing events are measured separately by Icescopy's brightness analysis.

Start with **[train_and_evaluate.ipynb](train_and_evaluate.ipynb)**. It includes installation, labeled-image previews, image augmentation, training, evaluation, and model export. Training and downloads are off by default; running the notebook first checks the supplied model.

## Contents

| Folder | Contents |
| --- | --- |
| `examples/real/` | One image and its `.icescopy` circle labels for each of five setups; four images from separate recordings for evaluation |
| `examples/synthetic/` | 40 rendered scenes with positive droplets, negative objects, and fixed fit/validation/calibration assignments |
| `models/` | General droplets 1.0.0: trainable PyTorch weights and a separate model file for Icescopy |
| `code/` | Training, evaluation, image transformations, and export |
| `tests/` | Checks for labels, transformations, training, and model export |
| `results/` | Locally generated runs; excluded from Git |

The **NC State/CIF images** come from Petters and Yadav's [DropFreezingDetection.jl v0.2.0](https://doi.org/10.5281/zenodo.7765097). See [example sources and licensing](examples/README.md) before reusing the images.

## Quick start

Use Python 3.11 in a separate environment. From the repository root:

```sh
python -m pip install -e ".[training]" jupyterlab
python -m jupyter lab auto_cell_ml/train_and_evaluate.ipynb
```

Choose that environment as the notebook kernel. Training supports Apple GPUs through PyTorch **MPS** (Metal Performance Shaders), NVIDIA GPUs through **CUDA**, and the CPU. The installed Icescopy app only needs OpenCV to run exported models; it does not need PyTorch.

The notebook starts from `models/general-droplets-1.0.0.pt`. To train from the original pretrained image encoder instead, use its optional fresh-training section. Every run writes to a new directory and keeps existing weights intact.

## How training works

The network contains 214,332 parameters. Its image encoder starts from TorchVision MobileNetV3-Small weights. It learns droplet centers, small corrections to their positions, and circle radii together. Example image patches tell it which appearance and size to find.

Each training view receives one or two randomly chosen labeled droplets as guidance. Pixels and circle labels are cropped, rotated, reflected, and scaled together; lighting and contrast also vary. Uniform scaling preserves the image's aspect ratio. Views cover the entire source image, including background. They are generated in memory each epoch rather than saved as thousands of files.

**Mark every droplet that should be found in a training image.** Saved circles are the positive targets; other valid positions teach the network what to reject. Only padding outside the source image is ignored. Incomplete labels therefore teach the model to reject real, unmarked droplets. Labels describe circular measurement regions, not exact droplet boundaries.

The supplied model trained first on augmented synthetic fit scenes for three epochs (passes through the training views), then on augmented real images from all five setups for 60 epochs. The final 20 epochs continued the saved weights with a new optimizer and lower learning rates. The notebook can continue those weights with new labeled data without the original pretrained download.

## Evaluate without mixing recordings

`examples/real/datasets.json` identifies each source image by a content hash and assigns its recording to training or evaluation. All transformed views from a training recording stay in training. Evaluation images come from different recordings. There is no independent PKU recording in this module.

The evaluator produces two separate overviews:

- **Training diagnostics:** predictions compared with the saved circles, excluding the two guidance examples. These measure fit to known images.
- **Independent recordings:** predictions using two supplied examples per image. These images have no complete labels, so inspect the overlays; detection counts are not accuracy scores.

A center match allows a distance of at most the larger of 3.5 pixels or 35% of the labeled radius, with one prediction per label. This does not measure circle-boundary accuracy. Results can differ slightly across PyTorch/OpenCV versions and devices.

## Use and distribute a new model

The notebook exports both a trainable `.pt` checkpoint and a versioned `.icescopy-model` file. In Icescopy, open **Preferences → ML → Browse…** and choose the latter, then save. Model updates can be distributed without updating the application.

The app accepts any number of selected guidance cells. It averages their learned appearance features and radii. With no selected cells, it uses a stored training average; this may be less accurate. More examples do not guarantee improvement. Existing cells are excluded from new selections.

Compatible model files use the `icescopy-droplet-onnx-v2` interface: a 64×64 RGB example encoder produces 32 values; a 256×256 RGB detector takes their average and a mean radius, and returns center scores, position corrections, and radii on a 64×64 grid. Inputs use RGB values from 0 to 1. The score threshold is 0.5. Different network implementations must retain this interface to work with the current app.

## Code map

- `data.py`: read saved labels and generate aligned training views.
- `model.py`: network, training loss, pretrained initialization, and ONNX export.
- `train.py`: synthetic training, real-image training, and continued training.
- `infer.py` and `evaluate.py`: predictions, overlays, and training diagnostics.
- `export.py`: versioned app bundles and shareable trainable checkpoints.
- `check_runtime.py`: compare exported app predictions against saved PyTorch predictions.

`forest.py` and `opencv_nn.py` are retained earlier experiments; the notebook does not use them. `image_samples.py` supplies the shared duplicate-suppression routine used by inference.
