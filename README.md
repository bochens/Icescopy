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

It also supports:

- manual freeze-frame editing
- sample assignment and sample catalog management
- image-wide exposure, contrast, crop, and uniform-exposure adjustments
- CSU `.dat` temperature import
- TAMU Linkam `.xlsx` temperature import
- session save/load with `.icescopy` files

## Notes

- The packaged app does not include the repo `README.md`.
- `.icescopy` session files are zip-based bundles containing the saved session state and result tables.
- Please reach out to me if you have a special temperature file format that needs to be paired with the freezing detection workflow, and I will help incorporate it into Icescopy.
