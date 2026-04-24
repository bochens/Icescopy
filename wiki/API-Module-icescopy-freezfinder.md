# API Module: `icescopy_freezfinder`

Freeze-finding utility functions and CSV-oriented batch dialog.

## Source

- File: `src/icescopy_freezfinder.py`

## Classes

| Class | Purpose | Page |
| --- | --- | --- |
| `FreezeFinderDialog` | Dialog for batch-running freeze finding from grayscale CSV input. | [FreezeFinderDialog](API-Class-FreezeFinderDialog) |

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `DEFAULT_FREEZE_RESULT_HEADERS` | 11 | Default value for freeze result headers. |
| `DEFAULT_FREEZE_FINDER_WIDTH` | 17 | Default value for freeze finder width. |
| `DEFAULT_FREEZE_FINDER_PROMINENCE` | 18 | Default value for freeze finder prominence. |
| `DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS` | 19 | Default value for freeze finder tail extend points. |
| `DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS` | 20 | Default value for convolution half window points. |
| `DEFAULT_CONVOLUTION_RAMP_POINTS` | 21 | Default value for convolution ramp points. |
| `DEFAULT_ONSET_DIFF_FRACTION` | 22 | Default value for onset diff fraction. |
| `DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING` | 23 | Default value for freeze finder detect brightening. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `build_image_datetime_array(datetime_array, filename_array)` | 26 | Builds image datetime array. |
| `read_grayscale_csv(gsm_file_path)` | 50 | Reads grayscale CSV. |
| `compute_freeze_result_rows(filename_array, image_datetime_array, image_grayscale_data, width=DEFAULT_FREEZE_FINDER_WIDTH, prominence=DEFAULT_FREEZE_FINDER_PROMINENCE, tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS, convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS, detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING, cell_ids=None, interpolated_image_temps=None, correction_func=None)` | 72 | Computes freeze result rows. |
| `refine_event_index_from_raw_timeseries(raw_grayscale, peak_index, left_ip, right_ip, center_offset, max_frame_index, onset_diff_fraction=DEFAULT_ONSET_DIFF_FRACTION, detect_brightening=DEFAULT_FREEZE_FINDER_DETECT_BRIGHTENING)` | 157 | Implements refine event index from raw timeseries. |
| `build_convolution_kernel(signal_length, convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS)` | 224 | Builds convolution kernel. |
| `compute_convolution_center_offset(signal_length, convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS)` | 259 | Computes convolution center offset. |
| `compute_convolution_timeseries(grayscale_values, tail_extend_points=DEFAULT_FREEZE_FINDER_TAIL_EXTEND_POINTS, convolution_half_window_points=DEFAULT_CONVOLUTION_HALF_WINDOW_POINTS, convolution_ramp_points=DEFAULT_CONVOLUTION_RAMP_POINTS)` | 272 | Computes convolution timeseries. |
| `write_freeze_results_csv(output_csv_path, headers, rows)` | 297 | Writes freeze results CSV. |
| `build_freeze_output_path(grayscale_csv_path)` | 306 | Builds freeze output path. |
