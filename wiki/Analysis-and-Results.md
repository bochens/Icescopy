# Analysis and Results

This page explains how analysis runs, what invalidates it, and how to read the output tables.

## Run analysis

Run analysis after:

- image order is correct
- cells are annotated
- keyframes are in place if needed
- samples are assigned if grouping matters

The analysis pipeline produces:

- grayscale measurements by frame and cell
- freeze event rows
- freeze count timeseries outputs if temperature data is present

## What invalidates analysis

Analysis should be rerun after changes to inputs that affect the measurement path.

Typical invalidating changes are:

- cell geometry changes
- keyframe changes
- crop changes
- exposure or contrast changes
- uniform exposure changes
- analysis preference changes

## Results tables

Icescopy currently works with three main result tables:

- Measurements
- Freeze Events
- Freeze Count Timeseries

The session file stores these as CSV tables inside the `.icescopy` zip bundle.

## Measurements

The measurements table stores grayscale timeseries derived from the annotated cells.

Use it when you need:

- the numeric grayscale history per cell
- the frame-by-frame measurement basis for freeze finding

## Freeze Events

The freeze-events table stores detected or manually corrected freeze rows.

Use it when you need:

- the event frame for each cell
- a compact event-level output instead of full timeseries

## Freeze Count Timeseries

The freeze count timeseries table merges image-derived freeze counts with imported external temperature timeseries.

Use it when you need:

- temperature-aligned freeze counts
- sample-level or grouped output for downstream interpretation

## Grayscale plot

The grayscale plot is the main review surface for timeseries behavior.

Use it to:

- inspect grayscale change over time
- compare detected freeze frames against the timeseries
- tune freeze-finding settings

## Freeze finding

Freeze finding depends on the configured detection settings.

The current app supports both:

- darkening-based detection
- brightening-based detection

That is controlled by the analysis preference for detection polarity.

## Tuning guidance

If the detector misses real events or creates false positives, review:

- convolution settings
- prominence threshold
- width settings
- whether the event is better represented as brightening instead of darkening

## Interpretation notes

The app gives a structured best estimate from the image sequence.
Final scientific interpretation still depends on:

- image quality
- annotation quality
- acquisition cadence
- external temperature quality if used
