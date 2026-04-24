# API Class: `ImageHistogramWidget`

Histogram display widget for image-edit review.

## Source

- Module: [`icescopy_image_edit`](API-Module-icescopy-image-edit)
- File: `src/icescopy_image_edit.py`
- Line: `387`

## Inheritance

- Bases: `QWidget`

## Purpose

Histogram display widget for image-edit review.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_histogram` | `__init__` | 390 | Stores histogram. |
| `_overlay_histogram` | `__init__` | 391 | Stores overlay histogram. |
| `_overlay_scale_max` | `__init__` | 393 | Stores overlay scale max. |
| `_scale_max` | `__init__` | 392 | Stores scale max. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None)` | 388 | Initializes the instance. |
| `set_histogram(histogram, *, overlay_histogram=None, scale_max=None, overlay_scale_max=None)` | 404 | Sets histogram. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `paintEvent(event)` | 423 | Qt paint event handler for this widget. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `clear_histogram()` | 397 | Clears histogram. |
