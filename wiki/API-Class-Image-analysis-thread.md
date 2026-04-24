# API Class: `Image_analysis_thread`

Image analysis thread class.

## Source

- Module: [`icescopy_aux`](API-Module-icescopy-aux)
- File: `src/icescopy_aux.py`
- Line: `385`

## Inheritance

- Bases: `QThread`

## Purpose

Image analysis thread class.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `analysis_done` | 387 | Stores analysis done. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_circular_grid_cache` | `__init__` | 434 | Cache entry or cache container for circular grid cache. |
| `_circular_mask_cache` | `__init__` | 433 | Cache entry or cache container for circular mask cache. |
| `convolution_half_window_points` | `__init__` | 425 | Stores convolution half window points. |
| `convolution_ramp_points` | `__init__` | 426 | Stores convolution ramp points. |
| `filePath` | `__init__` | 408 | Stores file path. |
| `freeze_finder_detect_brightening` | `__init__` | 427 | Stores freeze finder detect brightening. |
| `freeze_finder_prominence` | `__init__` | 423 | Stores freeze finder prominence. |
| `freeze_finder_tail_extend_points` | `__init__` | 424 | Stores freeze finder tail extend points. |
| `freeze_finder_width` | `__init__` | 422 | Geometry value for freeze finder width. |
| `freeze_output_path` | `__init__` | 432 | Filesystem path for freeze output path. |
| `freeze_result_headers` | `__init__` | 430 | Column header data for freeze result headers. |
| `freeze_result_rows` | `__init__` | 431 | Row-oriented data for freeze result rows. |
| `grayscale_result_headers` | `__init__` | 428 | Column header data for grayscale result headers. |
| `grayscale_result_rows` | `__init__` | 429 | Row-oriented data for grayscale result rows. |
| `imageFolderPath` | `__init__` | 421 | Stores image folder path. |
| `imageNames` | `__init__` | 410 | Stores image names. |
| `imagePaths` | `__init__` | 409 | Stores image paths. |
| `image_edit_contrast` | `__init__` | 417 | Stores image edit contrast. |
| `image_edit_crop_state` | `__init__` | 419 | State bundle for image edit crop state. |
| `image_edit_exposure` | `__init__` | 416 | Stores image edit exposure. |
| `image_edit_uniform_exposure_offsets` | `__init__` | 418 | Offset values for image edit uniform exposure offsets. |
| `list_of_cell_items` | `__init__` | 414 | Stores list of cell items. |
| `list_of_red_flags` | `__init__` | 415 | Stores list of red flags. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(filePath, imagePaths, imageNames, list_of_cell_items, list_of_red_flags, image_edit_exposure=0.0, image_edit_contrast=0.0, image_edit_uniform_exposure_offsets=None, image_edit_crop_state=None, freeze_finder_width=DEFAULT_FREEZE_FINDER_WIDTH, freeze_finder_prominence=DEFAULT_FREEZE_FINDER_PROMINENCE, freeze_finder_tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS, convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS, freeze_finder_detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING)` | 389 | Initializes the instance. |
| `run()` | 436 | Runs the primary task for this worker or dialog. |
| `gray_scale_mean(image_path, circle_pixel_positions, circle_sizes)` | 561 | Implements gray scale mean. |
| `get_cached_circular_mask(height, width, center_x, center_y, radius)` | 625 | Returns cached circular mask. |
