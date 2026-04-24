# Image Editing

This page describes the image-level edits that affect display and analysis input.

## Available controls

The current image-edit toolset includes:

- histogram review
- exposure
- contrast
- crop
- uniform exposure

These are image-wide transforms, not per-cell transforms.

## Histogram

The histogram helps you judge the intensity distribution of the current frame.

Use it to answer:

- is the image clipped?
- is the contrast too flat?
- is the region of interest using enough dynamic range?

The histogram should be interpreted together with what you see in the viewer.
It is a guide, not the result itself.

## Exposure

Exposure changes the overall brightness of the image.

Use it when:

- the full image is too dark
- the full image is too bright
- you need a clearer review display before annotation or analysis

The current UI blocks mouse-wheel changes on the exposure slider to avoid accidental edits.

## Contrast

Contrast changes the separation between light and dark values.

Use it when:

- event transitions are visually hard to see
- the image has low tonal separation

As with exposure, accidental wheel changes on this control are blocked.

## Crop

Crop restricts the active image region.

This matters because committed crop affects:

- viewer display
- histogram
- grayscale sampling
- analysis results

If you crop, confirm that every annotated cell remains inside the active area.

## Uniform exposure

Uniform exposure uses a reference area to equalize brightness across frames.

This is useful when:

- illumination drifts over time
- one control region should remain visually consistent
- you need frame-to-frame brightness normalization

## What image edit affects

Committed image edits affect downstream processing.

That means they are not just cosmetic.
They can change the inputs used by measurement and freeze detection.

In practice:

- display changes matter
- histogram changes matter
- analysis changes matter

## Undo and redo

Image edits are tracked in history.

That means you can:

- preview changes
- commit them
- undo them if needed

## Practical guidance

- use the smallest edit that makes review and analysis reliable
- avoid over-correcting images
- if you crop, verify the histogram and cell overlay again afterward
