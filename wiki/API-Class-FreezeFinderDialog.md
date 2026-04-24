# API Class: `FreezeFinderDialog`

Dialog for batch-running freeze finding from grayscale CSV input.

## Source

- Module: [`icescopy_freezfinder`](API-Module-icescopy-freezfinder)
- File: `src/icescopy_freezfinder.py`
- Line: `311`

## Inheritance

- Bases: `QDialog`

## Purpose

Dialog for batch-running freeze finding from grayscale CSV input.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `cancel_button` | `__init__` | 428 | Button widget for cancel button. |
| `convolution_half_window_points_edit` | `__init__` | 412 | Stores convolution half window points edit. |
| `convolution_ramp_points_edit` | `__init__` | 417 | Stores convolution ramp points edit. |
| `freeze_result_headers` | `__init__` | 324 | Column header data for freeze result headers. |
| `freeze_result_rows` | `__init__` | 325 | Row-oriented data for freeze result rows. |
| `input_file1_button` | `__init__` | 344 | Button widget for input file1 button. |
| `input_file1_edit` | `__init__` | 343 | Stores input file1 edit. |
| `input_file2_button` | `__init__` | 355 | Button widget for input file2 button. |
| `input_file2_edit` | `__init__` | 354 | Stores input file2 edit. |
| `input_file3_button` | `__init__` | 366 | Button widget for input file3 button. |
| `input_file3_edit` | `__init__` | 365 | Stores input file3 edit. |
| `ok_button` | `__init__` | 425 | Button widget for ok button. |
| `output_csv_path` | `__init__` | 326 | Filesystem path for output CSV path. |
| `output_file_button` | `__init__` | 377 | Button widget for output file button. |
| `output_file_edit` | `__init__` | 376 | Stores output file edit. |
| `prominence_edit` | `__init__` | 402 | Stores prominence edit. |
| `tail_extend_points_edit` | `__init__` | 407 | Stores tail extend points edit. |
| `width_edit` | `__init__` | 396 | Stores width edit. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(default_grayscale_path=None, default_output_dir=None, default_width=DEFAULT_FREEZE_FINDER_WIDTH, default_prominence=DEFAULT_FREEZE_FINDER_PROMINENCE, default_tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS, default_convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, default_convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS)` | 312 | Initializes the instance. |
| `select_input_file1()` | 442 | Implements select input file1. |
| `select_input_file2()` | 453 | Implements select input file2. |
| `select_input_file3()` | 464 | Implements select input file3. |
| `select_output_file()` | 475 | Implements select output file. |
| `run_freeze_finder_script()` | 485 | Implements run freeze finder script. |
| `file_dialog_options()` | 567 | Implements file dialog options. |
