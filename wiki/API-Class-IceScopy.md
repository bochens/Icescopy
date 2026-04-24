# API Class: `IceScopy`

Main application shell and composition root for the desktop app.

## Source

- Module: [`Icescopy`](API-Module-Icescopy)
- File: `src/Icescopy.py`
- Line: `128`

## Inheritance

- Bases: `QMainWindow`

## Purpose

Main application shell and composition root for the desktop app.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `active_image_panel` | `initData` | 1118 | Stores active image panel. |
| `add_folder_action` | `initUI` | 2380 | Qt action object for add folder action. |
| `add_images_action` | `initUI` | 2379 | Qt action object for add images action. |
| `analysis_progress_navigation_suppressed` | `initData` | 1082 | Tracks whether analysis progress navigation suppressed. |
| `analysis_progress_start_index` | `initData` | 1083 | Zero-based index for analysis progress start index. |
| `analysis_progress_timer` | `initUI` | 2591 | Timer object used for analysis progress timer. |
| `cell_controller` | `__init__` | 197 | Stores cell controller. |
| `cell_items` | `initData` | 1027 | Stores cell items. |
| `cell_records_by_id` | `initData` | 1030 | Stores cell records by ID. |
| `cell_state` | `__init__` | 196 | State bundle for cell state. |
| `cells_dock` | `initUI` | 2716 | Dock widget reference for cells dock. |
| `cells_panel_dirty` | `refresh_cells_panel` | 700 | Tracks whether cells panel dirty. |
| `cells_panel_force_refresh` | `refresh_cells_panel` | 761 | Stores cells panel force refresh. |
| `cells_panel_last_snapshot` | `refresh_cells_panel` | 759 | Stores cells panel last snapshot. |
| `cells_panel_widget` | `initUI` | 2693 | Qt widget reference for cells panel widget. |
| `cells_tree_widget` | `build_cells_panel` | 3346 | Qt widget reference for cells tree widget. |
| `circle_apply_button` | `build_tool_options_panel` | 3167 | Button widget for circle apply button. |
| `circle_cancel_button` | `build_tool_options_panel` | 3169 | Button widget for circle cancel button. |
| `circle_default_color` | `__init__` | 166 | Color setting for circle default color. |
| `circle_edit_color` | `__init__` | 169 | Color setting for circle edit color. |
| `circle_float_button` | `build_tool_options_panel` | 3168 | Button widget for circle float button. |
| `circle_hover_color` | `__init__` | 167 | Color setting for circle hover color. |
| `circle_label_offset_x` | `__init__` | 174 | Geometry value for circle label offset x. |
| `circle_label_offset_y` | `__init__` | 175 | Geometry value for circle label offset y. |
| `circle_offset_x_spinbox` | `build_tool_options_panel` | 3146 | Spin box widget for circle offset x spinbox. |
| `circle_offset_y_spinbox` | `build_tool_options_panel` | 3151 | Spin box widget for circle offset y spinbox. |
| `circle_pressed_color` | `__init__` | 170 | Color setting for circle pressed color. |
| `circle_radius` | `__init__` | 133 | Radius value for circle radius. |
| `circle_radius_spinbox` | `build_tool_options_panel` | 3141 | Spin box widget for circle radius spinbox. |
| `circle_selected_color` | `__init__` | 168 | Color setting for circle selected color. |
| `circle_tool_hint` | `build_tool_options_panel` | 3164 | Help text widget or message for circle tool hint. |
| `circle_tool_page` | `build_tool_options_panel` | 3140 | Page widget for circle tool page. |
| `clear_images_action` | `initUI` | 2382 | Qt action object for clear images action. |
| `console_dock` | `initUI` | 2713 | Dock widget reference for console dock. |
| `context_pixmap_items` | `initData` | 1106 | Stores context pixmap items. |
| `convolution_half_window_points` | `__init__` | 155 | Stores convolution half window points. |
| `convolution_ramp_points` | `__init__` | 156 | Stores convolution ramp points. |
| `current_session_file_path` | `initData` | 1121 | Current value for session file path. |
| `cursor_edit_section_label` | `build_tool_options_panel` | 2939 | Label widget for cursor edit section label. |
| `cursor_freeze_lineedit` | `build_tool_options_panel` | 2940 | Stores cursor freeze lineedit. |
| `cursor_info_edit_separator` | `build_tool_options_panel` | 2938 | Separator widget or layout marker for cursor info edit separator. |
| `cursor_info_label_widgets` | `build_tool_options_panel` | 2922 | Stores cursor info label widgets. |
| `cursor_info_row_widgets` | `build_tool_options_panel` | 2921 | Stores cursor info row widgets. |
| `cursor_info_section_label` | `build_tool_options_panel` | 2920 | Label widget for cursor info section label. |
| `cursor_info_value_labels` | `build_tool_options_panel` | 2923 | Stores cursor info value labels. |
| `cursor_sample_combo` | `build_tool_options_panel` | 2952 | Combo box widget for cursor sample combo. |
| `cursor_sample_combo_catalog_signature` | `invalidate_cursor_sample_combo_cache` | 510 | Stores cursor sample combo catalog signature. |
| `cursor_sample_combo_has_mixed_item` | `invalidate_cursor_sample_combo_cache` | 511 | Stores cursor sample combo has mixed item. |
| `cursor_sample_row` | `build_tool_options_panel` | 2955 | Layout row container for cursor sample row. |
| `cursor_tool_hint` | `build_tool_options_panel` | 2961 | Help text widget or message for cursor tool hint. |
| `cursor_tool_page` | `build_tool_options_panel` | 2919 | Page widget for cursor tool page. |
| `data_table` | `initUI` | 2672 | Stores data table. |
| `default_circle_radius` | `__init__` | 176 | Default value for circle radius. |
| `default_dock_state` | `__init__` | 206 | Default value for dock state. |
| `default_grid_cell_id_direction` | `__init__` | 182 | Default value for grid cell ID direction. |
| `default_grid_columns` | `__init__` | 178 | Number of columns in the active grid definition. |
| `default_grid_horizontal_pitch` | `__init__` | 179 | Default value for grid horizontal pitch. |
| `default_grid_rotation_degrees` | `__init__` | 181 | Default value for grid rotation degrees. |
| `default_grid_rows` | `__init__` | 177 | Number of rows in the active grid definition. |
| `default_grid_vertical_pitch` | `__init__` | 180 | Default value for grid vertical pitch. |
| `delete_tool_hint` | `build_tool_options_panel` | 2967 | Help text widget or message for delete tool hint. |
| `delete_tool_page` | `build_tool_options_panel` | 2966 | Page widget for delete tool page. |
| `deselect_tool_action` | `initUI` | 2412 | Qt action object for deselect tool action. |
| `displayed_image_edit_crop_applied` | `initData` | 1105 | Stores displayed image edit crop applied. |
| `dot_size` | `__init__` | 136 | Size value for dot size. |
| `edit_circle_apply_button` | `build_tool_options_panel` | 3202 | Button widget for edit circle apply button. |
| `edit_circle_cancel_button` | `build_tool_options_panel` | 3204 | Button widget for edit circle cancel button. |
| `edit_circle_cell_id_spinbox` | `build_tool_options_panel` | 3173 | Spin box widget for edit circle cell ID spinbox. |
| `edit_circle_float_button` | `build_tool_options_panel` | 3203 | Button widget for edit circle float button. |
| `edit_circle_offset_x_spinbox` | `build_tool_options_panel` | 3180 | Spin box widget for edit circle offset x spinbox. |
| `edit_circle_offset_y_spinbox` | `build_tool_options_panel` | 3185 | Spin box widget for edit circle offset y spinbox. |
| `edit_circle_radius_spinbox` | `build_tool_options_panel` | 3175 | Spin box widget for edit circle radius spinbox. |
| `edit_circle_tool_hint` | `build_tool_options_panel` | 3199 | Help text widget or message for edit circle tool hint. |
| `edit_circle_tool_page` | `build_tool_options_panel` | 3172 | Page widget for edit circle tool page. |
| `edit_grid_apply_button` | `build_tool_options_panel` | 3314 | Button widget for edit grid apply button. |
| `edit_grid_cancel_button` | `build_tool_options_panel` | 3316 | Button widget for edit grid cancel button. |
| `edit_grid_float_button` | `build_tool_options_panel` | 3315 | Button widget for edit grid float button. |
| `edit_grid_hpitch_spinbox` | `build_tool_options_panel` | 3275 | Spin box widget for edit grid hpitch spinbox. |
| `edit_grid_offset_x_spinbox` | `build_tool_options_panel` | 3290 | Spin box widget for edit grid offset x spinbox. |
| `edit_grid_offset_y_spinbox` | `build_tool_options_panel` | 3295 | Spin box widget for edit grid offset y spinbox. |
| `edit_grid_radius_spinbox` | `build_tool_options_panel` | 3270 | Spin box widget for edit grid radius spinbox. |
| `edit_grid_rotation_spinbox` | `build_tool_options_panel` | 3285 | Spin box widget for edit grid rotation spinbox. |
| `edit_grid_tool_hint` | `build_tool_options_panel` | 3311 | Help text widget or message for edit grid tool hint. |
| `edit_grid_tool_page` | `build_tool_options_panel` | 3269 | Page widget for edit grid tool page. |
| `edit_grid_vpitch_spinbox` | `build_tool_options_panel` | 3280 | Spin box widget for edit grid vpitch spinbox. |
| `edit_group_base_horizontal_pitch` | `__init__` | 188 | Spacing value for edit group base horizontal pitch. |
| `edit_group_base_radii_by_number` | `__init__` | 186 | Stores edit group base radii by number. |
| `edit_group_base_radius` | `__init__` | 185 | Radius value for edit group base radius. |
| `edit_group_base_rotation_degrees` | `__init__` | 190 | Stores edit group base rotation degrees. |
| `edit_group_base_vertical_pitch` | `__init__` | 189 | Spacing value for edit group base vertical pitch. |
| `edit_group_horizontal_pitch_delta` | `__init__` | 191 | Stores edit group horizontal pitch delta. |
| `edit_group_radius_delta` | `__init__` | 187 | Stores edit group radius delta. |
| `edit_group_rotation_delta` | `__init__` | 193 | Stores edit group rotation delta. |
| `edit_group_vertical_pitch_delta` | `__init__` | 192 | Stores edit group vertical pitch delta. |
| `edit_single_base_radius` | `__init__` | 183 | Radius value for edit single base radius. |
| `edit_single_radius_delta` | `__init__` | 184 | Stores edit single radius delta. |
| `edit_tool_action` | `initUI` | 2411 | Qt action object for edit tool action. |
| `flag_toggle_button` | `initUI` | 2607 | Button widget for flag toggle button. |
| `flagframe_list` | `initData` | 1048 | Ordered list used for flagframe list. |
| `frame_status_label` | `initUI` | 2775 | Label widget for frame status label. |
| `freeze_dock` | `initUI` | 2720 | Dock widget reference for freeze dock. |
| `freeze_finder_detect_brightening` | `__init__` | 157 | Stores freeze finder detect brightening. |
| `freeze_finder_prominence` | `__init__` | 153 | Stores freeze finder prominence. |
| `freeze_finder_tail_extend_points` | `__init__` | 154 | Stores freeze finder tail extend points. |
| `freeze_finder_width` | `__init__` | 152 | Geometry value for freeze finder width. |
| `freeze_results_headers` | `apply_manual_freeze_event_indices` | 670 | Column header data for freeze results headers. |
| `freeze_results_rows` | `apply_manual_freeze_event_indices` | 668 | Row-oriented data for freeze results rows. |
| `freeze_table` | `initUI` | 2673 | Stores freeze table. |
| `grayscale_dock` | `initUI` | 2717 | Dock widget reference for grayscale dock. |
| `grayscale_plot_dock` | `initUI` | 2718 | Dock widget reference for grayscale plot dock. |
| `grayscale_plot_widget` | `initUI` | 2675 | Qt widget reference for grayscale plot widget. |
| `grayscale_results_headers` | `initData` | 1069 | Column header data for grayscale results headers. |
| `grayscale_results_rows` | `initData` | 1070 | Row-oriented data for grayscale results rows. |
| `grid_apply_button` | `build_tool_options_panel` | 3264 | Button widget for grid apply button. |
| `grid_cancel_button` | `build_tool_options_panel` | 3266 | Button widget for grid cancel button. |
| `grid_cell_id_direction` | `__init__` | 148 | Stores grid cell ID direction. |
| `grid_columns` | `__init__` | 144 | Number of columns in the active grid definition. |
| `grid_columns_spinbox` | `build_tool_options_panel` | 3213 | Spin box widget for grid columns spinbox. |
| `grid_float_button` | `build_tool_options_panel` | 3265 | Button widget for grid float button. |
| `grid_horizontal_pitch` | `__init__` | 145 | Spacing value for grid horizontal pitch. |
| `grid_hpitch_spinbox` | `build_tool_options_panel` | 3223 | Spin box widget for grid hpitch spinbox. |
| `grid_offset_x_spinbox` | `build_tool_options_panel` | 3238 | Spin box widget for grid offset x spinbox. |
| `grid_offset_y_spinbox` | `build_tool_options_panel` | 3243 | Spin box widget for grid offset y spinbox. |
| `grid_pitch_wheel_step` | `__init__` | 150 | Stores grid pitch wheel step. |
| `grid_preview_fill_color` | `__init__` | 172 | Color setting for grid preview fill color. |
| `grid_preview_floating` | `initData` | 1111 | Stores grid preview floating. |
| `grid_preview_handle_item` | `initData` | 1109 | Stores grid preview handle item. |
| `grid_preview_items` | `initData` | 1108 | Stores grid preview items. |
| `grid_preview_origin_pixels` | `initData` | 1110 | Stores grid preview origin pixels. |
| `grid_preview_outline_color` | `__init__` | 171 | Color setting for grid preview outline color. |
| `grid_radius_spinbox` | `build_tool_options_panel` | 3218 | Spin box widget for grid radius spinbox. |
| `grid_rotation_degrees` | `__init__` | 147 | Stores grid rotation degrees. |
| `grid_rotation_spinbox` | `build_tool_options_panel` | 3233 | Spin box widget for grid rotation spinbox. |
| `grid_rows` | `__init__` | 143 | Number of rows in the active grid definition. |
| `grid_rows_spinbox` | `build_tool_options_panel` | 3208 | Spin box widget for grid rows spinbox. |
| `grid_tilt_wheel_step` | `__init__` | 151 | Stores grid tilt wheel step. |
| `grid_tool_action` | `initUI` | 2410 | Qt action object for grid tool action. |
| `grid_tool_hint` | `build_tool_options_panel` | 3261 | Help text widget or message for grid tool hint. |
| `grid_tool_page` | `build_tool_options_panel` | 3207 | Page widget for grid tool page. |
| `grid_vertical_pitch` | `__init__` | 146 | Spacing value for grid vertical pitch. |
| `grid_vpitch_spinbox` | `build_tool_options_panel` | 3228 | Spin box widget for grid vpitch spinbox. |
| `history_restoring` | `__init__` | 201 | Stores history restoring. |
| `imageNames` | `initData` | 1054 | Stores image names. |
| `imagePaths` | `initData` | 1053 | Stores image paths. |
| `image_cache` | `initData` | 1097 | Cache entry or cache container for image cache. |
| `image_cache_size` | `initData` | 1098 | Cache entry or cache container for image cache size. |
| `image_edit_action` | `initUI` | 2396 | Qt action object for image edit action. |
| `image_edit_contrast` | `initData` | 1035 | Stores image edit contrast. |
| `image_edit_contrast_block` | `build_tool_options_panel` | 3024 | Grouped layout block for image edit contrast block. |
| `image_edit_contrast_header` | `build_tool_options_panel` | 3031 | Header widget or layout object for image edit contrast header. |
| `image_edit_contrast_label` | `build_tool_options_panel` | 3037 | Label widget for image edit contrast label. |
| `image_edit_contrast_separator` | `build_tool_options_panel` | 3061 | Separator widget or layout marker for image edit contrast separator. |
| `image_edit_contrast_slider` | `build_tool_options_panel` | 3049 | Slider widget for image edit contrast slider. |
| `image_edit_contrast_spinbox` | `build_tool_options_panel` | 3041 | Spin box widget for image edit contrast spinbox. |
| `image_edit_crop_angle` | `initData` | 1045 | Angle value for image edit crop angle. |
| `image_edit_crop_apply_button` | `build_tool_options_panel` | 3111 | Button widget for image edit crop apply button. |
| `image_edit_crop_button_row` | `build_tool_options_panel` | 3102 | Layout row container for image edit crop button row. |
| `image_edit_crop_center_x` | `initData` | 1041 | Geometry value for image edit crop center x. |
| `image_edit_crop_center_y` | `initData` | 1042 | Geometry value for image edit crop center y. |
| `image_edit_crop_height` | `initData` | 1044 | Geometry value for image edit crop height. |
| `image_edit_crop_overlay` | `initData` | 1104 | Overlay object used for image edit crop overlay. |
| `image_edit_crop_reset_button` | `build_tool_options_panel` | 3116 | Button widget for image edit crop reset button. |
| `image_edit_crop_section_label` | `build_tool_options_panel` | 3101 | Label widget for image edit crop section label. |
| `image_edit_crop_start_button` | `build_tool_options_panel` | 3106 | Button widget for image edit crop start button. |
| `image_edit_crop_width` | `initData` | 1043 | Geometry value for image edit crop width. |
| `image_edit_exposure` | `initData` | 1034 | Stores image edit exposure. |
| `image_edit_exposure_block` | `build_tool_options_panel` | 2984 | Grouped layout block for image edit exposure block. |
| `image_edit_exposure_header` | `build_tool_options_panel` | 2991 | Header widget or layout object for image edit exposure header. |
| `image_edit_exposure_label` | `build_tool_options_panel` | 2997 | Label widget for image edit exposure label. |
| `image_edit_exposure_separator` | `build_tool_options_panel` | 3022 | Separator widget or layout marker for image edit exposure separator. |
| `image_edit_exposure_slider` | `build_tool_options_panel` | 3010 | Slider widget for image edit exposure slider. |
| `image_edit_exposure_spinbox` | `build_tool_options_panel` | 3001 | Spin box widget for image edit exposure spinbox. |
| `image_edit_histogram_scale_cache` | `initData` | 1102 | Cache entry or cache container for image edit histogram scale cache. |
| `image_edit_histogram_separator` | `build_tool_options_panel` | 2982 | Separator widget or layout marker for image edit histogram separator. |
| `image_edit_histogram_timer` | `initUI` | 2587 | Timer object used for image edit histogram timer. |
| `image_edit_histogram_widget` | `build_tool_options_panel` | 2979 | Qt widget reference for image edit histogram widget. |
| `image_edit_preview_in_progress` | `initData` | 1060 | Tracks whether image edit preview in progress. |
| `image_edit_preview_timer` | `initUI` | 2583 | Timer object used for image edit preview timer. |
| `image_edit_tool_hint` | `build_tool_options_panel` | 3135 | Help text widget or message for image edit tool hint. |
| `image_edit_tool_page` | `build_tool_options_panel` | 2972 | Page widget for image edit tool page. |
| `image_edit_uniform_exposure_area_button` | `build_tool_options_panel` | 3068 | Button widget for image edit uniform exposure area button. |
| `image_edit_uniform_exposure_area_height` | `initData` | 1039 | Geometry value for image edit uniform exposure area height. |
| `image_edit_uniform_exposure_area_width` | `initData` | 1038 | Geometry value for image edit uniform exposure area width. |
| `image_edit_uniform_exposure_area_x` | `initData` | 1036 | Geometry value for image edit uniform exposure area x. |
| `image_edit_uniform_exposure_area_y` | `initData` | 1037 | Geometry value for image edit uniform exposure area y. |
| `image_edit_uniform_exposure_button_row` | `build_tool_options_panel` | 3064 | Layout row container for image edit uniform exposure button row. |
| `image_edit_uniform_exposure_hint` | `build_tool_options_panel` | 3096 | Help text widget or message for image edit uniform exposure hint. |
| `image_edit_uniform_exposure_offsets` | `initData` | 1040 | Offset values for image edit uniform exposure offsets. |
| `image_edit_uniform_exposure_overlay` | `initData` | 1103 | Overlay object used for image edit uniform exposure overlay. |
| `image_edit_uniform_exposure_reset_button` | `build_tool_options_panel` | 3078 | Button widget for image edit uniform exposure reset button. |
| `image_edit_uniform_exposure_run_button` | `build_tool_options_panel` | 3073 | Button widget for image edit uniform exposure run button. |
| `image_edit_uniform_exposure_section_label` | `build_tool_options_panel` | 3063 | Label widget for image edit uniform exposure section label. |
| `image_edit_uniform_exposure_separator` | `build_tool_options_panel` | 3099 | Separator widget or layout marker for image edit uniform exposure separator. |
| `image_index` | `initData` | 1055 | Zero-based index for image index. |
| `image_list_dock` | `initUI` | 2712 | Dock widget reference for image list dock. |
| `image_list_enabled` | `__init__` | 200 | Tracks whether image list enabled. |
| `image_list_entry_ids` | `initData` | 1115 | Stores image list entry ids. |
| `image_list_model` | `initUI` | 2657 | Stores image list model. |
| `image_list_widget` | `initUI` | 2658 | Qt widget reference for image list widget. |
| `image_name_label` | `initUI` | 2788 | Label widget for image name label. |
| `image_preview_timer` | `initUI` | 2580 | Timer object used for image preview timer. |
| `image_slider` | `initUI` | 2572 | Slider widget for image slider. |
| `image_textbox` | `initUI` | 2596 | Stores image textbox. |
| `image_width` | `initData` | 1052 | Geometry value for image width. |
| `import_csu_is_dat_action` | `initUI` | 2392 | Qt action object for import csu is dat action. |
| `import_tamu_linkam_xlsx_action` | `initUI` | 2393 | Qt action object for import tamu linkam xlsx action. |
| `keyframe_cell_items_dict` | `initData` | 1049 | Mapping used for keyframe cell items dict. |
| `keyframe_list` | `initData` | 1047 | Ordered list used for keyframe list. |
| `keyframe_toggle_button` | `initUI` | 2606 | Button widget for keyframe toggle button. |
| `last_committed_image_index` | `initData` | 1056 | Most recently used value for committed image index. |
| `last_freeze_output_path` | `apply_manual_freeze_event_indices` | 671 | Most recently used value for freeze output path. |
| `last_grayscale_output_path` | `initData` | 1067 | Most recently used value for grayscale output path. |
| `last_temperature_calibration_path` | `initData` | 1077 | Most recently used value for temperature calibration path. |
| `last_temperature_import_path` | `initData` | 1076 | Most recently used value for temperature import path. |
| `last_temperature_reset_temperature` | `initData` | 1078 | Most recently used value for temperature reset temperature. |
| `leftButton` | `initUI` | 2604 | Stores left button. |
| `maximum_zoom` | `__init__` | 135 | Stores maximum zoom. |
| `new_session_action` | `initUI` | 2383 | Qt action object for new session action. |
| `next_cell_id` | `initData` | 1029 | Next value to allocate for cell ID. |
| `next_image_list_entry_id` | `initData` | 1116 | Next value to allocate for image list entry ID. |
| `next_sample_id` | `recompute_next_sample_id` | 438 | Next value to allocate for sample ID. |
| `open_session_action` | `initUI` | 2384 | Qt action object for open session action. |
| `output_results_action` | `initUI` | 2391 | Qt action object for output results action. |
| `output_state` | `initData` | 1094 | State bundle for output state. |
| `pan_tool_action` | `initUI` | 2413 | Qt action object for pan tool action. |
| `pen_width` | `__init__` | 134 | Geometry value for pen width. |
| `pending_analysis_before_state` | `initData` | 1085 | Pending value for analysis before state. |
| `pending_analysis_progress_index` | `initData` | 1084 | Pending value for analysis progress index. |
| `pending_image_edit_histogram_apply_crop` | `initData` | 1062 | Pending value for image edit histogram apply crop. |
| `pending_image_edit_histogram_qimage` | `initData` | 1061 | Pending value for image edit histogram qimage. |
| `pending_image_edit_preview_state` | `initData` | 1059 | Pending value for image edit preview state. |
| `pending_navigation_before_index` | `initData` | 1079 | Pending value for navigation before index. |
| `pending_navigation_history_text` | `initData` | 1080 | Pending value for navigation history text. |
| `pending_preview_image_index` | `initData` | 1057 | Pending value for preview image index. |
| `pixmap_cache` | `initData` | 1099 | Cache entry or cache container for pixmap cache. |
| `pixmap_cache_size` | `initData` | 1100 | Cache entry or cache container for pixmap cache size. |
| `pixmap_item` | `update_display_pixmaps` | 8191 | Stores pixmap item. |
| `placeholder_items` | `initData` | 1107 | Stores placeholder items. |
| `preferences_action` | `initUI` | 2369 | Qt action object for preferences action. |
| `preview_cancel_shortcut` | `initUI` | 2508 | Stores preview cancel shortcut. |
| `preview_confirm_shortcut` | `initUI` | 2502 | Stores preview confirm shortcut. |
| `preview_confirm_shortcut_enter` | `initUI` | 2505 | Stores preview confirm shortcut enter. |
| `preview_frame_update_in_progress` | `initData` | 1058 | Tracks whether preview frame update in progress. |
| `preview_handle_size` | `__init__` | 173 | Size value for preview handle size. |
| `preview_offset_x` | `initData` | 1112 | Geometry value for preview offset x. |
| `preview_offset_y` | `initData` | 1113 | Geometry value for preview offset y. |
| `radius_status_label` | `initUI` | 2773 | Label widget for radius status label. |
| `radius_textbox` | `initUI` | 2777 | Stores radius textbox. |
| `radius_wheel_step` | `__init__` | 149 | Stores radius wheel step. |
| `raw_image_cache` | `initData` | 1095 | Cache entry or cache container for raw image cache. |
| `raw_image_cache_size` | `initData` | 1096 | Cache entry or cache container for raw image cache size. |
| `raw_image_size_cache` | `initData` | 1101 | Cache entry or cache container for raw image size cache. |
| `redo_action` | `initUI` | 2402 | Qt action object for redo action. |
| `relink_images_action` | `initUI` | 2389 | Qt action object for relink images action. |
| `remove_selected_action` | `initUI` | 2381 | Qt action object for remove selected action. |
| `rendered_cell_items` | `initData` | 1028 | Stores rendered cell items. |
| `reset_cursor_action` | `initUI` | 2408 | Qt action object for reset cursor action. |
| `restore_window_action` | `initUI` | 2745 | Qt action object for restore window action. |
| `results_table_tabs` | `initUI` | 2679 | Stores results table tabs. |
| `results_tables_dock` | `initUI` | 2719 | Dock widget reference for results tables dock. |
| `rightButton` | `initUI` | 2605 | Stores right button. |
| `run_analysis_action` | `initUI` | 2390 | Qt action object for run analysis action. |
| `sample_add_button` | `build_sample_catalog_panel` | 3409 | Button widget for sample add button. |
| `sample_catalog` | `ensure_sample_catalog_matches_cell_records` | 488 | Stores sample catalog. |
| `sample_catalog_dock` | `initUI` | 2715 | Dock widget reference for sample catalog dock. |
| `sample_catalog_table` | `build_sample_catalog_panel` | 3389 | Stores sample catalog table. |
| `sample_catalog_table_syncing` | `build_sample_catalog_panel` | 3388 | Stores sample catalog table syncing. |
| `sample_catalog_widget` | `initUI` | 2692 | Qt widget reference for sample catalog widget. |
| `sample_delete_button` | `build_sample_catalog_panel` | 3411 | Button widget for sample delete button. |
| `sample_manager_action` | `initUI` | 2395 | Qt action object for sample manager action. |
| `sample_name_pattern` | `set_preferences` | 240 | Stores sample name pattern. |
| `save_session_action` | `initUI` | 2385 | Qt action object for save session action. |
| `save_session_as_action` | `initUI` | 2386 | Qt action object for save session as action. |
| `scene` | `initUI` | 2639 | Stores scene. |
| `select_tool_action` | `initUI` | 2409 | Qt action object for select tool action. |
| `session_active` | `initData` | 1120 | Tracks whether session active. |
| `session_date` | `initData` | 1090 | Stores session date. |
| `session_institution` | `initData` | 1089 | Stores session institution. |
| `session_metadata_status_label` | `initUI` | 2769 | Label widget for session metadata status label. |
| `session_project_name` | `initData` | 1087 | Display name for session project name. |
| `session_user_name` | `initData` | 1088 | Display name for session user name. |
| `slider_buttons_layout` | `initUI` | 2627 | Stores slider buttons layout. |
| `slider_buttons_widget` | `initUI` | 2631 | Qt widget reference for slider buttons widget. |
| `slider_drag_start_index` | `initData` | 1081 | Zero-based index for slider drag start index. |
| `slider_maxzoom_pixel_interval` | `__init__` | 137 | Stores slider maxzoom pixel interval. |
| `slider_tick_pixel_interval` | `__init__` | 138 | Stores slider tick pixel interval. |
| `sort_images_action` | `initUI` | 2394 | Qt action object for sort images action. |
| `sort_mode` | `__init__` | 142 | Mode value for sort mode. |
| `space_held` | `__init__` | 205 | Stores space held. |
| `statusBar` | `initUI` | 2766 | Stores status bar. |
| `syncing_image_list_selection` | `initData` | 1117 | Stores syncing image list selection. |
| `temperature_cycle_warmup_hysteresis_c` | `__init__` | 158 | Stores temperature cycle warmup hysteresis c. |
| `freeze_count_timeseries_headers` | `initData` | 1073 | Column header data for freeze count timeseries headers. |
| `freeze_count_timeseries_rows` | `initData` | 1074 | Row-oriented data for freeze count timeseries rows. |
| `freeze_count_timeseries_summary` | `initData` | 1075 | Summary metadata for freeze count timeseries summary. |
| `freeze_count_timeseries_table` | `initUI` | 2674 | Stores freeze count timeseries table. |
| `temporary_event_data` | `__init__` | 204 | Stores temporary event data. |
| `terminal` | `initUI` | 2653 | Stores terminal. |
| `timer` | `initData` | 1093 | Stores timer. |
| `timeseries_convolution_line_width` | `__init__` | 161 | Geometry value for timeseries convolution line width. |
| `timeseries_current_frame_color` | `__init__` | 164 | Color setting for timeseries current frame color. |
| `timeseries_current_frame_line_width` | `__init__` | 165 | Geometry value for timeseries current frame line width. |
| `timeseries_freeze_line_color` | `__init__` | 162 | Color setting for timeseries freeze line color. |
| `timeseries_freeze_line_width` | `__init__` | 163 | Geometry value for timeseries freeze line width. |
| `timeseries_palette` | `__init__` | 159 | Stores timeseries palette. |
| `timeseries_line_width` | `__init__` | 160 | Geometry value for timeseries line width. |
| `tool_mode` | `initData` | 1119 | Mode value for tool mode. |
| `tool_name_dict` | `initUI` | 2560 | Mapping used for tool name dict. |
| `tool_options_dock` | `initUI` | 2714 | Dock widget reference for tool options dock. |
| `tool_options_mode_label` | `build_tool_options_panel` | 2905 | Label widget for tool options mode label. |
| `tool_options_none_label` | `build_tool_options_panel` | 2914 | Label widget for tool options none label. |
| `tool_options_none_page` | `build_tool_options_panel` | 2913 | Page widget for tool options none page. |
| `tool_options_stack` | `build_tool_options_panel` | 2910 | Stores tool options stack. |
| `tool_options_widget` | `initUI` | 2691 | Qt widget reference for tool options widget. |
| `tool_status_label` | `initUI` | 2790 | Label widget for tool status label. |
| `toolbar` | `initUI` | 2529 | Stores toolbar. |
| `undo_action` | `initUI` | 2401 | Qt action object for undo action. |
| `undo_limit` | `__init__` | 139 | Stores undo limit. |
| `undo_redo_enabled` | `__init__` | 199 | Tracks whether undo redo enabled. |
| `undo_stack` | `__init__` | 198 | Stores undo stack. |
| `view` | `initUI` | 2642 | Stores view. |
| `view_slider_widget` | `initUI` | 2650 | Qt widget reference for view slider widget. |
| `viewer_double_action` | `initUI` | 2398 | Qt action object for viewer double action. |
| `viewer_image_count` | `__init__` | 140 | Count value for viewer image count. |
| `viewer_orientation_toggle_action` | `initUI` | 2400 | Qt action object for viewer orientation toggle action. |
| `viewer_single_action` | `initUI` | 2397 | Qt action object for viewer single action. |
| `viewer_split_orientation` | `__init__` | 141 | Stores viewer split orientation. |
| `viewer_triple_action` | `initUI` | 2399 | Qt action object for viewer triple action. |
| `worker` | `outputData` | 8491 | Stores worker. |
| `zoom_slider` | `initUI` | 2615 | Slider widget for zoom slider. |
| `zoom_status_label` | `initUI` | 2774 | Label widget for zoom status label. |
| `zoom_textbox` | `initUI` | 2778 | Stores zoom textbox. |
| `zoom_window_action` | `initUI` | 2743 | Qt action object for zoom window action. |

