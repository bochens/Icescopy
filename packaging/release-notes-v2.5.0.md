# Icescopy 2.5.0

## Experimental droplet selection

Select a few marked droplets, then use the **star tool** beside **Edit Cell** to find similar droplets or filled wells in the current frame.

- Detection respects the crop and avoids duplicating existing cells. Edit or undo the added selections together.
- Choose the bundled **General droplets 1.0.0** model or load a compatible `.icescopy-model` file in **Preferences → ML**.
- Detection runs on the CPU; a GPU is not required.
- Load models from paths containing non-English characters on Windows.

Review detected circles before analyzing freezing.

## Training and model updates

The [training notebook](https://github.com/bochens/Icescopy/blob/v2.5.0/auto_cell_ml/train_and_evaluate.ipynb) includes synthetic scenes, labeled examples, evaluation images, and trainable weights. Continue training the supplied model or train a compatible model for your setup, then load it in Icescopy.

NC State/CIF examples are from Petters and Yadav (2023), [DropFreezingDetection.jl v0.2.0](https://doi.org/10.5281/zenodo.7765097).

## Model downloads

- [general-droplets-1.0.0.icescopy-model](https://github.com/bochens/Icescopy/releases/download/v2.5.0/general-droplets-1.0.0.icescopy-model): load in **Preferences → ML**; also bundled with the app.
- [general-droplets-1.0.0.pt](https://github.com/bochens/Icescopy/releases/download/v2.5.0/general-droplets-1.0.0.pt): weights for further training.

## Downloads

Save your work and close Icescopy before updating.

- **macOS, Apple Silicon:** [Icescopy-macos-arm64.zip](https://github.com/bochens/Icescopy/releases/download/v2.5.0/Icescopy-macos-arm64.zip). Unzip and move **Icescopy.app** to **Applications**. See [macOS opening instructions](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md#install-on-macos).
- **Windows 10 (1809 or later) / 11, x64:** [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.5.0/Icescopy-windows-installer.exe). Run the installer.
