# Sessions, Export, and Preferences

This page covers session files, relinking, CSV export, and user preferences.

## Session files

Icescopy uses `.icescopy` session files.

These are zip-based bundles that store:

- session metadata
- application state
- result tables as CSV members

The current result bundle members are:

- `grayscale.csv`
- `freeze.csv`
- `freeze_count_timeseries.csv`

## Save a session

Save the session when:

- you have loaded images
- you have annotated cells
- you want a stable place to continue from later

Saving early is useful because later relink and export workflows are simpler when the session already has a known file path.

## Save to a new location

Use Save As when:

- branching a workflow
- preserving a checkpoint
- relocating the working session

## Open a session

Opening a session should restore:

- image list
- cells
- samples
- keyframes and flags
- result tables

If the session opens but images are missing, use relink.

## Relink an image folder

Relinking is needed when:

- the image folder moved
- the session was copied to another machine
- the absolute image paths in the session no longer match the real file location

## Export results

Icescopy can export the tabular outputs as CSV.

Export is useful for:

- downstream analysis
- record keeping
- integration with other tools

## Preferences

Preferences control the default application behavior.

Important preference categories include:

- default sort mode
- sample name pattern
- analysis settings
- display and annotation defaults

## Preference file

The preference file is distinct from a session.

Preferences describe defaults.
A session describes one working analysis state.

## Recommended practice

- treat preferences as global defaults
- treat session files as experiment-specific working state
- export CSVs when you need stable downstream records