## Methods

### Analysis and results

| Method | Line | Explanation |
| --- | --- | --- |
| `show_analysis_progress_frame(index)` | 1920 | Implements show analysis progress frame. |
| `get_analysis_progress_interval_ms()` | 1937 | Returns analysis progress interval ms. |
| `enqueue_analysis_progress_frame(index)` | 1940 | Implements enqueue analysis progress frame. |
| `flush_pending_analysis_progress()` | 1953 | Implements flush pending analysis progress. |
| `update_results_tables()` | 4374 | Updates results tables. |
| `update_results_table_visibility()` | 4387 | Updates results table visibility. |
| `invalidate_analysis_results(reason=None)` | 4431 | Invalidates analysis results. |
| `refresh_grayscale_plot()` | 4461 | Refreshes grayscale plot. |
| `grayscale_plot_is_visible()` | 4482 | Implements grayscale plot is visible. |
| `update_grayscale_plot_current_frame()` | 4494 | Updates grayscale plot current frame. |
| `get_plot_current_image_index()` | 4501 | Returns plot current image index. |
| `load_grayscale_results(file_path)` | 5693 | Loads grayscale results. |
| `set_freeze_results(headers, rows)` | 5710 | Sets freeze results. |
| `export_grayscale_results_for_external_tool()` | 6418 | Exports grayscale results for external tool. |
| `export_results_csv(checked=False)` | 6452 | Exports results CSV. |
| `onAnalysisDone(index, results)` | 8535 | Implements on analysis done. |

