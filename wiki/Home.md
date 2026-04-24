# Icescopy Wiki

Icescopy is a desktop application for reviewing freezing-array image sequences, annotating droplets or wells, generating grayscale measurement time series, identifying freeze events, and combining image-derived results with external temperature data.

This wiki is the package documentation set for the repository.
It is split into task-focused pages instead of one large manual page.

## Audience

This wiki is written for:

- users running the desktop application
- researchers reviewing image-derived freeze results
- maintainers who need architecture context

## Start here

- [Installation and Setup](Installation-and-Setup)
- [Quick Start](Quick-Start)
- [Annotation Workflow](Annotation-Workflow)
- [Image Editing](Image-Editing)
- [Analysis and Results](Analysis-and-Results)
- [Temperature Import](Temperature-Import)
- [Sessions, Export, and Preferences](Sessions-Export-and-Preferences)
- [Troubleshooting](Troubleshooting)

## Developer and architecture pages

- [Architecture Overview](Architecture-Overview)
- [Cell System](Cell-System)

## Core workflow

Most sessions follow this order:

1. Start a session and load images.
2. Sort the image sequence if needed.
3. Annotate cells or droplets.
4. Assign samples if the experiment uses sample groups.
5. Run analysis.
6. Review the grayscale plot and results tables.
7. Import temperature data if needed.
8. Save the session.
9. Export the results.

## Key concepts

### Session

A `.icescopy` file is the saved working state of an analysis session.
It stores session metadata, application state, and results tables.

### Cell

A cell is the annotated region of interest used for grayscale measurement and freeze detection.
Cells have stable IDs and can also be grouped into samples.

### Keyframe

A keyframe stores a known cell layout at a particular frame.
Icescopy interpolates between keyframes to reduce repetitive manual edits.

### Freeze Count Timeseries

Freeze count timeseries combines image-derived freeze counts with external temperature timeseries, including repeated cooling-warming cycles when supported by the imported format.
