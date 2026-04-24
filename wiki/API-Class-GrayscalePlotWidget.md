# API Class: `GrayscalePlotWidget`

Dock widget that renders grayscale timeseries, convolution timeseries, and freeze markers.

## Source

- Module: [`icescopy_plot`](API-Module-icescopy-plot)
- File: `src/icescopy_plot.py`
- Line: `8`

## Inheritance

- Bases: `QWidget`

## Purpose

Dock widget that renders grayscale timeseries, convolution timeseries, and freeze markers.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `LEGEND_CELL_LIMIT` | 11 | Stores legend cell limit. |
| `PALETTES` | 13 | Stores palettes. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `_column_map_cache` | `__init__` | 70 | Cache entry or cache container for column map cache. |
| `_convolution_cache` | `__init__` | 73 | Cache entry or cache container for convolution cache. |
| `_data_signature` | `__init__` | 68 | Stores data signature. |
| `_freeze_map_cache` | `__init__` | 71 | Cache entry or cache container for freeze map cache. |
| `_render_signature` | `__init__` | 69 | Stores render signature. |
| `_series_cache_by_cell` | `__init__` | 72 | Cache entry or cache container for series cache by cell. |
| `cell_ids` | `__init__` | 55 | Stores cell ids. |
| `convolution_half_window_points` | `__init__` | 58 | Stores convolution half window points. |
| `convolution_line_width` | `__init__` | 62 | Geometry value for convolution line width. |
| `convolution_ramp_points` | `__init__` | 59 | Stores convolution ramp points. |
| `convolution_view_box` | `__init__` | 100 | Stores convolution view box. |
| `current_frame_color` | `__init__` | 65 | Current value for frame color. |
| `current_frame_line` | `__init__` | 67 | Current value for frame line. |
| `current_frame_width` | `__init__` | 66 | Current value for frame width. |
| `current_image_index` | `__init__` | 56 | Current value for image index. |
| `freeze_line_color` | `__init__` | 63 | Color setting for freeze line color. |
| `freeze_line_width` | `__init__` | 64 | Geometry value for freeze line width. |
| `freeze_rows` | `__init__` | 54 | Row-oriented data for freeze rows. |
| `grayscale_headers` | `__init__` | 52 | Column header data for grayscale headers. |
| `grayscale_rows` | `__init__` | 53 | Row-oriented data for grayscale rows. |
| `message_label` | `__init__` | 75 | Label widget for message label. |
| `plot_item` | `__init__` | 95 | Stores plot item. |
| `plot_widget` | `__init__` | 84 | Qt widget reference for plot widget. |
| `stack` | `__init__` | 107 | Stores stack. |
| `tail_extend_points` | `__init__` | 57 | Stores tail extend points. |
| `timeseries_line_width` | `__init__` | 61 | Geometry value for timeseries line width. |
| `timeseries_palette` | `__init__` | 60 | Stores timeseries palette. |

## Methods

### Computation and construction

| Method | Line | Explanation |
| --- | --- | --- |
| `_build_data_signature(headers, rows, freeze_rows)` | 241 | Implements build data signature. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None)` | 48 | Initializes the instance. |
| `sizeHint()` | 112 | Implements size hint. |
| `minimumSizeHint()` | 115 | Implements minimum size hint. |
| `set_current_image_index(current_image_index)` | 198 | Sets current image index. |
| `_palette_colors()` | 205 | Implements palette colors. |
| `_timeseries_pen(series_index)` | 208 | Implements timeseries pen. |
| `_convolution_pen(series_index)` | 213 | Implements convolution pen. |
| `_freeze_pen()` | 218 | Implements freeze pen. |
| `_current_frame_pen()` | 221 | Implements current frame pen. |
| `_show_message(message)` | 224 | Implements show message. |
| `_show_plot()` | 228 | Implements show plot. |
| `_grayscale_column_map()` | 268 | Implements grayscale column map. |
| `_freeze_index_map()` | 288 | Implements freeze index map. |
| `_series_for_cell(cell_id)` | 308 | Implements series for cell. |
| `_convolution_for_cell(cell_id, y_values)` | 341 | Implements convolution for cell. |
| `_selected_series()` | 372 | Implements selected series. |
| `_configure_data_item(data_item)` | 382 | Implements configure data item. |
| `_freeze_segment_arrays(freeze_indices, y_min, y_max)` | 388 | Implements freeze segment arrays. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `invalidate_render_cache()` | 118 | Invalidates render cache. |
| `update_plot_data(grayscale_headers, grayscale_rows, freeze_rows, cell_ids, current_image_index=None, tail_extend_points=0, convolution_half_window_points=0, convolution_ramp_points=0, timeseries_palette='bright', timeseries_line_width=2.0, convolution_line_width=1.0, freeze_line_color=(220, 20, 60, 180), freeze_line_width=1.0, current_frame_color=(255, 204, 0, 220), current_frame_width=2.0)` | 123 | Updates plot data. |
| `_clear_plot()` | 231 | Implements clear plot. |
| `_invalidate_data_caches()` | 258 | Implements invalidate data caches. |
| `update_convolution_view_geometry()` | 264 | Updates convolution view geometry. |
| `refresh_plot()` | 396 | Refreshes plot. |