### Cells and samples

| Method | Line | Explanation |
| --- | --- | --- |
| `sample_visual_color(sample_id, alpha=255)` | 349 | Returns sample-related visual color. |
| `sample_visual_color_for_cell(cell_id, alpha=255)` | 359 | Returns sample-related visual color for cell. |
| `refresh_cell_sample_visuals()` | 365 | Refreshes cell sample visuals. |
| `extract_cell_id_from_analysis_header(header_text)` | 371 | Implements extract cell ID from analysis header. |
| `extract_cell_id_from_label(label_text)` | 374 | Implements extract cell ID from label. |
| `ensure_cell_record(cell_id)` | 383 | Ensures cell record. |
| `ensure_cell_registry_matches_scene_cells()` | 386 | Ensures cell registry matches scene cells. |
| `recompute_next_cell_id(preserve_if_larger=True)` | 389 | Recomputes next cell ID. |
| `allocate_cell_id()` | 392 | Allocates cell ID. |
| `cell_id_exists(cell_id, exclude_cell_id=None)` | 395 | Implements cell ID exists. |
| `rename_cell_id(old_cell_id, new_cell_id)` | 398 | Renames cell ID. |
| `clear_cell_analysis()` | 401 | Clears cell analysis. |
| `sync_cell_analysis_from_results()` | 404 | Synchronizes cell analysis from results. |
| `prune_analysis_results_for_deleted_cells(deleted_cell_ids)` | 407 | Prunes analysis results for deleted cells. |
| `recompute_next_sample_id(preserve_if_larger=True)` | 429 | Recomputes next sample ID. |
| `allocate_sample_id()` | 445 | Allocates sample ID. |
| `default_sample_name(sample_id)` | 451 | Returns the default sample name. |
| `sample_name_for_id(sample_id)` | 477 | Returns sample-related name for ID. |
| `ensure_sample_catalog_matches_cell_records()` | 486 | Ensures sample catalog matches cell records. |
| `cursor_sample_catalog_signature()` | 503 | Implements cursor sample catalog signature. |
| `invalidate_cursor_sample_combo_cache()` | 509 | Invalidates cursor sample combo cache. |
| `set_cursor_sample_combo_mixed_item_visible(visible)` | 513 | Sets cursor sample combo mixed item visible. |
| `refresh_cursor_sample_combo_catalog(include_mixed_item=False, force=False)` | 530 | Refreshes cursor sample combo catalog. |
| `parse_freeze_frame_text(text)` | 621 | Parses freeze frame text. |
| `rebuild_freeze_rows_for_cell(cell_id, freeze_event_indices)` | 627 | Implements rebuild freeze rows for cell. |
| `build_cells_panel_records()` | 678 | Builds cells panel records. |
| `refresh_cells_panel(changed_columns=None, preserve_selection=False)` | 696 | Refreshes cells panel. |
| `sync_cells_panel_selection()` | 763 | Synchronizes cells panel selection. |
| `handle_cells_panel_selection_changed()` | 781 | Handles cells panel selection changed. |
| `should_refresh_cells_panel_from_redraw()` | 794 | Returns whether refresh cells panel from redraw. |
| `handle_cells_panel_visibility_changed(visible)` | 805 | Handles cells panel visibility changed. |
| `apply_cursor_freeze_frames_edit()` | 922 | Applies cursor freeze frames edit. |
| `apply_edit_circle_cell_id_edit()` | 978 | Applies edit circle cell ID edit. |
| `build_cells_panel()` | 3337 | Builds cells panel. |
| `build_sample_catalog_panel()` | 3374 | Builds sample catalog panel. |
| `selected_sample_catalog_id()` | 3429 | Returns selected sample catalog ID. |
| `refresh_sample_catalog_table(select_sample_id=None, preserve_selection=True)` | 3449 | Refreshes sample catalog table. |
| `update_sample_catalog_buttons()` | 3493 | Updates sample catalog buttons. |
| `add_sample_catalog_entry()` | 3498 | Implements add sample catalog entry. |
| `delete_selected_sample_catalog_entry()` | 3508 | Implements delete selected sample catalog entry. |
| `handle_sample_catalog_item_changed(item)` | 3541 | Handles sample catalog item changed. |
| `update_cursor_sample_controls()` | 3574 | Updates cursor sample controls. |
| `update_cursor_sample_assignment_state()` | 3611 | Updates cursor sample assignment state. |
| `assign_selected_cells_to_current_sample()` | 3617 | Implements assign selected cells to current sample. |
| `create_sample_from_cursor_controls()` | 3650 | Creates sample from cursor controls. |
| `get_selected_cell_items()` | 4117 | Returns selected cell items. |
| `delete_selected_cells()` | 4120 | Implements delete selected cells. |
| `infer_grid_parameters_from_cells(selected_items)` | 4154 | Infers grid parameters from cells. |
| `handle_scene_cell_selection_changed()` | 4157 | Handles scene cell selection changed. |
| `reselect_cell_ids(cell_ids, sync_tool_panel=True)` | 4164 | Implements reselect cell ids. |
| `show_sample_catalog_manager()` | 4191 | Implements show sample catalog manager. |
| `get_plot_target_cell_ids()` | 4450 | Returns plot target cell ids. |
| `push_cell_history(text, before_state, include_analysis=False)` | 5385 | Implements push cell history. |
| `edit_current_keyframe_cell_item()` | 6582 | Implements edit current keyframe cell item. |
| `add_cell_item_to_keyframes(added_items=None)` | 6597 | Implements add cell item to keyframes. |
| `delete_cell_item_to_keyframes(cell_id)` | 6625 | Implements delete cell item to keyframes. |
| `delete_cell_items_to_keyframes(cell_ids)` | 6628 | Implements delete cell items to keyframes. |
| `activate_edit_cell_item(cell_item)` | 6968 | Implements activate edit cell item. |
| `anchor_cell_items_to_current_image(cell_items)` | 8243 | Implements anchor cell items to current image. |
| `update_cell_items_selectable_state()` | 8806 | Updates cell items selectable state. |
| `unselect_all_cell_items()` | 8809 | Implements unselect all cell items. |
| `update_cell_items_cell_ids()` | 8812 | Updates cell items cell ids. |
| `reset_cell_items_edit_chosen()` | 8815 | Resets cell items edit chosen. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__()` | 130 | Initializes the instance. |
| `set_preferences(preserve_session_tool_state=False)` | 211 | Sets preferences. |
| `get_qcolor(color_value)` | 340 | Returns qcolor. |
| `summarize_integer_list(values, limit=8)` | 549 | Summarizes integer list. |
| `format_integer_list_csv(values)` | 580 | Formats integer list CSV. |
| `parse_integer_csv_text(text, *, allow_empty=True, minimum=None, maximum=None)` | 596 | Parses integer CSV text. |
| `apply_manual_freeze_event_indices(cell_id, freeze_event_indices, refresh_tables=True)` | 645 | Applies manual freeze event indices. |
| `current_single_edit_target_item()` | 969 | Returns the current single edit target item. |
| `initData()` | 1020 | Implements init data. |
| `image_pixel_to_scene_coordinates(pixel_x, pixel_y, image_rect=None, *, index=None, apply_crop=None)` | 1465 | Implements image pixel to scene coordinates. |
| `scene_to_image_pixel_coordinates(scene_pos, image_rect=None, *, index=None, apply_crop=None)` | 1484 | Implements scene to image pixel coordinates. |
| `format_numeric_value(value)` | 2840 | Formats numeric value. |
| `current_circle_controls()` | 3747 | Returns the current circle controls. |
| `current_grid_controls()` | 3768 | Returns the current grid controls. |
| `handle_circle_radius_spinbox_changed(value)` | 3914 | Handles circle radius spinbox changed. |
| `handle_grid_radius_change(value)` | 3929 | Handles grid radius change. |
| `handle_grid_parameter_change(*_args)` | 3963 | Handles grid parameter change. |
| `clear_grid_preview()` | 3986 | Clears grid preview. |
| `cancel_grid_preview()` | 3991 | Cancels grid preview. |
| `float_grid_preview()` | 3994 | Implements float grid preview. |
| `update_grid_preview()` | 4003 | Updates grid preview. |
| `update_grid_apply_state()` | 4006 | Updates grid apply state. |
| `handle_grid_apply_action()` | 4009 | Handles grid apply action. |
| `handle_circle_apply_action()` | 4012 | Handles circle apply action. |
| `focus_is_text_entry_widget()` | 4015 | Implements focus is text entry widget. |
| `focus_widget_is_within(focus_widget, roots)` | 4057 | Implements focus widget is within. |
| `confirm_active_preview()` | 4079 | Implements confirm active preview. |
| `handle_circle_float_action()` | 4095 | Handles circle float action. |
| `handle_circle_cancel_action()` | 4099 | Handles circle cancel action. |
| `handle_grid_float_action()` | 4110 | Handles grid float action. |
| `handle_grid_cancel_action()` | 4114 | Handles grid cancel action. |
| `get_edit_target_items()` | 4151 | Returns edit target items. |
| `apply_grid_preview()` | 4188 | Applies grid preview. |
| `zoom_window()` | 4197 | Implements zoom window. |
| `eventFilter(watched, event)` | 4283 | Implements event filter. |
| `setup_table_widget(table_widget)` | 4338 | Implements setup table widget. |
| `set_table_data(table_widget, headers, rows)` | 4347 | Sets table data. |
| `cancel_transient_history_state()` | 4664 | Clear unfinished interaction state before undo/redo. |
| `push_snapshot_history(text, before_state)` | 5376 | Implements push snapshot history. |
| `push_data_history(text, before_state)` | 5421 | Implements push data history. |
| `push_navigation_history(text, before_index, after_index)` | 5439 | Implements push navigation history. |
| `format_image_list_entry(index)` | 5450 | Formats image list entry. |
| `populate_image_list()` | 5461 | Implements populate image list. |
| `update_image_list_annotations(rows=None)` | 5469 | Updates image list annotations. |
| `sync_image_list_selection()` | 5483 | Synchronizes image list selection. |
| `handle_image_list_selection(index)` | 5526 | Handles image list selection. |
| `handle_image_list_current_changed(current, previous)` | 5540 | Handles image list current changed. |
| `update_document_interface_state()` | 5587 | Updates document interface state. |
| `get_selected_image_rows()` | 5636 | Returns selected image rows. |
| `navigate_to_image(index, history_text='Change Frame')` | 5646 | Implements navigate to image. |
| `write_csv_table(file_path, headers, rows)` | 6438 | Writes CSV table. |
| `update_flaggedframe_list(is_flagging)` | 6576 | Updates flaggedframe list. |
| `grid_horizontal_pitch_shortcut_label()` | 6724 | Implements grid horizontal pitch shortcut label. |
| `grid_vertical_pitch_shortcut_label()` | 6727 | Implements grid vertical pitch shortcut label. |
| `grid_tilt_shortcut_label()` | 6730 | Implements grid tilt shortcut label. |
| `is_caps_lock_pressed()` | 6733 | Returns whether caps lock pressed. |
| `is_grid_horizontal_pitch_modifier_active(modifiers)` | 6741 | Returns whether grid horizontal pitch modifier active. |
| `is_grid_tilt_modifier_active(modifiers)` | 6746 | Returns whether grid tilt modifier active. |
| `showAboutDialog()` | 6752 | Implements show about dialog. |
| `showPreferencesDialog()` | 6756 | Implements show preferences dialog. |
| `log(message)` | 6768 | Implements log. |
| `file_dialog_options()` | 6772 | Implements file dialog options. |
| `reset_transient_interaction_state()` | 6792 | Hard-clear unfinished preview/edit state without changing the active tool. |
| `cancel_edit_state()` | 6811 | Cancel any active or remembered edit workflow before switching tools. |
| `preserve_edit_state_for_pan()` | 6844 | Remember the current edit workflow so pan can return to it. |
| `is_pan_interaction_active()` | 6937 | Returns whether pan interaction active. |
| `enter_temporary_pan_mode()` | 6943 | Enters temporary pan mode. |
| `get_image_paths_from_folder(input_dirpath)` | 7019 | Returns image paths from folder. |
| `natural_sort_key(file_path)` | 7035 | Implements natural sort key. |
| `get_exif_sort_value(file_path)` | 7041 | Returns exif sort value. |
| `is_sort_mode_available(mode, file_paths=None)` | 7052 | Returns whether sort mode available. |
| `get_sort_availability(file_paths=None)` | 7072 | Returns sort availability. |
| `sort_image_paths(file_paths, mode=None)` | 7082 | Implements sort image paths. |
| `openSortImagesDialog()` | 7099 | Implements open sort images dialog. |
| `open_add_images_dialog()` | 7157 | Implements open add images dialog. |
| `loadFolder()` | 7172 | Implements load folder. |
| `loadImages()` | 7182 | Implements load images. |
| `relink_images_folder(checked=False)` | 7244 | Implements relink images folder. |
| `load_aux(input_imagePath)` | 7500 | Loads aux. |
| `remove_selected_image()` | 7576 | Removes selected image. |
| `remove_selected_list_images()` | 7585 | Removes selected list images. |
| `reset_pending_frame_navigation_state(stop_timer=False)` | 7791 | Resets pending frame navigation state. |
| `finalize_frame_update(index)` | 7928 | Implements finalize frame update. |
| `handle_frame_navigation_shortcut(key)` | 8039 | Handles frame navigation shortcut. |
| `resize_image_textbox()` | 8063 | Implements resize image textbox. |
| `updateRadiusTextbox()` | 8246 | Implements update radius textbox. |
| `updateCircleRadius_from_textedit()` | 8260 | Implements update circle radius from textedit. |
| `updateZoomTextbox()` | 8272 | Implements update zoom textbox. |
| `updateZoomLevel()` | 8276 | Implements update zoom level. |
| `updateButtonStates()` | 8285 | Implements update button states. |
| `undo()` | 8329 | Implements undo. |
| `redo()` | 8342 | Implements redo. |
| `keyPressEvent(event)` | 8355 | Qt key-press event handler. |
| `keyReleaseEvent(event)` | 8436 | Qt key-release event handler. |
| `outputData()` | 8479 | Implements output data. |
| `out_put_interpolation()` | 8528 | Implements out put interpolation. |
| `onThreadFinished()` | 8541 | Implements on thread finished. |
| `key_press_button_highlight(button)` | 8609 | Implements key press button highlight. |
| `reset_button_stylesheet(theme=None)` | 8689 | Resets button stylesheet. |
| `update_toggle_flagging_button_icon(theme=None)` | 8783 | Updates toggle flagging button icon. |
| `reset_button_icon(theme=None)` | 8796 | Resets button icon. |
| `switch_light_dark_mode(theme=None)` | 8819 | Implements switch light dark mode. |
| `resizeEvent(event)` | 8827 | Qt resize event handler for this widget. |
| `closeEvent(event)` | 8832 | Implements close event. |
| `load_preferences_from_xml()` | 8835 | Loads preferences from xml. |

### Image display and cache

| Method | Line | Explanation |
| --- | --- | --- |
| `format_numeric_display(value, decimals=1)` | 565 | Formats numeric display. |
| `get_raw_image_dimensions(index)` | 1413 | Returns raw image dimensions. |
| `get_current_raw_image_dimensions()` | 1435 | Returns current raw image dimensions. |
| `clear_image_caches()` | 7800 | Clears image caches. |
| `get_cached_raw_image(image_path)` | 7807 | Returns cached raw image. |
| `updateImage(index, preview=False)` | 7978 | Implements update image. |
| `updateImageFromTextbox()` | 8054 | Implements update image from textbox. |
| `get_cached_image(index, *, apply_crop=None)` | 8077 | Returns cached image. |
| `get_cached_pixmap(index, *, apply_crop=None)` | 8104 | Returns cached pixmap. |
| `get_display_slots(current_index)` | 8123 | Returns display slots. |
| `clear_context_pixmaps()` | 8142 | Clears context pixmaps. |
| `update_display_pixmaps(current_index, *, apply_crop=None)` | 8150 | Updates display pixmaps. |
| `displayMarkedRegions()` | 8228 | Implements display marked regions. |
| `interpolate_and_displayMarkedRegions(index, preview=False)` | 8233 | Implements interpolate and display marked regions. |

### Image edit

| Method | Line | Explanation |
| --- | --- | --- |
| `apply_image_edit_state(state, *, invalidate_results=False, refresh_display=True, sync_controls=True)` | 1159 | Applies image edit state. |
| `refresh_current_image_edit_visuals()` | 1270 | Refreshes current image edit visuals. |
| `prewarm_current_image_edit_render_cache()` | 1291 | Implements prewarm current image edit render cache. |
| `get_image_edit_histogram_interval_ms()` | 1301 | Returns image edit histogram interval ms. |
| `request_image_edit_histogram_refresh(q_image=None, *, immediate=False, apply_crop=None)` | 1304 | Implements request image edit histogram refresh. |
| `flush_pending_image_edit_histogram()` | 1318 | Implements flush pending image edit histogram. |
| `normalize_image_edit_uniform_exposure_area_state(area_state=None, *, raw_width=None, raw_height=None)` | 1325 | Normalizes image edit uniform exposure area state. |
| `current_image_edit_uniform_exposure_area_state(*, index=None)` | 1330 | Returns the current image edit uniform exposure area state. |
| `current_image_edit_uniform_exposure_state()` | 1348 | Returns the current image edit uniform exposure state. |
| `compose_image_edit_state(*, exposure=None, contrast=None, uniform_exposure=None, crop=None)` | 1359 | Implements compose image edit state. |
| `has_image_edit_uniform_exposure_area()` | 1367 | Returns whether image edit uniform exposure area. |
| `has_image_edit_uniform_exposure()` | 1378 | Returns whether image edit uniform exposure. |
| `get_image_edit_uniform_exposure_offset(*, index=None, image_path=None)` | 1381 | Returns image edit uniform exposure offset. |
| `current_image_edit_total_exposure(*, index=None, image_path=None)` | 1394 | Returns the current image edit total exposure. |
| `current_image_edit_crop_state(*, index=None)` | 1400 | Returns the current image edit crop state. |
| `normalize_image_edit_crop_state(crop_state=None, *, raw_width=None, raw_height=None)` | 1440 | Normalizes image edit crop state. |
| `should_apply_crop_in_display()` | 1445 | Returns whether apply crop in display. |
| `current_image_edit_crop_transform(index=None, *, apply_crop=None)` | 1448 | Returns the current image edit crop transform. |
| `sync_image_edit_controls()` | 1500 | Synchronizes image edit controls. |
| `refresh_image_edit_histogram(q_image=None, *, apply_crop=None)` | 1536 | Refreshes image edit histogram. |
| `begin_image_edit_history(text)` | 1604 | Begins image edit history. |
| `commit_image_edit_history(text=None)` | 1612 | Commits image edit history. |
| `log_image_edit_change(history_text)` | 1623 | Implements log image edit change. |
| `get_image_edit_preview_interval_ms()` | 1648 | Returns image edit preview interval ms. |
| `reset_pending_image_edit_preview_state(stop_timer=False)` | 1651 | Resets pending image edit preview state. |
| `compose_pending_image_edit_preview_state(*, exposure=None, contrast=None)` | 1657 | Implements compose pending image edit preview state. |
| `queue_image_edit_preview_state(state)` | 1669 | Implements queue image edit preview state. |
| `flush_pending_image_edit_preview()` | 1675 | Implements flush pending image edit preview. |
| `handle_image_edit_exposure_slider_changed(slider_value)` | 1694 | Handles image edit exposure slider changed. |
| `handle_image_edit_exposure_spinbox_changed(exposure_value)` | 1713 | Handles image edit exposure spinbox changed. |
| `handle_image_edit_exposure_slider_released()` | 1726 | Handles image edit exposure slider released. |
| `handle_image_edit_contrast_slider_changed(contrast_value)` | 1738 | Handles image edit contrast slider changed. |
| `handle_image_edit_contrast_spinbox_changed(contrast_value)` | 1757 | Handles image edit contrast spinbox changed. |
| `handle_image_edit_contrast_slider_released()` | 1770 | Handles image edit contrast slider released. |
| `is_image_edit_uniform_exposure_area_active()` | 1782 | Returns whether image edit uniform exposure area active. |
| `begin_image_edit_uniform_exposure_area()` | 1785 | Begins image edit uniform exposure area. |
| `end_image_edit_uniform_exposure_area()` | 1806 | Ends image edit uniform exposure area. |
| `handle_image_edit_uniform_exposure_area_button()` | 1815 | Handles image edit uniform exposure area button. |
| `handle_image_edit_uniform_exposure_overlay_changed(area_state, finalize=False)` | 1821 | Handles image edit uniform exposure overlay changed. |
| `ensure_image_edit_uniform_exposure_overlay()` | 1852 | Ensures image edit uniform exposure overlay. |
| `sync_image_edit_uniform_exposure_overlay()` | 1863 | Synchronizes image edit uniform exposure overlay. |
| `show_image_edit_progress_frame(index)` | 1902 | Implements show image edit progress frame. |
| `compute_image_edit_uniform_exposure_solution(area_state, reference_index, progress_callback=None)` | 1962 | Computes image edit uniform exposure solution. |
| `run_image_edit_uniform_exposure()` | 2022 | Implements run image edit uniform exposure. |
| `reset_image_edit_uniform_exposure()` | 2060 | Resets image edit uniform exposure. |
| `is_image_edit_crop_active()` | 2079 | Returns whether image edit crop active. |
| `get_image_edit_crop_draft_state()` | 2082 | Returns image edit crop draft state. |
| `discard_image_edit_crop_draft()` | 2088 | Implements discard image edit crop draft. |
| `reset_image_edit_crop()` | 2092 | Resets image edit crop. |
| `begin_image_edit_crop()` | 2120 | Begins image edit crop. |
| `handle_image_edit_crop_primary_button()` | 2150 | Handles image edit crop primary button. |
| `apply_image_edit_crop()` | 2156 | Applies image edit crop. |
| `trigger_image_edit_crop_apply_button()` | 2177 | Implements trigger image edit crop apply button. |
| `cancel_image_edit_crop()` | 2185 | Cancels image edit crop. |
| `handle_image_edit_crop_overlay_changed(crop_state, finalize=False)` | 2197 | Handles image edit crop overlay changed. |
| `ensure_image_edit_crop_overlay()` | 2206 | Ensures image edit crop overlay. |
| `sync_image_edit_crop_overlay()` | 2217 | Synchronizes image edit crop overlay. |
| `reset_image_edit_slider_to_default(slider)` | 4258 | Resets image edit slider to default. |
| `push_image_edit_history(text, before_state)` | 5430 | Implements push image edit history. |
| `apply_image_edit_tool_ui()` | 6866 | Applies image edit tool UI. |

### Session and state

| Method | Line | Explanation |
| --- | --- | --- |
| `serialize_cell_records()` | 377 | Serializes cell records. |
| `deserialize_cell_records(payload)` | 380 | Deserializes cell records. |
| `serialize_sample_catalog()` | 410 | Serializes sample catalog. |
| `deserialize_sample_catalog(payload)` | 417 | Deserializes sample catalog. |
| `restore_add_defaults(include_grid=False)` | 1011 | Restores add defaults. |
| `serialize_session_metadata()` | 1124 | Serializes session metadata. |
| `serialize_image_edit_state()` | 1132 | Serializes image edit state. |
| `apply_session_metadata(metadata)` | 2236 | Applies session metadata. |
| `format_session_metadata_status_text()` | 2244 | Formats session metadata status text. |
| `update_session_metadata_status_label()` | 2259 | Updates session metadata status label. |
| `has_session_content()` | 2268 | Returns whether session content. |
| `has_session_save_payload()` | 2295 | Returns whether session save payload. |
| `prompt_save_before_replacing_session(next_action_label='starting a new session')` | 2298 | Implements prompt save before replacing session. |
| `prompt_new_session_metadata()` | 2320 | Implements prompt new session metadata. |
| `newSession(checked=False)` | 2326 | Implements new session. |
| `restore_window()` | 4201 | Restores window. |
| `capture_session_state()` | 4508 | Captures session state. |
| `capture_cell_state(include_analysis=False)` | 4536 | Captures cell state. |
| `capture_data_state()` | 4566 | Captures data state. |
| `capture_image_edit_history_state()` | 4588 | Captures image edit history state. |
| `capture_image_session_state()` | 4594 | Captures image session state. |
| `capture_timeline_marker_state()` | 4620 | Captures timeline marker state. |
| `capture_loaded_images_state()` | 4629 | Captures loaded images state. |
| `get_active_tool_for_restore()` | 4651 | Return the user-facing tool to preserve across undo/redo. |
| `restore_tool_mode_ui(restored_tool_mode=None)` | 4685 | Reapply cursor/drag/action state after undo/redo restores data. |
| `restore_image_session_state(state, preserve_active_tool=False)` | 4719 | Restores image session state. |
| `restore_loaded_images_state(state, preserve_active_tool=False)` | 4841 | Restores loaded images state. |
| `restore_session_state(state, preserve_active_tool=False)` | 4958 | Restores session state. |
| `restore_cell_state(state, preserve_active_tool=False)` | 5092 | Restores cell state. |
| `restore_timeline_marker_state(state, preserve_active_tool=False)` | 5228 | Restores timeline marker state. |
| `restore_data_state(state, preserve_active_tool=False)` | 5287 | Restores data state. |
| `restore_image_edit_history_state(state, preserve_active_tool=False)` | 5333 | Restores image edit history state. |
| `restore_navigation_index(index, preserve_active_tool=False)` | 5351 | Restores navigation index. |
| `push_image_session_history(text, before_state)` | 5403 | Implements push image session history. |
| `push_loaded_images_history(text, before_state)` | 5412 | Implements push loaded images history. |
| `update_session_actions_state()` | 5547 | Updates session actions state. |
| `restore_after_edit_mode()` | 6785 | Restore controls that are temporarily disabled during single-edit. |
| `resort_current_session()` | 7118 | Implements resort current session. |
| `openSession()` | 7193 | Implements open session. |
| `get_missing_session_image_paths()` | 7234 | Returns missing session image paths. |
| `handle_save_session_action()` | 7436 | Handles save session action. |
| `persist_session_to_path(file_path, *, show_errors=True)` | 7440 | Implements persist session to path. |
| `persist_session_to_current_file(*, show_errors=True)` | 7462 | Implements persist session to current file. |
| `saveSession()` | 7468 | Implements save session. |
| `saveSessionAs()` | 7479 | Implements save session as. |
| `remove_images_from_session(rows)` | 7604 | Removes images from session. |
| `clear_loaded_images(checked=False, confirm=True, log_message='Cleared all loaded images from this session')` | 7671 | Clears loaded images. |
| `clear_session(checked=False, confirm=True, log_message='Cleared session', record_history=True, new_metadata=None, activate_session=False)` | 7733 | Clears session. |

### Temperature import

| Method | Line | Explanation |
| --- | --- | --- |
| `update_freeze_count_timeseries_table()` | 4382 | Updates freeze count timeseries table. |
| `set_freeze_count_timeseries_results(headers, rows, summary=None)` | 4406 | Sets freeze count timeseries results. |
| `invalidate_freeze_count_timeseries_results(reason=None)` | 4420 | Invalidates freeze count timeseries results. |
| `build_freeze_count_timeseries_sample_groups(grouping_mode='samples')` | 5720 | Builds freeze count timeseries sample groups. |
| `build_freeze_count_timeseries_image_counts(sample_groups, count_mode='cumulative')` | 5765 | Builds freeze count timeseries image counts. |
| `build_tamu_freeze_count_timeseries_sample_groups()` | 5822 | Builds tamu freeze count timeseries sample groups. |
| `normalize_temperature_reset_threshold(reset_temperature)` | 5831 | Normalizes temperature reset threshold. |
| `detect_cycle_start_indexes_from_temperatures(temperatures, reset_temperature)` | 5834 | Detects cycle start indexes from temperatures. |
| `build_cycle_ids_from_start_indexes(total_count, cycle_start_indexes)` | 5841 | Builds cycle ids from start indexes. |
| `cycle_index_for_position(position_value, cycle_start_positions)` | 5844 | Implements cycle index for position. |
| `build_tamu_image_timing_context(parsed_timeseries, reset_temperature=None)` | 5850 | Builds tamu image timing context. |
| `build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)` | 5889 | Builds tamu cycle reset image counts. |
| `reconcile_counts_by_cycle(raw_counts, anchor_counts, maximum_count, cycle_ids)` | 5926 | Implements reconcile counts by cycle. |
| `corrected_temperature_for_cell(measured_temperature, cell_id, calibration_by_well)` | 5934 | Implements corrected temperature for cell. |
| `corrected_temperature_for_group(measured_temperature, group, calibration_by_well)` | 5953 | Implements corrected temperature for group. |
| `build_csu_freeze_count_timeseries_results(parsed_data, blank_sample_names=None, reset_temperature=None)` | 5969 | Builds csu freeze count timeseries results. |
| `build_tamu_freeze_count_timeseries_results(parsed_timeseries, calibration_by_well=None, reset_temperature=None)` | 6143 | Builds tamu freeze count timeseries results. |
| `import_csu_is_dat(checked=False)` | 6253 | Imports csu is dat. |
| `import_tamu_linkam_xlsx(checked=False)` | 6334 | Imports tamu linkam xlsx. |
| `write_freeze_count_timeseries_csv(file_path)` | 6445 | Writes freeze count timeseries CSV. |

### Timeline

| Method | Line | Explanation |
| --- | --- | --- |
| `get_slider_handle_rect(slider)` | 4245 | Returns slider handle rect. |
| `push_timeline_marker_history(text, before_state)` | 5394 | Implements push timeline marker history. |
| `commit_slider_release_navigation()` | 5679 | Commits slider release navigation. |
| `update_keyframe_list(is_adding)` | 6559 | Updates keyframe list. |
| `keyframe_interpolation(frame_number)` | 6646 | Implements keyframe interpolation. |
| `zoom_slider_set_maximum()` | 6760 | Implements zoom slider set maximum. |
| `handle_preview_image_slider_value(index)` | 7828 | Handles preview image slider value. |
| `handle_image_slider_pressed()` | 7844 | Handles image slider pressed. |
| `handle_image_slider_released()` | 7855 | Handles image slider released. |
| `handle_committed_image_slider_value(index)` | 7905 | Handles committed image slider value. |
| `ensure_slider_window_contains_index(index)` | 7946 | Ensures slider window contains index. |
| `decreaseSliderValue()` | 8019 | Implements decrease slider value. |
| `increaseSliderValue()` | 8029 | Implements increase slider value. |
| `sync_zoom_slider_row_geometry()` | 8631 | Synchronizes zoom slider row geometry. |
| `reset_slider_stylesheet(theme=None)` | 8663 | Resets slider stylesheet. |
| `update_toggle_keyframe_button_icon(theme=None)` | 8770 | Updates toggle keyframe button icon. |

### UI shell

| Method | Line | Explanation |
| --- | --- | --- |
| `set_cursor_display_field_locked(field, locked)` | 573 | Sets cursor display field locked. |
| `refresh_cursor_selection_info(selected_items=None)` | 811 | Refreshes cursor selection info. |
| `update_cursor_record_edit_state(selected_items=None)` | 888 | Updates cursor record edit state. |
| `initUI()` | 2346 | Implements init UI. |
| `finalize_initial_dock_layout()` | 2831 | Implements finalize initial dock layout. |
| `enforce_initial_right_dock_tab()` | 2834 | Implements enforce initial right dock tab. |
| `current_preview_absolute_coordinates()` | 2843 | Returns the current preview absolute coordinates. |
| `clamp_preview_absolute_coordinates(x_value, y_value)` | 2855 | Implements clamp preview absolute coordinates. |
| `set_preview_absolute_coordinates(x_value, y_value)` | 2875 | Sets preview absolute coordinates. |
| `build_tool_options_panel()` | 2896 | Builds tool options panel. |
| `sync_tool_options_panel()` | 3673 | Synchronizes tool options panel. |
| `update_preview_shortcut_enabled_state()` | 3733 | Updates preview shortcut enabled state. |
| `sync_circle_tool_panel(radius, is_edit=False)` | 3799 | Synchronizes circle tool panel. |
| `sync_grid_tool_panel(is_edit=False)` | 3838 | Synchronizes grid tool panel. |
| `sync_active_preview_coordinate_controls()` | 3899 | Synchronizes active preview coordinate controls. |
| `handle_preview_offset_change(*_args)` | 3940 | Handles preview offset change. |
| `update_grid_preview_from_scene_pos(scene_pos, pin=False)` | 3997 | Updates grid preview from scene pos. |
| `get_grid_preview_definitions()` | 4000 | Returns grid preview definitions. |
| `focus_is_tool_options_editor()` | 4032 | Implements focus is tool options editor. |
| `focus_allows_preview_shortcut()` | 4068 | Implements focus allows preview shortcut. |
| `handle_preview_confirm_shortcut()` | 4090 | Handles preview confirm shortcut. |
| `handle_preview_cancel_shortcut()` | 4102 | Handles preview cancel shortcut. |
| `create_dock_widget(title, widget, object_name)` | 4205 | Creates dock widget. |
| `show_dock_widget(dock_widget)` | 4227 | Implements show dock widget. |
| `store_default_dock_state()` | 4236 | Implements store default dock state. |
| `reset_panel_layout()` | 4239 | Resets panel layout. |
| `set_active_image_panel(panel_name)` | 5633 | Sets active image panel. |
| `set_tools_highlight(tool_mode)` | 6775 | Sets tools highlight. |
| `cancel_unfinished_tool_workflow()` | 6826 | Drop any transient add/edit/grid interaction before a real tool switch. |
| `set_view_cursor_shape(cursor_shape)` | 6849 | Sets view cursor shape. |
| `apply_cursor_tool_ui()` | 6855 | Applies cursor tool UI. |
| `finalize_tool_mode_after_commit()` | 6878 | Clear transient override state without changing the active tool. |
| `apply_select_tool_ui(preserve_preview=False)` | 6884 | Applies select tool UI. |
| `apply_grid_tool_ui(preserve_preview=False)` | 6896 | Applies grid tool UI. |
| `apply_deselect_tool_ui()` | 6911 | Applies deselect tool UI. |
| `reset_cursor_tool(checked)` | 6922 | Resets cursor tool. |
| `panTool(checked)` | 6927 | Implements pan tool. |
| `imageEditTool(checked)` | 6951 | Implements image edit tool. |
| `selectTool(checked)` | 6956 | Implements select tool. |
| `gridTool(checked)` | 6962 | Implements grid tool. |
| `editTool(checked)` | 6996 | Implements edit tool. |
| `deselectTool(checked)` | 7011 | Implements deselect tool. |
| `remove_current_viewer_image()` | 7599 | Removes current viewer image. |
| `get_preview_frame_interval_ms()` | 7878 | Returns preview frame interval ms. |
| `flush_pending_preview_image()` | 7881 | Implements flush pending preview image. |
| `is_viewer_split_vertical()` | 8139 | Returns whether viewer split vertical. |
| `set_undo_status()` | 8307 | Sets undo status. |
| `set_redo_status()` | 8318 | Sets redo status. |
| `key_press_toolbutton_highlight(an_action)` | 8596 | Implements key press toolbutton highlight. |
| `reset_toolbar_stylesheet(theme=None)` | 8622 | Resets toolbar stylesheet. |
| `reset_status_bar_stylesheet(theme=None)` | 8677 | Resets status bar stylesheet. |
| `toolbar_icon(mode_folder, icon_name)` | 8701 | Implements toolbar icon. |
| `reset_toolbar_icon(theme=None)` | 8704 | Resets toolbar icon. |
| `update_viewer_mode_actions()` | 8731 | Updates viewer mode actions. |
| `update_viewer_orientation_toggle_action(mode_folder=None)` | 8737 | Updates viewer orientation toggle action. |
| `set_viewer_image_count(count)` | 8755 | Sets viewer image count. |
| `toggle_viewer_split_orientation()` | 8762 | Toggles viewer split orientation. |
