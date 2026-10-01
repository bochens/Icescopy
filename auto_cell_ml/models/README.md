# General droplets 1.0.0

Model ID: `general-droplets`. Architecture: example-guided MobileNetV3-Small encoder with center, position-correction, and radius outputs; 214,332 parameters.

| File | Purpose |
| --- | --- |
| `general-droplets-1.0.0.pt` | Continue training in the supplied notebook; contains PyTorch weights and public model metadata |
| `general-droplets-1.0.0.icescopy-model` | Load in Icescopy under Preferences → ML; contains ONNX inference networks, metadata, and the encoder license |
| `sha256.json` | Content hashes for checking these files |

Both files represent the same trained network. The app file also stores average guidance features and radius for detection without selected examples. The trainable checkpoint has no optimizer state; continued training starts a new optimizer. Neither model file contains the source images or their circle labels.

Training used three synthetic epochs followed by 60 real-image epochs across the five supplied setups. See the [notebook](../train_and_evaluate.ipynb) for continued training, evaluation, and export with a new version code. The independent evaluation images are not training inputs. PKU has no independent evaluation recording.

The encoder was initialized from TorchVision's MobileNetV3-Small ImageNet weights. Its [license](TORCHVISION-LICENSE.txt) is retained here and inside the app bundle. Icescopy's code license applies to its own training implementation; third-party example image terms and the Petters–Yadav citation are documented in [examples](../examples/README.md).
