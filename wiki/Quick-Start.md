# Quick Start

This page is the fastest practical path through a standard Icescopy session.

## Before you start

Have these ready:

- an ordered image sequence
- session metadata such as project name, user name, institution, analysis date, and well volume if you want those fields in exports
- a sample map if cells belong to different samples
- a writable location for the session file
- optional temperature data files if you plan to import them later

## Standard workflow

1. Open Icescopy.
2. Start a new session.
3. Enter session metadata.
4. Add images or add an image folder.
5. Check the image order in the `Images` dock.
6. Annotate cells.
7. Assign samples if needed.
8. Edit sample catalog metadata if you will export sample-level data.
9. Run analysis.
10. Review the `Grayscale Plot` and freeze events.
11. Import temperature data if needed.
12. Review the freeze count timeseries table.
13. Save the session.
14. Export results if needed.

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

Temperature import is a separate step after analysis.
When temperature data is imported, the app builds the freeze count timeseries table from the current freeze events and current sample assignments.

## Set sample metadata

Use the sample catalog when sample-level output matters.

Fill in:

- sample name
- sample long name if useful
- sampling site
- collection start and collection end in `YYYY-MM-DD HH:MM:SS`
- sample type: `air`, `soil`, or `other`
- dilution factor
- type-specific fields such as air volume, filter fraction, suspension volume, and dry mass

Missing sample metadata is exported as `nan` instead of blocking export.
This lets downstream software identify which values are missing.

## Import temperature data

Use one of the temperature importers after freeze events are available:

- standard two-column temperature CSV
- CSU `.dat`
- TAMU Linkam `.xlsx`

The freeze count timeseries output contains `number total` and `number frozen` columns.
It does not calculate or export a `fraction frozen` column.

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
- sample assignment
- whether a crop or image edit is active
- timestamp source and timestamp style for temperature import
- whether the results are stale and need a rerun
