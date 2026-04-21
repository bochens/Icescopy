# Troubleshoot Common Problems

Use this page to resolve the most common session, packaging, and import problems.

## Session Opens But Images Are Missing

Symptom:
- the session opens
- the image list is present
- the images do not resolve

Action:
1. Open `File -> Relink Images Folder...`.
2. Select the folder that contains the session images.

## A Session Was Shared With Another Computer

Cause:
- the saved absolute image paths do not exist on the second machine

Action:
1. Open the session.
2. Relink the image folder on the new machine.

## The Built App Does Not Launch

Cause:
- you are running the intermediate PyInstaller `build/` output instead of the packaged app

Do not run:
- `build/Icescopy/Icescopy`

Run one of these instead:
- `dist/Icescopy.app`
- `dist/Icescopy.app/Contents/MacOS/Icescopy`
- `dist/Icescopy/Icescopy`

## Packaging Fails With Cache Or Permission Errors

Use temporary cache locations during build:

```bash
PYINSTALLER_CONFIG_DIR=/tmp/icescopy-pyinstaller \
MPLCONFIGDIR=/tmp/icescopy-mpl \
XDG_CACHE_HOME=/tmp \
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

## Temperature Import Looks Wrong

Check these first:
- the correct importer was used
- sample names match where required
- the reset temperature is appropriate for the run
- cycle warm-up hysteresis is not too small
- current freeze annotations are correct

Remember:
- CSU uses the `.dat` file as the authoritative picture-to-time mapping
- TAMU uses filename time plus interpolation from the Linkam trace

Also check:
- whether sample names were finalized before CSU import
- whether blank samples were selected only for CSU
- whether the current freeze frames are correct before import

## A New Cycle Appears At The Wrong Time

Cause:
- reset detection depends on both `Reset After Warmed To (°C)` and `Cycle Warm-Up Hysteresis (°C)`

Action:
1. Review the chosen reset temperature.
2. Increase cycle warm-up hysteresis if minor temperature jitter is creating false cycle boundaries.

## Result Tables Look Stale

Cause:
- the session state changed after the table was generated

Action:
1. Re-run analysis after changing cells, freeze annotations, samples, or image-edit settings.
2. Re-run temperature import after changing freeze annotations or sample assignments.

Notes:
- `Cell Edit` and `Image Edit` can preserve existing tables in the session state
- preserved tables are not automatically recomputed
- image add, image removal, and image reorder operations invalidate analysis results

## Cells Drift Off The Droplets During The Run

Cause:
- the geometry changes across frames but only one static cell layout is defined

Action:
1. Add keyframes at frames where the layout visibly changes.
2. Edit cell geometry on those keyframes.
3. Scrub between keyframes and confirm the interpolation is accurate.
4. Re-run analysis after the geometry is corrected.

## Freeze Finding Misses Real Events Or Calls Too Many

Cause:
- the detector parameters do not match the signal shape in the current data

Action:
1. Use the `Grayscale Plot` instead of guessing from the tables alone.
2. Compare the solid grayscale trace and dashed convolution trace against the image sequence.
3. Adjust `Peak Prominence` and `Peak Width` first.
4. Adjust convolution parameters only after the basic event thresholding is close.

## The Packaged App Is Large

Cause:
- the application bundles PySide6, OpenCV, NumPy, Pandas, SciPy, and PyQtGraph

Result:
- a large bundle size is expected unless dependencies are reduced
