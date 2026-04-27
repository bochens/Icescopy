# Icescopy Wiki

Icescopy is a desktop application for reviewing freezing-array image sequences, annotating droplets or wells, generating grayscale measurement timeseries, identifying freeze events, and combining image-derived results with external temperature data.

This wiki is the package documentation set for the repository.
It is split into task-focused pages instead of one large document.

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

## Recommended workflow

Most sessions should follow this order:

1. Start a session and load images.
2. Sort the image sequence if needed.
3. Annotate cells or droplets.
4. Fill in session metadata and well volume if they matter for export.
5. Assign cells to samples if the experiment uses sample groups.
6. Edit sample catalog metadata before temperature import when possible.
7. Run analysis.
8. Review the grayscale plot and freeze event table.
9. Import temperature data if needed.
10. Review the freeze count timeseries table.
11. Save the session.
12. Export the results.

## Workflow rules that prevent rework

- Image order should be fixed before analysis.
- Cell geometry and keyframes should be stable before analysis.
- Sample assignment should be stable before temperature import.
- Sample catalog metadata can be edited later without rerunning image analysis.
- If sample assignment changes after temperature import, reimport temperature data so the grouped freeze count timeseries is rebuilt.
- Exported freeze count timeseries CSVs include sample metadata comments for downstream tools.

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
The exported data columns are count columns only: `number total` and `number frozen`.
