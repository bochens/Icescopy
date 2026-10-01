# Bundled droplet model

**General droplets 1.0.0** (`general-droplets`) is versioned independently of the application. The application uses OpenCV CPU inference. `droplet_reference.onnx` encodes selected cells; `droplet_detector.onnx` finds matching centers and radii. `droplet_detector.json` records hashes, input geometry, the fixed score threshold, and the generic reference used when no cells are selected.

The 214,332-parameter network starts from the first nine feature blocks of TorchVision MobileNetV3-Small, ImageNet weights `mobilenet_v3_small-047dcff4.pth` (SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`). It was trained further on augmented synthetic scenes and labeled droplet images. The TorchVision license is retained beside the models.

Developer training, evaluation, and export code live in `auto_cell_ml/`. The exported files are inference assets; retain the PyTorch training checkpoint separately for future training. No source images or private source paths are bundled here. Detection is experimental and can miss droplets or include unwanted objects.

For separate distribution, package the metadata and both graphs into one `.icescopy-model` file with `auto_cell_ml/code/export.py`. Users select that file in Preferences → ML. Keep this README and the TorchVision license in the bundle.
