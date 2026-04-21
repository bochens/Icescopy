# Icescopy

Icescopy is a desktop application for reviewing image sequences from ice-freezing array experiments, annotating droplets or wells, generating grayscale measurement timeseries, identifying freezing frames, and merging those image-derived results with external temperature data.

## Citation

If you use Icescopy in your work, please cite it as:

Chen, B. (2026). *Icescopy* (Version 2.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.19673845


## What The Software Does

Icescopy is built around four core tasks:

1. Load and sort an image sequence.
2. Mark cells or droplets manually with single-cell or grid tools.
3. Review grayscale measurements and freezing events.
4. Save a reusable session and export result tables.

The current application also supports:

- manual freeze-frame editing
- sample assignment and sample catalog management
- image-wide exposure, contrast, crop, and uniform-exposure adjustments
- CSU `.dat` temperature import
- TAMU Linkam `.xlsx` temperature import
- session save/load with `.icescopy` files

## Project Layout

- [src](/Users/C832577250/Project/Icescopy/src): application source code
- [resources](/Users/C832577250/Project/Icescopy/resources): runtime assets packaged with the app
- [documentation](/Users/C832577250/Project/Icescopy/documentation): developer notes, manual build tooling, and the LaTeX template
- [Icescopy.spec](/Users/C832577250/Project/Icescopy/Icescopy.spec): PyInstaller build specification for the macOS app
- [Icescopy-Manual.pdf](/Users/C832577250/Project/Icescopy/Icescopy-Manual.pdf): tracked PDF copy of the user manual

## Run From Source

Use the `Icescopy` conda environment:

```bash
source /Users/C832577250/miniforge3/bin/activate
conda activate Icescopy
python /Users/C832577250/Project/Icescopy/src/Icescopy.py
```

## Build The macOS App

```bash
source /Users/C832577250/miniforge3/bin/activate
conda activate Icescopy
cd /Users/C832577250/Project/Icescopy
PYINSTALLER_CONFIG_DIR=/tmp/icescopy-pyinstaller \
MPLCONFIGDIR=/tmp/icescopy-mpl \
XDG_CACHE_HOME=/tmp \
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

Build outputs:

- [dist/Icescopy.app](/Users/C832577250/Project/Icescopy/dist/Icescopy.app)
- [dist/Icescopy](/Users/C832577250/Project/Icescopy/dist/Icescopy)
- [dist/Icescopy-macos-arm64.zip](/Users/C832577250/Project/Icescopy/dist/Icescopy-macos-arm64.zip)

These build outputs are generated locally and are not intended to stay tracked in git.

## Documentation

Tracked documentation entry points:

- [Icescopy-Manual.pdf](/Users/C832577250/Project/Icescopy/Icescopy-Manual.pdf)
- [documentation/build_manual_pdf.py](/Users/C832577250/Project/Icescopy/documentation/build_manual_pdf.py)
- [documentation/latex/icescopy-manual-template.tex](/Users/C832577250/Project/Icescopy/documentation/latex/icescopy-manual-template.tex)

The manual covers:

- loading images
- cell annotation workflows
- cursor, add, edit, delete, and pan tools
- image edit controls
- analysis and result tables
- temperature import workflows
- session management and export

## Notes

- The packaged app does not include the repo `README.md`, `documentation/`, or the tracked PDF manual.
- `.icescopy` session files are zip-based bundles containing the saved session state and result tables.
- Local working folders such as `manual/`, `design/`, `tmp/`, `build/`, `dist/`, and `output/` are ignored and are not part of the tracked source tree.
- Please reach out to me if you have a special temperature file format that needs to be paired with the freezing detection workflow, and I will help incorporate it into Icescopy.
