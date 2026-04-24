# Quick Start

This page is the fastest practical path through a standard Icescopy session.

## Before you start

Have these ready:

- an ordered image sequence
- a writable location for the session file
- optional temperature data files if you plan to import them later

## Standard workflow

1. Open Icescopy.
2. Start a new session.
3. Add images or add an image folder.
4. Check the image order in the `Images` dock.
5. Annotate cells.
6. Assign samples if needed.
7. Run analysis.
8. Review the `Grayscale Plot` and the results tables.
9. Save the session.
10. Export results if needed.

## Load images

Use:

- `File -> Add Images...`
- `File -> Add Folder...`

After loading, confirm:

- the image list is populated
- the frame slider covers the full sequence
- the first and last few images are in the expected order

## Annotate cells

Use either:

- single-cell placement
- grid placement

If cells drift during the run:

- add keyframes at frames where the layout visibly changes
- adjust the cell positions there

## Run analysis

Use the analysis command from the app UI after annotation is complete.

The app will populate:

- grayscale measurements
- freeze events
- freeze count timeseries results if external temperature data was imported

## Save early

Save the session near the start of work instead of waiting until the end.

This helps with:

- relinking images later
- resuming work after interruption
- sharing the session file with the image folder structure intact

## If something looks wrong

Check these first:

- image order
- cell placement
- whether a crop or image edit is active
- whether the results are stale and need a rerun
