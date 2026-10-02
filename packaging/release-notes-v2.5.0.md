# Icescopy 2.5.0

This release adds experimental, example-guided droplet selection. Select a few marked droplets, then use the star tool beside **Edit Cell** to find similar droplets in the current frame. Freezing analysis continues to use the existing brightness and convolution method.

## Droplet selection

- Detect water droplets and filled wells in a single image or video frame. Selected cells guide the appearance and size to find; detection also runs without examples, with potentially lower accuracy.
- Existing cells are protected from duplicate selections. Detection respects the current crop, and added cells can be edited or undone together.
- The completion dialog reports the model version, guidance count, detections, and added cells.
- **Preferences → ML** lets you choose the bundled **General droplets 1.0.0** model or browse for a separate `.icescopy-model` file.
- The app runs the small exported network on the CPU through OpenCV. It does not include PyTorch or require a GPU.

Detection remains experimental. Review the circles before analyzing freezing, especially with unfamiliar instruments, lighting, or empty wells. More guidance examples do not guarantee better results.

## Training and model updates

The repository's [auto_cell_ml module](https://github.com/bochens/Icescopy/tree/v2.5.0/auto_cell_ml) includes an instructional notebook, synthetic examples, labeled images from five setups, separate evaluation images, and trainable weights. Training supports Apple GPUs, NVIDIA GPUs, and CPUs. Model versions can be distributed separately from the app.

The NC State/CIF example images are credited to Petters and Yadav (2023), [DropFreezingDetection.jl v0.2.0](https://doi.org/10.5281/zenodo.7765097), with the upstream license included. Independent evaluation images do not have complete labels; the notebook shows overlays without claiming numerical accuracy on them.

## Other changes

- Avoid unnecessary save prompts when starting a new session without unsaved changes.
- Updated README figures and droplet-detection documentation.

## Downloads

**Mac, Apple Silicon:** download `Icescopy-macos-arm64.zip`, unzip it, and copy `Icescopy.app` into Applications after saving work and closing the old app. This build is signed locally for integrity; it is not Apple-notarized. See the [Mac installation guide](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md#install-on-macos).

**Model only:** `general-droplets-1.0.0.icescopy-model` can be selected in Preferences → ML. It is also bundled in the Mac and Windows apps. `general-droplets-1.0.0.pt` is the separate trainable checkpoint for the notebook, not an app installer.

**Windows:** download [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.5.0/Icescopy-windows-installer.exe) for 64-bit x64 Windows 10 (1809 or later) or Windows 11. Save work and close Icescopy before upgrading, run the installer, then open Icescopy from the Start menu. It installs for your Windows account and includes Python, the required libraries, and the General droplets 1.0.0 model. No separate Python installation or GPU is required.

GitHub displays a SHA-256 checksum beside each uploaded file under **Assets**.

The Windows build includes a compatibility fix for loading droplet models from paths containing non-English characters, such as Windows usernames. Its source is `v2.5.0` plus [the Windows model-path fix](https://github.com/bochens/Icescopy/commit/9e52f31de6831a0ab0178226c2baabba9f02cd7b).
