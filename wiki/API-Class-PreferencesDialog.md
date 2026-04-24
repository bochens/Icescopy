# API Class: `PreferencesDialog`

Dialog for editing persisted application preferences.

## Source

- Module: [`icescopy_aux`](API-Module-icescopy-aux)
- File: `src/icescopy_aux.py`
- Line: `723`

## Inheritance

- Bases: `QDialog`

## Purpose

Dialog for editing persisted application preferences.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `category_list` | `__init__` | 858 | Ordered list used for category list. |
| `circle_default_color_field` | `__init__` | 804 | Stores circle default color field. |
| `circle_edit_color_field` | `__init__` | 807 | Stores circle edit color field. |
| `circle_hover_color_field` | `__init__` | 805 | Stores circle hover color field. |
| `circle_label_offset_x_field` | `__init__` | 802 | Stores circle label offset x field. |
| `circle_label_offset_y_field` | `__init__` | 803 | Stores circle label offset y field. |
| `circle_pressed_color_field` | `__init__` | 808 | Stores circle pressed color field. |
| `circle_selected_color_field` | `__init__` | 806 | Stores circle selected color field. |
| `convolution_half_window_points_field` | `__init__` | 778 | Stores convolution half window points field. |
| `convolution_ramp_points_field` | `__init__` | 779 | Stores convolution ramp points field. |
| `default_circle_radius_field` | `__init__` | 741 | Default value for circle radius field. |
| `dot_size_field` | `__init__` | 744 | Stores dot size field. |
| `freeze_finder_detect_brightening_field` | `__init__` | 780 | Stores freeze finder detect brightening field. |
| `freeze_finder_prominence_field` | `__init__` | 776 | Stores freeze finder prominence field. |
| `freeze_finder_tail_extend_points_field` | `__init__` | 777 | Stores freeze finder tail extend points field. |
| `freeze_finder_width_field` | `__init__` | 775 | Stores freeze finder width field. |
| `grid_cell_id_direction_field` | `__init__` | 766 | Stores grid cell ID direction field. |
| `grid_columns_field` | `__init__` | 762 | Stores grid columns field. |
| `grid_horizontal_pitch_field` | `__init__` | 763 | Stores grid horizontal pitch field. |
| `grid_pitch_wheel_step_field` | `__init__` | 773 | Stores grid pitch wheel step field. |
| `grid_preview_fill_color_field` | `__init__` | 810 | Stores grid preview fill color field. |
| `grid_preview_outline_color_field` | `__init__` | 809 | Stores grid preview outline color field. |
| `grid_rotation_field` | `__init__` | 765 | Stores grid rotation field. |
| `grid_rows_field` | `__init__` | 761 | Stores grid rows field. |
| `grid_tilt_wheel_step_field` | `__init__` | 774 | Stores grid tilt wheel step field. |
| `grid_vertical_pitch_field` | `__init__` | 764 | Stores grid vertical pitch field. |
| `main_window` | `__init__` | 726 | Stores main window. |
| `maximum_zoom_field` | `__init__` | 743 | Stores maximum zoom field. |
| `pages` | `__init__` | 863 | Stores pages. |
| `pages_scroll_area` | `__init__` | 873 | Stores pages scroll area. |
| `pen_width_field` | `__init__` | 742 | Stores pen width field. |
| `preference_field_width` | `__init__` | 737 | Geometry value for preference field width. |
| `preference_help_width` | `__init__` | 739 | Geometry value for preference help width. |
| `preference_label_width` | `__init__` | 736 | Geometry value for preference label width. |
| `preference_page_width` | `__init__` | 738 | Geometry value for preference page width. |
| `preview_handle_size_field` | `__init__` | 801 | Stores preview handle size field. |
| `radius_wheel_step_field` | `__init__` | 772 | Stores radius wheel step field. |
| `sample_name_pattern_field` | `__init__` | 748 | Stores sample name pattern field. |
| `saved_preferences` | `__init__` | 727 | Stores saved preferences. |
| `slider_maxzoom_pixel_interval_field` | `__init__` | 745 | Stores slider maxzoom pixel interval field. |
| `slider_tick_pixel_interval_field` | `__init__` | 746 | Stores slider tick pixel interval field. |
| `sort_mode_field` | `__init__` | 754 | Stores sort mode field. |
| `temperature_cycle_warmup_hysteresis_c_field` | `__init__` | 782 | Stores temperature cycle warmup hysteresis c field. |
| `timeseries_convolution_line_width_field` | `__init__` | 796 | Stores timeseries convolution line width field. |
| `timeseries_current_frame_color_field` | `__init__` | 799 | Stores timeseries current frame color field. |
| `timeseries_current_frame_line_width_field` | `__init__` | 800 | Stores timeseries current frame line width field. |
| `timeseries_freeze_line_color_field` | `__init__` | 797 | Stores timeseries freeze line color field. |
| `timeseries_freeze_line_width_field` | `__init__` | 798 | Stores timeseries freeze line width field. |
| `timeseries_line_width_field` | `__init__` | 795 | Stores timeseries line width field. |
| `timeseries_palette_field` | `__init__` | 789 | Stores timeseries palette field. |
| `undo_limit_field` | `__init__` | 747 | Stores undo limit field. |
| `viewer_image_count_field` | `__init__` | 749 | Stores viewer image count field. |

## Methods

### Computation and construction

| Method | Line | Explanation |
| --- | --- | --- |
| `build_field_with_help(widget, help_text)` | 926 | Builds field with help. |
| `build_info_group_box(title, paragraphs)` | 939 | Builds info group box. |
| `build_group_box(title, rows)` | 966 | Builds group box. |
| `build_section_separator()` | 999 | Builds section separator. |
| `build_preferences_page(title, subtitle, groups)` | 1007 | Builds preferences page. |
| `build_general_page()` | 1047 | Builds general page. |
| `build_viewer_page()` | 1062 | Builds viewer page. |
| `build_drawing_page()` | 1074 | Builds drawing page. |
| `build_timeline_page()` | 1116 | Builds timeline page. |
| `build_analysis_page()` | 1128 | Builds analysis page. |
| `build_timeseries_page()` | 1203 | Builds timeseries page. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, parent=None)` | 724 | Initializes the instance. |
| `pref_value(key)` | 896 | Implements pref value. |
| `reset_page_scroll_position()` | 899 | Resets page scroll position. |
| `make_spinbox(minimum, maximum, value)` | 903 | Implements make spinbox. |
| `make_double_spinbox(minimum, maximum, value, decimals)` | 909 | Implements make double spinbox. |
| `make_help_label(text)` | 917 | Implements make help label. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `load_saved_preferences()` | 889 | Loads saved preferences. |
| `save_preferences()` | 1222 | Saves preferences. |

### State serialization

| Method | Line | Explanation |
| --- | --- | --- |
| `restore_visual_defaults()` | 1276 | Restores visual defaults. |
