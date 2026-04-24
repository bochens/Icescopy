# API Class: `IceScopy`

Main application shell and composition root for the desktop app.

## Source

- Module: [`Icescopy`](API-Module-Icescopy)
- File: `src/Icescopy.py`
- Line: `317`

## Inheritance

- Bases: `QMainWindow`

## Purpose

Main application shell and composition root for the desktop app.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `active_image_panel` | `initData` | 1423 | Stores active image panel. |
| `add_folder_action` | `initUI` | 2701 | Qt action object for add folder action. |
| `add_images_action` | `initUI` | 2700 | Qt action object for add images action. |
| `analysis_progress_navigation_suppressed` | `initData` | 1386 | Tracks whether analysis progress navigation suppressed. |
| `analysis_progress_start_index` | `initData` | 1387 | Zero-based index for analysis progress start index. |
| `analysis_progress_timer` | `initUI` | 2919 | Timer object used for analysis progress timer. |
| `cell_controller` | `__init__` | 386 | Stores cell controller. |
| `cell_items` | `initData` | 1323 | Stores cell items. |
| `cell_records_by_id` | `initData` | 1326 | Stores cell records by ID. |
| `cell_state` | `__init__` | 385 | State bundle for cell state. |
| `cells_dock` | `initUI` | 3044 | Dock widget reference for cells dock. |
| `cells_panel_dirty` | `refresh_cells_panel` | 996 | Tracks whether cells panel dirty. |
| `cells_panel_force_refresh` | `refresh_cells_panel` | 1057 | Stores cells panel force refresh. |
| `cells_panel_last_snapshot` | `refresh_cells_panel` | 1055 | Stores cells panel last snapshot. |
| `cells_panel_widget` | `initUI` | 3021 | Qt widget reference for cells panel widget. |
| `cells_tree_widget` | `build_cells_panel` | 3674 | Qt widget reference for cells tree widget. |
| `circle_apply_button` | `build_tool_options_panel` | 3495 | Button widget for circle apply button. |
| `circle_cancel_button` | `build_tool_options_panel` | 3497 | Button widget for circle cancel button. |
| `circle_default_color` | `__init__` | 355 | Color setting for circle default color. |
| `circle_edit_color` | `__init__` | 358 | Color setting for circle edit color. |
| `circle_float_button` | `build_tool_options_panel` | 3496 | Button widget for circle float button. |
| `circle_hover_color` | `__init__` | 356 | Color setting for circle hover color. |
| `circle_label_offset_x` | `__init__` | 363 | Geometry value for circle label offset x. |
| `circle_label_offset_y` | `__init__` | 364 | Geometry value for circle label offset y. |
| `circle_offset_x_spinbox` | `build_tool_options_panel` | 3474 | Spin box widget for circle offset x spinbox. |
| `circle_offset_y_spinbox` | `build_tool_options_panel` | 3479 | Spin box widget for circle offset y spinbox. |
| `circle_pressed_color` | `__init__` | 359 | Color setting for circle pressed color. |
| `circle_radius` | `__init__` | 322 | Radius value for circle radius. |
| `circle_radius_spinbox` | `build_tool_options_panel` | 3469 | Spin box widget for circle radius spinbox. |
| `circle_selected_color` | `__init__` | 357 | Color setting for circle selected color. |
| `circle_tool_hint` | `build_tool_options_panel` | 3492 | Help text widget or message for circle tool hint. |
| `circle_tool_page` | `build_tool_options_panel` | 3468 | Page widget for circle tool page. |
| `clear_images_action` | `initUI` | 2703 | Qt action object for clear images action. |
| `console_dock` | `initUI` | 3041 | Dock widget reference for console dock. |
| `context_pixmap_items` | `initData` | 1411 | Stores context pixmap items. |
| `convolution_half_window_points` | `__init__` | 344 | Stores convolution half window points. |
| `convolution_ramp_points` | `__init__` | 345 | Stores convolution ramp points. |
| `current_session_file_path` | `initData` | 1426 | Current value for session file path. |
| `cursor_edit_section_label` | `build_tool_options_panel` | 3267 | Label widget for cursor edit section label. |
| `cursor_freeze_lineedit` | `build_tool_options_panel` | 3268 | Stores cursor freeze lineedit. |
| `cursor_info_edit_separator` | `build_tool_options_panel` | 3266 | Separator widget or layout marker for cursor info edit separator. |
| `cursor_info_label_widgets` | `build_tool_options_panel` | 3250 | Stores cursor info label widgets. |
| `cursor_info_row_widgets` | `build_tool_options_panel` | 3249 | Stores cursor info row widgets. |
| `cursor_info_section_label` | `build_tool_options_panel` | 3248 | Label widget for cursor info section label. |
| `cursor_info_value_labels` | `build_tool_options_panel` | 3251 | Stores cursor info value labels. |
| `cursor_sample_combo` | `build_tool_options_panel` | 3280 | Combo box widget for cursor sample combo. |
| `cursor_sample_combo_catalog_signature` | `invalidate_cursor_sample_combo_cache` | 807 | Stores cursor sample combo catalog signature. |
| `cursor_sample_combo_has_mixed_item` | `invalidate_cursor_sample_combo_cache` | 808 | Stores cursor sample combo has mixed item. |
| `cursor_sample_row` | `build_tool_options_panel` | 3283 | Layout row container for cursor sample row. |
| `cursor_tool_hint` | `build_tool_options_panel` | 3289 | Help text widget or message for cursor tool hint. |
| `cursor_tool_page` | `build_tool_options_panel` | 3247 | Page widget for cursor tool page. |
| `data_table` | `initUI` | 3000 | Stores data table. |
| `default_circle_radius` | `__init__` | 365 | Default value for circle radius. |
| `default_dock_state` | `__init__` | 395 | Default value for dock state. |
| `default_grid_cell_id_direction` | `__init__` | 371 | Default value for grid cell ID direction. |
| `default_grid_columns` | `__init__` | 367 | Number of columns in the active grid definition. |
| `default_grid_horizontal_pitch` | `__init__` | 368 | Default value for grid horizontal pitch. |
| `default_grid_rotation_degrees` | `__init__` | 370 | Default value for grid rotation degrees. |
| `default_grid_rows` | `__init__` | 366 | Number of rows in the active grid definition. |
| `default_grid_vertical_pitch` | `__init__` | 369 | Default value for grid vertical pitch. |
| `delete_tool_hint` | `build_tool_options_panel` | 3295 | Help text widget or message for delete tool hint. |
| `delete_tool_page` | `build_tool_options_panel` | 3294 | Page widget for delete tool page. |
| `deselect_tool_action` | `initUI` | 2735 | Qt action object for deselect tool action. |
| `displayed_image_edit_crop_applied` | `initData` | 1410 | Stores displayed image edit crop applied. |
| `dot_size` | `__init__` | 325 | Size value for dot size. |
| `edit_circle_apply_button` | `build_tool_options_panel` | 3530 | Button widget for edit circle apply button. |
| `edit_circle_cancel_button` | `build_tool_options_panel` | 3532 | Button widget for edit circle cancel button. |
| `edit_circle_cell_id_spinbox` | `build_tool_options_panel` | 3501 | Spin box widget for edit circle cell ID spinbox. |
| `edit_circle_float_button` | `build_tool_options_panel` | 3531 | Button widget for edit circle float button. |
| `edit_circle_offset_x_spinbox` | `build_tool_options_panel` | 3508 | Spin box widget for edit circle offset x spinbox. |
| `edit_circle_offset_y_spinbox` | `build_tool_options_panel` | 3513 | Spin box widget for edit circle offset y spinbox. |
| `edit_circle_radius_spinbox` | `build_tool_options_panel` | 3503 | Spin box widget for edit circle radius spinbox. |
| `edit_circle_tool_hint` | `build_tool_options_panel` | 3527 | Help text widget or message for edit circle tool hint. |
| `edit_circle_tool_page` | `build_tool_options_panel` | 3500 | Page widget for edit circle tool page. |
| `edit_grid_apply_button` | `build_tool_options_panel` | 3642 | Button widget for edit grid apply button. |
| `edit_grid_cancel_button` | `build_tool_options_panel` | 3644 | Button widget for edit grid cancel button. |
| `edit_grid_float_button` | `build_tool_options_panel` | 3643 | Button widget for edit grid float button. |
| `edit_grid_hpitch_spinbox` | `build_tool_options_panel` | 3603 | Spin box widget for edit grid hpitch spinbox. |
| `edit_grid_offset_x_spinbox` | `build_tool_options_panel` | 3618 | Spin box widget for edit grid offset x spinbox. |
| `edit_grid_offset_y_spinbox` | `build_tool_options_panel` | 3623 | Spin box widget for edit grid offset y spinbox. |
| `edit_grid_radius_spinbox` | `build_tool_options_panel` | 3598 | Spin box widget for edit grid radius spinbox. |
| `edit_grid_rotation_spinbox` | `build_tool_options_panel` | 3613 | Spin box widget for edit grid rotation spinbox. |
| `edit_grid_tool_hint` | `build_tool_options_panel` | 3639 | Help text widget or message for edit grid tool hint. |
| `edit_grid_tool_page` | `build_tool_options_panel` | 3597 | Page widget for edit grid tool page. |
| `edit_grid_vpitch_spinbox` | `build_tool_options_panel` | 3608 | Spin box widget for edit grid vpitch spinbox. |
| `edit_group_base_horizontal_pitch` | `__init__` | 377 | Spacing value for edit group base horizontal pitch. |
| `edit_group_base_radii_by_number` | `__init__` | 375 | Stores edit group base radii by number. |
| `edit_group_base_radius` | `__init__` | 374 | Radius value for edit group base radius. |
| `edit_group_base_rotation_degrees` | `__init__` | 379 | Stores edit group base rotation degrees. |
| `edit_group_base_vertical_pitch` | `__init__` | 378 | Spacing value for edit group base vertical pitch. |
| `edit_group_horizontal_pitch_delta` | `__init__` | 380 | Stores edit group horizontal pitch delta. |
| `edit_group_radius_delta` | `__init__` | 376 | Stores edit group radius delta. |
| `edit_group_rotation_delta` | `__init__` | 382 | Stores edit group rotation delta. |
| `edit_group_vertical_pitch_delta` | `__init__` | 381 | Stores edit group vertical pitch delta. |
| `edit_session_metadata_action` | `initUI` | 2708 | Qt action object for edit session metadata action. |
| `edit_single_base_radius` | `__init__` | 372 | Radius value for edit single base radius. |
| `edit_single_radius_delta` | `__init__` | 373 | Stores edit single radius delta. |
| `edit_tool_action` | `initUI` | 2734 | Qt action object for edit tool action. |
| `flag_toggle_button` | `initUI` | 2935 | Button widget for flag toggle button. |
| `flagframe_list` | `initData` | 1344 | Ordered list used for flagframe list. |
| `frame_status_label` | `initUI` | 3103 | Label widget for frame status label. |
| `freeze_count_timeseries_headers` | `initData` | 1369 | Column header data for freeze count timeseries headers. |
| `freeze_count_timeseries_rows` | `initData` | 1370 | Row-oriented data for freeze count timeseries rows. |
| `freeze_count_timeseries_summary` | `initData` | 1371 | Summary metadata for freeze count timeseries summary. |
| `freeze_count_timeseries_table` | `initUI` | 3002 | Stores freeze count timeseries table. |
| `freeze_dock` | `initUI` | 3048 | Dock widget reference for freeze dock. |
| `freeze_finder_detect_brightening` | `__init__` | 346 | Stores freeze finder detect brightening. |
| `freeze_finder_prominence` | `__init__` | 342 | Stores freeze finder prominence. |
| `freeze_finder_tail_extend_points` | `__init__` | 343 | Stores freeze finder tail extend points. |
| `freeze_finder_width` | `__init__` | 341 | Geometry value for freeze finder width. |
| `freeze_results_headers` | `apply_manual_freeze_event_indices` | 967 | Column header data for freeze results headers. |
| `freeze_results_rows` | `apply_manual_freeze_event_indices` | 965 | Row-oriented data for freeze results rows. |
| `freeze_table` | `initUI` | 3001 | Stores freeze table. |
| `grayscale_dock` | `initUI` | 3045 | Dock widget reference for grayscale dock. |
| `grayscale_plot_dock` | `initUI` | 3046 | Dock widget reference for grayscale plot dock. |
| `grayscale_plot_widget` | `initUI` | 3003 | Qt widget reference for grayscale plot widget. |
| `grayscale_results_headers` | `initData` | 1365 | Column header data for grayscale results headers. |
| `grayscale_results_rows` | `initData` | 1366 | Row-oriented data for grayscale results rows. |
| `grid_apply_button` | `build_tool_options_panel` | 3592 | Button widget for grid apply button. |
| `grid_cancel_button` | `build_tool_options_panel` | 3594 | Button widget for grid cancel button. |
| `grid_cell_id_direction` | `__init__` | 337 | Stores grid cell ID direction. |
| `grid_columns` | `__init__` | 333 | Number of columns in the active grid definition. |
| `grid_columns_spinbox` | `build_tool_options_panel` | 3541 | Spin box widget for grid columns spinbox. |
| `grid_float_button` | `build_tool_options_panel` | 3593 | Button widget for grid float button. |
| `grid_horizontal_pitch` | `__init__` | 334 | Spacing value for grid horizontal pitch. |
| `grid_hpitch_spinbox` | `build_tool_options_panel` | 3551 | Spin box widget for grid hpitch spinbox. |
| `grid_offset_x_spinbox` | `build_tool_options_panel` | 3566 | Spin box widget for grid offset x spinbox. |
| `grid_offset_y_spinbox` | `build_tool_options_panel` | 3571 | Spin box widget for grid offset y spinbox. |
| `grid_pitch_wheel_step` | `__init__` | 339 | Stores grid pitch wheel step. |
| `grid_preview_fill_color` | `__init__` | 361 | Color setting for grid preview fill color. |
| `grid_preview_floating` | `initData` | 1416 | Stores grid preview floating. |
| `grid_preview_handle_item` | `initData` | 1414 | Stores grid preview handle item. |
| `grid_preview_items` | `initData` | 1413 | Stores grid preview items. |
| `grid_preview_origin_pixels` | `initData` | 1415 | Stores grid preview origin pixels. |
| `grid_preview_outline_color` | `__init__` | 360 | Color setting for grid preview outline color. |
| `grid_radius_spinbox` | `build_tool_options_panel` | 3546 | Spin box widget for grid radius spinbox. |
| `grid_rotation_degrees` | `__init__` | 336 | Stores grid rotation degrees. |
| `grid_rotation_spinbox` | `build_tool_options_panel` | 3561 | Spin box widget for grid rotation spinbox. |
| `grid_rows` | `__init__` | 332 | Number of rows in the active grid definition. |
| `grid_rows_spinbox` | `build_tool_options_panel` | 3536 | Spin box widget for grid rows spinbox. |
| `grid_tilt_wheel_step` | `__init__` | 340 | Stores grid tilt wheel step. |
| `grid_tool_action` | `initUI` | 2733 | Qt action object for grid tool action. |
| `grid_tool_hint` | `build_tool_options_panel` | 3589 | Help text widget or message for grid tool hint. |
| `grid_tool_page` | `build_tool_options_panel` | 3535 | Page widget for grid tool page. |
| `grid_vertical_pitch` | `__init__` | 335 | Spacing value for grid vertical pitch. |
| `grid_vpitch_spinbox` | `build_tool_options_panel` | 3556 | Spin box widget for grid vpitch spinbox. |
| `history_restoring` | `__init__` | 390 | Stores history restoring. |
| `imageNames` | `initData` | 1350 | Stores image names. |
| `imagePaths` | `initData` | 1349 | Stores image paths. |
| `image_cache` | `initData` | 1402 | Cache entry or cache container for image cache. |
| `image_cache_size` | `initData` | 1403 | Cache entry or cache container for image cache size. |
| `image_edit_action` | `initUI` | 2719 | Qt action object for image edit action. |
| `image_edit_contrast` | `initData` | 1331 | Stores image edit contrast. |
| `image_edit_contrast_block` | `build_tool_options_panel` | 3352 | Grouped layout block for image edit contrast block. |
| `image_edit_contrast_header` | `build_tool_options_panel` | 3359 | Header widget or layout object for image edit contrast header. |
| `image_edit_contrast_label` | `build_tool_options_panel` | 3365 | Label widget for image edit contrast label. |
| `image_edit_contrast_separator` | `build_tool_options_panel` | 3389 | Separator widget or layout marker for image edit contrast separator. |
| `image_edit_contrast_slider` | `build_tool_options_panel` | 3377 | Slider widget for image edit contrast slider. |
| `image_edit_contrast_spinbox` | `build_tool_options_panel` | 3369 | Spin box widget for image edit contrast spinbox. |
| `image_edit_crop_angle` | `initData` | 1341 | Angle value for image edit crop angle. |
| `image_edit_crop_apply_button` | `build_tool_options_panel` | 3439 | Button widget for image edit crop apply button. |
| `image_edit_crop_button_row` | `build_tool_options_panel` | 3430 | Layout row container for image edit crop button row. |
| `image_edit_crop_center_x` | `initData` | 1337 | Geometry value for image edit crop center x. |
| `image_edit_crop_center_y` | `initData` | 1338 | Geometry value for image edit crop center y. |
| `image_edit_crop_height` | `initData` | 1340 | Geometry value for image edit crop height. |
| `image_edit_crop_overlay` | `initData` | 1409 | Overlay object used for image edit crop overlay. |
| `image_edit_crop_reset_button` | `build_tool_options_panel` | 3444 | Button widget for image edit crop reset button. |
| `image_edit_crop_section_label` | `build_tool_options_panel` | 3429 | Label widget for image edit crop section label. |
| `image_edit_crop_start_button` | `build_tool_options_panel` | 3434 | Button widget for image edit crop start button. |
| `image_edit_crop_width` | `initData` | 1339 | Geometry value for image edit crop width. |
| `image_edit_exposure` | `initData` | 1330 | Stores image edit exposure. |
| `image_edit_exposure_block` | `build_tool_options_panel` | 3312 | Grouped layout block for image edit exposure block. |
| `image_edit_exposure_header` | `build_tool_options_panel` | 3319 | Header widget or layout object for image edit exposure header. |
| `image_edit_exposure_label` | `build_tool_options_panel` | 3325 | Label widget for image edit exposure label. |
| `image_edit_exposure_separator` | `build_tool_options_panel` | 3350 | Separator widget or layout marker for image edit exposure separator. |
| `image_edit_exposure_slider` | `build_tool_options_panel` | 3338 | Slider widget for image edit exposure slider. |
| `image_edit_exposure_spinbox` | `build_tool_options_panel` | 3329 | Spin box widget for image edit exposure spinbox. |
| `image_edit_histogram_scale_cache` | `initData` | 1407 | Cache entry or cache container for image edit histogram scale cache. |
| `image_edit_histogram_separator` | `build_tool_options_panel` | 3310 | Separator widget or layout marker for image edit histogram separator. |
| `image_edit_histogram_timer` | `initUI` | 2915 | Timer object used for image edit histogram timer. |
| `image_edit_histogram_widget` | `build_tool_options_panel` | 3307 | Qt widget reference for image edit histogram widget. |
| `image_edit_preview_in_progress` | `initData` | 1356 | Tracks whether image edit preview in progress. |
| `image_edit_preview_timer` | `initUI` | 2911 | Timer object used for image edit preview timer. |
| `image_edit_tool_hint` | `build_tool_options_panel` | 3463 | Help text widget or message for image edit tool hint. |
| `image_edit_tool_page` | `build_tool_options_panel` | 3300 | Page widget for image edit tool page. |
| `image_edit_uniform_exposure_area_button` | `build_tool_options_panel` | 3396 | Button widget for image edit uniform exposure area button. |
| `image_edit_uniform_exposure_area_height` | `initData` | 1335 | Geometry value for image edit uniform exposure area height. |
| `image_edit_uniform_exposure_area_width` | `initData` | 1334 | Geometry value for image edit uniform exposure area width. |
| `image_edit_uniform_exposure_area_x` | `initData` | 1332 | Geometry value for image edit uniform exposure area x. |
| `image_edit_uniform_exposure_area_y` | `initData` | 1333 | Geometry value for image edit uniform exposure area y. |
| `image_edit_uniform_exposure_button_row` | `build_tool_options_panel` | 3392 | Layout row container for image edit uniform exposure button row. |
| `image_edit_uniform_exposure_hint` | `build_tool_options_panel` | 3424 | Help text widget or message for image edit uniform exposure hint. |
| `image_edit_uniform_exposure_offsets` | `initData` | 1336 | Offset values for image edit uniform exposure offsets. |
| `image_edit_uniform_exposure_overlay` | `initData` | 1408 | Overlay object used for image edit uniform exposure overlay. |
| `image_edit_uniform_exposure_reset_button` | `build_tool_options_panel` | 3406 | Button widget for image edit uniform exposure reset button. |
| `image_edit_uniform_exposure_run_button` | `build_tool_options_panel` | 3401 | Button widget for image edit uniform exposure run button. |
| `image_edit_uniform_exposure_section_label` | `build_tool_options_panel` | 3391 | Label widget for image edit uniform exposure section label. |
| `image_edit_uniform_exposure_separator` | `build_tool_options_panel` | 3427 | Separator widget or layout marker for image edit uniform exposure separator. |
| `image_index` | `initData` | 1351 | Zero-based index for image index. |
| `image_list_dock` | `initUI` | 3040 | Dock widget reference for image list dock. |
| `image_list_enabled` | `__init__` | 389 | Tracks whether image list enabled. |
| `image_list_entry_ids` | `initData` | 1420 | Stores image list entry ids. |
| `image_list_model` | `initUI` | 2985 | Stores image list model. |
| `image_list_widget` | `initUI` | 2986 | Qt widget reference for image list widget. |
| `image_name_label` | `initUI` | 3116 | Label widget for image name label. |
| `image_preview_timer` | `initUI` | 2908 | Timer object used for image preview timer. |
| `image_slider` | `initUI` | 2900 | Slider widget for image slider. |
| `image_textbox` | `initUI` | 2924 | Stores image textbox. |
| `image_width` | `initData` | 1348 | Geometry value for image width. |
| `import_csu_is_dat_action` | `initUI` | 2715 | Qt action object for import csu is dat action. |
| `import_tamu_linkam_xlsx_action` | `initUI` | 2716 | Qt action object for import tamu linkam xlsx action. |
| `import_temperature_csv_action` | `initUI` | 2714 | Qt action object for import temperature CSV action. |
| `keyframe_cell_items_dict` | `initData` | 1345 | Mapping used for keyframe cell items dict. |
| `keyframe_list` | `initData` | 1343 | Ordered list used for keyframe list. |
| `keyframe_toggle_button` | `initUI` | 2934 | Button widget for keyframe toggle button. |
| `last_committed_image_index` | `initData` | 1352 | Most recently used value for committed image index. |
| `last_freeze_output_path` | `apply_manual_freeze_event_indices` | 968 | Most recently used value for freeze output path. |
| `last_grayscale_output_path` | `initData` | 1363 | Most recently used value for grayscale output path. |
| `last_standard_temperature_frame_interval_seconds` | `initData` | 1381 | Most recently used value for standard temperature frame interval seconds. |
| `last_standard_temperature_generated_start_text` | `initData` | 1380 | Most recently used value for standard temperature generated start text. |
| `last_standard_temperature_image_timestamp_source` | `initData` | 1376 | Most recently used value for standard temperature image timestamp source. |
| `last_standard_temperature_image_timestamp_style` | `initData` | 1377 | Most recently used value for standard temperature image timestamp style. |
| `last_standard_temperature_temperature_timestamp_style` | `initData` | 1378 | Most recently used value for standard temperature temperature timestamp style. |
| `last_standard_temperature_temperature_unit` | `initData` | 1382 | Most recently used value for standard temperature temperature unit. |
| `last_standard_temperature_use_image_timestamp_style` | `initData` | 1379 | Most recently used value for standard temperature use image timestamp style. |
| `last_temperature_blank_sample_names` | `initData` | 1375 | Most recently used value for temperature blank sample names. |
| `last_temperature_calibration_path` | `initData` | 1373 | Most recently used value for temperature calibration path. |
| `last_temperature_import_path` | `initData` | 1372 | Most recently used value for temperature import path. |
| `last_temperature_reset_temperature` | `initData` | 1374 | Most recently used value for temperature reset temperature. |
| `leftButton` | `initUI` | 2932 | Stores left button. |
| `maximum_zoom` | `__init__` | 324 | Stores maximum zoom. |
| `new_session_action` | `initUI` | 2704 | Qt action object for new session action. |
| `next_cell_id` | `initData` | 1325 | Next value to allocate for cell ID. |
| `next_image_list_entry_id` | `initData` | 1421 | Next value to allocate for image list entry ID. |
| `next_sample_id` | `recompute_next_sample_id` | 614 | Next value to allocate for sample ID. |
| `open_session_action` | `initUI` | 2705 | Qt action object for open session action. |
| `output_results_action` | `initUI` | 2713 | Qt action object for output results action. |
| `output_state` | `initData` | 1399 | State bundle for output state. |
| `pan_tool_action` | `initUI` | 2736 | Qt action object for pan tool action. |
| `pen_width` | `__init__` | 323 | Geometry value for pen width. |
| `pending_analysis_before_state` | `initData` | 1389 | Pending value for analysis before state. |
| `pending_analysis_progress_index` | `initData` | 1388 | Pending value for analysis progress index. |
| `pending_image_edit_histogram_apply_crop` | `initData` | 1358 | Pending value for image edit histogram apply crop. |
| `pending_image_edit_histogram_qimage` | `initData` | 1357 | Pending value for image edit histogram qimage. |
| `pending_image_edit_preview_state` | `initData` | 1355 | Pending value for image edit preview state. |
| `pending_navigation_before_index` | `initData` | 1383 | Pending value for navigation before index. |
| `pending_navigation_history_text` | `initData` | 1384 | Pending value for navigation history text. |
| `pending_preview_image_index` | `initData` | 1353 | Pending value for preview image index. |
| `pixmap_cache` | `initData` | 1404 | Cache entry or cache container for pixmap cache. |
| `pixmap_cache_size` | `initData` | 1405 | Cache entry or cache container for pixmap cache size. |
| `pixmap_item` | `update_display_pixmaps` | 9435 | Stores pixmap item. |
| `placeholder_items` | `initData` | 1412 | Stores placeholder items. |
| `preferences_action` | `initUI` | 2690 | Qt action object for preferences action. |
| `preview_cancel_shortcut` | `initUI` | 2836 | Stores preview cancel shortcut. |
| `preview_confirm_shortcut` | `initUI` | 2830 | Stores preview confirm shortcut. |
| `preview_confirm_shortcut_enter` | `initUI` | 2833 | Stores preview confirm shortcut enter. |
| `preview_frame_update_in_progress` | `initData` | 1354 | Tracks whether preview frame update in progress. |
| `preview_handle_size` | `__init__` | 362 | Size value for preview handle size. |
| `preview_offset_x` | `initData` | 1417 | Geometry value for preview offset x. |
| `preview_offset_y` | `initData` | 1418 | Geometry value for preview offset y. |
| `radius_status_label` | `initUI` | 3101 | Label widget for radius status label. |
| `radius_textbox` | `initUI` | 3105 | Stores radius textbox. |
| `radius_wheel_step` | `__init__` | 338 | Stores radius wheel step. |
| `raw_image_cache` | `initData` | 1400 | Cache entry or cache container for raw image cache. |
| `raw_image_cache_size` | `initData` | 1401 | Cache entry or cache container for raw image cache size. |
| `raw_image_size_cache` | `initData` | 1406 | Cache entry or cache container for raw image size cache. |
| `redo_action` | `initUI` | 2725 | Qt action object for redo action. |
| `relink_images_action` | `initUI` | 2711 | Qt action object for relink images action. |
| `remove_selected_action` | `initUI` | 2702 | Qt action object for remove selected action. |
| `rendered_cell_items` | `initData` | 1324 | Stores rendered cell items. |
| `reset_cursor_action` | `initUI` | 2731 | Qt action object for reset cursor action. |
| `restore_window_action` | `initUI` | 3073 | Qt action object for restore window action. |
| `results_table_tabs` | `initUI` | 3007 | Stores results table tabs. |
| `results_tables_dock` | `initUI` | 3047 | Dock widget reference for results tables dock. |
| `rightButton` | `initUI` | 2933 | Stores right button. |
| `run_analysis_action` | `initUI` | 2712 | Qt action object for run analysis action. |
| `sample_add_button` | `build_sample_catalog_panel` | 3744 | Button widget for sample add button. |
| `sample_catalog` | `ensure_sample_catalog_matches_cell_records` | 769 | Stores sample catalog. |
| `sample_catalog_dock` | `initUI` | 3043 | Dock widget reference for sample catalog dock. |
| `sample_catalog_tree` | `build_sample_catalog_panel` | 3712 | Stores sample catalog tree. |
| `sample_catalog_tree_delegate` | `build_sample_catalog_panel` | 3734 | Stores sample catalog tree delegate. |
| `sample_catalog_tree_syncing` | `build_sample_catalog_panel` | 3711 | Stores sample catalog tree syncing. |
| `sample_catalog_widget` | `initUI` | 3020 | Qt widget reference for sample catalog widget. |
| `sample_delete_button` | `build_sample_catalog_panel` | 3746 | Button widget for sample delete button. |
| `sample_manager_action` | `initUI` | 2718 | Qt action object for sample manager action. |
| `sample_name_pattern` | `set_preferences` | 429 | Stores sample name pattern. |
| `save_session_action` | `initUI` | 2706 | Qt action object for save session action. |
| `save_session_as_action` | `initUI` | 2707 | Qt action object for save session as action. |
| `scene` | `initUI` | 2967 | Stores scene. |
| `select_tool_action` | `initUI` | 2732 | Qt action object for select tool action. |
| `session_active` | `initData` | 1425 | Tracks whether session active. |
| `session_date` | `initData` | 1394 | Stores session date. |
| `session_institution` | `initData` | 1393 | Stores session institution. |
| `session_metadata_status_label` | `initUI` | 3097 | Label widget for session metadata status label. |
| `session_project_name` | `initData` | 1391 | Display name for session project name. |
| `session_user_name` | `initData` | 1392 | Display name for session user name. |
| `session_well_volume_uL` | `initData` | 1395 | Stores session well volume u l. |
| `slider_buttons_layout` | `initUI` | 2955 | Stores slider buttons layout. |
| `slider_buttons_widget` | `initUI` | 2959 | Qt widget reference for slider buttons widget. |
| `slider_drag_start_index` | `initData` | 1385 | Zero-based index for slider drag start index. |
| `slider_maxzoom_pixel_interval` | `__init__` | 326 | Stores slider maxzoom pixel interval. |
| `slider_tick_pixel_interval` | `__init__` | 327 | Stores slider tick pixel interval. |
| `sort_images_action` | `initUI` | 2717 | Qt action object for sort images action. |
| `sort_mode` | `__init__` | 331 | Mode value for sort mode. |
| `space_held` | `__init__` | 394 | Stores space held. |
| `statusBar` | `initUI` | 3094 | Stores status bar. |
| `syncing_image_list_selection` | `initData` | 1422 | Stores syncing image list selection. |
| `temperature_cycle_warmup_hysteresis_c` | `__init__` | 347 | Stores temperature cycle warmup hysteresis c. |
| `temporary_event_data` | `__init__` | 393 | Stores temporary event data. |
| `terminal` | `initUI` | 2981 | Stores terminal. |
| `timer` | `initData` | 1398 | Stores timer. |
| `timeseries_convolution_line_width` | `__init__` | 350 | Geometry value for timeseries convolution line width. |
| `timeseries_current_frame_color` | `__init__` | 353 | Color setting for timeseries current frame color. |
| `timeseries_current_frame_line_width` | `__init__` | 354 | Geometry value for timeseries current frame line width. |
| `timeseries_freeze_line_color` | `__init__` | 351 | Color setting for timeseries freeze line color. |
| `timeseries_freeze_line_width` | `__init__` | 352 | Geometry value for timeseries freeze line width. |
| `timeseries_line_width` | `__init__` | 349 | Geometry value for timeseries line width. |
| `timeseries_palette` | `__init__` | 348 | Stores timeseries palette. |
| `tool_mode` | `initData` | 1424 | Mode value for tool mode. |
| `tool_name_dict` | `initUI` | 2888 | Mapping used for tool name dict. |
| `tool_options_dock` | `initUI` | 3042 | Dock widget reference for tool options dock. |
| `tool_options_mode_label` | `build_tool_options_panel` | 3233 | Label widget for tool options mode label. |
| `tool_options_none_label` | `build_tool_options_panel` | 3242 | Label widget for tool options none label. |
| `tool_options_none_page` | `build_tool_options_panel` | 3241 | Page widget for tool options none page. |
| `tool_options_stack` | `build_tool_options_panel` | 3238 | Stores tool options stack. |
| `tool_options_widget` | `initUI` | 3019 | Qt widget reference for tool options widget. |
| `tool_status_label` | `initUI` | 3118 | Label widget for tool status label. |
| `toolbar` | `initUI` | 2857 | Stores toolbar. |
| `undo_action` | `initUI` | 2724 | Qt action object for undo action. |
| `undo_limit` | `__init__` | 328 | Stores undo limit. |
| `undo_redo_enabled` | `__init__` | 388 | Tracks whether undo redo enabled. |
| `undo_stack` | `__init__` | 387 | Stores undo stack. |
| `view` | `initUI` | 2970 | Stores view. |
| `view_slider_widget` | `initUI` | 2978 | Qt widget reference for view slider widget. |
| `viewer_double_action` | `initUI` | 2721 | Qt action object for viewer double action. |
| `viewer_image_count` | `__init__` | 329 | Count value for viewer image count. |
| `viewer_orientation_toggle_action` | `initUI` | 2723 | Qt action object for viewer orientation toggle action. |
| `viewer_single_action` | `initUI` | 2720 | Qt action object for viewer single action. |
| `viewer_split_orientation` | `__init__` | 330 | Stores viewer split orientation. |
| `viewer_triple_action` | `initUI` | 2722 | Qt action object for viewer triple action. |
| `worker` | `outputData` | 9735 | Stores worker. |
| `zoom_slider` | `initUI` | 2943 | Slider widget for zoom slider. |
| `zoom_status_label` | `initUI` | 3102 | Label widget for zoom status label. |
| `zoom_textbox` | `initUI` | 3106 | Stores zoom textbox. |
| `zoom_window_action` | `initUI` | 3071 | Qt action object for zoom window action. |

## Methods

### Analysis and results

| Method | Line | Explanation |
| --- | --- | --- |
| `show_analysis_progress_frame(index)` | 2226 | Implements show analysis progress frame. |
| `get_analysis_progress_interval_ms()` | 2243 | Returns analysis progress interval ms. |
| `enqueue_analysis_progress_frame(index)` | 2246 | Implements enqueue analysis progress frame. |
| `flush_pending_analysis_progress()` | 2259 | Implements flush pending analysis progress. |
| `update_results_tables()` | 4820 | Updates results tables. |
| `update_results_table_visibility()` | 4833 | Updates results table visibility. |
| `set_freeze_count_timeseries_results(headers, rows, summary=None)` | 4852 | Sets freeze count timeseries results. |
| `invalidate_freeze_count_timeseries_results(reason=None)` | 4966 | Invalidates freeze count timeseries results. |
| `invalidate_analysis_results(reason=None)` | 4977 | Invalidates analysis results. |
| `refresh_grayscale_plot()` | 5007 | Refreshes grayscale plot. |
| `grayscale_plot_is_visible()` | 5028 | Implements grayscale plot is visible. |
| `update_grayscale_plot_current_frame()` | 5040 | Updates grayscale plot current frame. |
| `get_plot_current_image_index()` | 5047 | Returns plot current image index. |
| `load_grayscale_results(file_path)` | 6322 | Loads grayscale results. |
| `set_freeze_results(headers, rows)` | 6339 | Sets freeze results. |
| `build_standard_freeze_count_timeseries_results(parsed_timeseries, blank_sample_names=None, image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME, image_timestamp_style=TIMESTAMP_STYLE_AUTO, generated_start_text='', frame_interval_seconds=None, temperature_timestamp_style=TIMESTAMP_STYLE_AUTO, temperature_unit=TEMPERATURE_UNIT_CELSIUS, reset_temperature=None)` | 6720 | Builds standard freeze count timeseries results. |
| `export_grayscale_results_for_external_tool()` | 7601 | Exports grayscale results for external tool. |
| `export_results_csv(checked=False)` | 7639 | Exports results CSV. |
| `onAnalysisDone(index, results)` | 9779 | Implements on analysis done. |

### Cells and samples

| Method | Line | Explanation |
| --- | --- | --- |
| `sample_visual_color(sample_id, alpha=255)` | 538 | Returns sample-related visual color. |
| `sample_visual_color_for_cell(cell_id, alpha=255)` | 548 | Returns sample-related visual color for cell. |
| `refresh_cell_sample_visuals()` | 554 | Refreshes cell sample visuals. |
| `extract_cell_id_from_analysis_header(header_text)` | 560 | Implements extract cell ID from analysis header. |
| `extract_cell_id_from_label(label_text)` | 563 | Implements extract cell ID from label. |
| `ensure_cell_record(cell_id)` | 572 | Ensures cell record. |
| `ensure_cell_registry_matches_scene_cells()` | 575 | Ensures cell registry matches scene cells. |
| `recompute_next_cell_id(preserve_if_larger=True)` | 578 | Recomputes next cell ID. |
| `allocate_cell_id()` | 581 | Allocates cell ID. |
| `cell_id_exists(cell_id, exclude_cell_id=None)` | 584 | Implements cell ID exists. |
| `rename_cell_id(old_cell_id, new_cell_id)` | 587 | Renames cell ID. |
| `clear_cell_analysis()` | 590 | Clears cell analysis. |
| `sync_cell_analysis_from_results()` | 593 | Synchronizes cell analysis from results. |
| `prune_analysis_results_for_deleted_cells(deleted_cell_ids)` | 596 | Prunes analysis results for deleted cells. |
| `recompute_next_sample_id(preserve_if_larger=True)` | 605 | Recomputes next sample ID. |
| `allocate_sample_id()` | 621 | Allocates sample ID. |
| `default_sample_name(sample_id)` | 627 | Returns the default sample name. |
| `sample_name_for_id(sample_id)` | 653 | Returns sample-related name for ID. |
| `sample_record_for_id(sample_id)` | 656 | Returns sample-related record for ID. |
| `default_sample_record(sample_id)` | 665 | Returns the default sample record. |
| `build_freeze_count_timeseries_sample_column_metadata(sample)` | 670 | Builds freeze count timeseries sample column metadata. |
| `freeze_count_timeseries_sample_column_metadata()` | 686 | Implements freeze count timeseries sample column metadata. |
| `ensure_sample_catalog_matches_cell_records()` | 767 | Ensures sample catalog matches cell records. |
| `cursor_sample_catalog_signature()` | 784 | Implements cursor sample catalog signature. |
| `ordered_sample_catalog_records()` | 790 | Returns ordered sample catalog records. |
| `available_sample_names()` | 799 | Implements available sample names. |
| `invalidate_cursor_sample_combo_cache()` | 806 | Invalidates cursor sample combo cache. |
| `set_cursor_sample_combo_mixed_item_visible(visible)` | 810 | Sets cursor sample combo mixed item visible. |
| `refresh_cursor_sample_combo_catalog(include_mixed_item=False, force=False)` | 827 | Refreshes cursor sample combo catalog. |
| `parse_freeze_frame_text(text)` | 918 | Parses freeze frame text. |
| `rebuild_freeze_rows_for_cell(cell_id, freeze_event_indices)` | 924 | Implements rebuild freeze rows for cell. |
| `build_cells_panel_records()` | 975 | Builds cells panel records. |
| `refresh_cells_panel(changed_columns=None, preserve_selection=False)` | 992 | Refreshes cells panel. |
| `sync_cells_panel_selection()` | 1059 | Synchronizes cells panel selection. |
| `handle_cells_panel_selection_changed()` | 1077 | Handles cells panel selection changed. |
| `should_refresh_cells_panel_from_redraw()` | 1090 | Returns whether refresh cells panel from redraw. |
| `handle_cells_panel_visibility_changed(visible)` | 1101 | Handles cells panel visibility changed. |
| `apply_cursor_freeze_frames_edit()` | 1218 | Applies cursor freeze frames edit. |
| `apply_edit_circle_cell_id_edit()` | 1274 | Applies edit circle cell ID edit. |
| `build_cells_panel()` | 3665 | Builds cells panel. |
| `build_sample_catalog_panel()` | 3702 | Builds sample catalog panel. |
| `selected_sample_catalog_id()` | 3764 | Returns selected sample catalog ID. |
| `sample_catalog_field_is_relevant(field_name, sample_record)` | 3779 | Returns sample-related catalog field is relevant. |
| `apply_sample_catalog_tree_field_state(child_item, field_name, sample_record)` | 3787 | Applies sample catalog tree field state. |
| `apply_sample_catalog_tree_item_state(top_item, sample_id, sample_record)` | 3815 | Applies sample catalog tree item state. |
| `sample_catalog_top_item_by_id(sample_id)` | 3835 | Returns sample-related catalog top item by ID. |
| `refresh_sample_catalog_tree(select_sample_id=None, preserve_selection=True)` | 3844 | Refreshes sample catalog tree. |
| `update_sample_catalog_buttons()` | 3908 | Updates sample catalog buttons. |
| `add_sample_catalog_entry()` | 3913 | Implements add sample catalog entry. |
| `delete_selected_sample_catalog_entry()` | 3923 | Implements delete selected sample catalog entry. |
| `handle_sample_catalog_item_changed(item, column)` | 3956 | Handles sample catalog item changed. |
| `update_cursor_sample_controls()` | 4019 | Updates cursor sample controls. |
| `update_cursor_sample_assignment_state()` | 4056 | Updates cursor sample assignment state. |
| `assign_selected_cells_to_current_sample()` | 4062 | Implements assign selected cells to current sample. |
| `create_sample_from_cursor_controls()` | 4095 | Creates sample from cursor controls. |
| `get_selected_cell_items()` | 4563 | Returns selected cell items. |
| `delete_selected_cells()` | 4566 | Implements delete selected cells. |
| `infer_grid_parameters_from_cells(selected_items)` | 4600 | Infers grid parameters from cells. |
| `handle_scene_cell_selection_changed()` | 4603 | Handles scene cell selection changed. |
| `reselect_cell_ids(cell_ids, sync_tool_panel=True)` | 4610 | Implements reselect cell ids. |
| `show_sample_catalog_manager()` | 4637 | Implements show sample catalog manager. |
| `relabel_freeze_count_timeseries_header_sample_name(header_text, sample_name)` | 4866 | Implements relabel freeze count timeseries header sample name. |
| `refresh_freeze_count_timeseries_metadata_from_sample_catalog(*, relabel_headers=False)` | 4877 | Refreshes freeze count timeseries metadata from sample catalog. |
| `get_plot_target_cell_ids()` | 4996 | Returns plot target cell ids. |
| `push_cell_history(text, before_state, include_analysis=False)` | 6012 | Implements push cell history. |
| `build_freeze_count_timeseries_sample_groups(grouping_mode='samples')` | 6349 | Builds freeze count timeseries sample groups. |
| `edit_current_keyframe_cell_item()` | 7802 | Implements edit current keyframe cell item. |
| `add_cell_item_to_keyframes(added_items=None)` | 7817 | Implements add cell item to keyframes. |
| `delete_cell_item_to_keyframes(cell_id)` | 7845 | Implements delete cell item to keyframes. |
| `delete_cell_items_to_keyframes(cell_ids)` | 7848 | Implements delete cell items to keyframes. |
| `activate_edit_cell_item(cell_item)` | 8212 | Implements activate edit cell item. |
| `anchor_cell_items_to_current_image(cell_items)` | 9487 | Implements anchor cell items to current image. |
| `update_cell_items_selectable_state()` | 10050 | Updates cell items selectable state. |
| `unselect_all_cell_items()` | 10053 | Implements unselect all cell items. |
| `reset_cell_items_edit_chosen()` | 10056 | Resets cell items edit chosen. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__()` | 319 | Initializes the instance. |
| `set_preferences(preserve_session_tool_state=False)` | 400 | Sets preferences. |
| `get_qcolor(color_value)` | 529 | Returns qcolor. |
| `build_freeze_count_timeseries_missing_metadata_report()` | 692 | Builds freeze count timeseries missing metadata report. |
| `show_freeze_count_timeseries_export_notice(exported_paths)` | 745 | Implements show freeze count timeseries export notice. |
| `summarize_integer_list(values, limit=8)` | 846 | Summarizes integer list. |
| `format_integer_list_csv(values)` | 877 | Formats integer list CSV. |
| `parse_integer_csv_text(text, *, allow_empty=True, minimum=None, maximum=None)` | 893 | Parses integer CSV text. |
| `apply_manual_freeze_event_indices(cell_id, freeze_event_indices, refresh_tables=True)` | 942 | Applies manual freeze event indices. |
| `current_single_edit_target_item()` | 1265 | Returns the current single edit target item. |
| `initData()` | 1316 | Implements init data. |
| `image_pixel_to_scene_coordinates(pixel_x, pixel_y, image_rect=None, *, index=None, apply_crop=None)` | 1771 | Implements image pixel to scene coordinates. |
| `scene_to_image_pixel_coordinates(scene_pos, image_rect=None, *, index=None, apply_crop=None)` | 1790 | Implements scene to image pixel coordinates. |
| `format_numeric_value(value)` | 3168 | Formats numeric value. |
| `current_circle_controls()` | 4193 | Returns the current circle controls. |
| `current_grid_controls()` | 4214 | Returns the current grid controls. |
| `handle_circle_radius_spinbox_changed(value)` | 4360 | Handles circle radius spinbox changed. |
| `handle_grid_radius_change(value)` | 4375 | Handles grid radius change. |
| `handle_grid_parameter_change(*_args)` | 4409 | Handles grid parameter change. |
| `clear_grid_preview()` | 4432 | Clears grid preview. |
| `cancel_grid_preview()` | 4437 | Cancels grid preview. |
| `float_grid_preview()` | 4440 | Implements float grid preview. |
| `update_grid_preview()` | 4449 | Updates grid preview. |
| `update_grid_apply_state()` | 4452 | Updates grid apply state. |
| `handle_grid_apply_action()` | 4455 | Handles grid apply action. |
| `handle_circle_apply_action()` | 4458 | Handles circle apply action. |
| `focus_is_text_entry_widget()` | 4461 | Implements focus is text entry widget. |
| `focus_widget_is_within(focus_widget, roots)` | 4503 | Implements focus widget is within. |
| `confirm_active_preview()` | 4525 | Implements confirm active preview. |
| `handle_circle_float_action()` | 4541 | Handles circle float action. |
| `handle_circle_cancel_action()` | 4545 | Handles circle cancel action. |
| `handle_grid_float_action()` | 4556 | Handles grid float action. |
| `handle_grid_cancel_action()` | 4560 | Handles grid cancel action. |
| `get_edit_target_items()` | 4597 | Returns edit target items. |
| `apply_grid_preview()` | 4634 | Applies grid preview. |
| `zoom_window()` | 4643 | Implements zoom window. |
| `eventFilter(watched, event)` | 4729 | Implements event filter. |
| `setup_table_widget(table_widget)` | 4784 | Implements setup table widget. |
| `set_table_data(table_widget, headers, rows)` | 4793 | Sets table data. |
| `update_freeze_count_timeseries_table()` | 4828 | Updates freeze count timeseries table. |
| `cancel_transient_history_state()` | 5248 | Clear unfinished interaction state before undo/redo. |
| `push_snapshot_history(text, before_state)` | 6003 | Implements push snapshot history. |
| `push_data_history(text, before_state)` | 6048 | Implements push data history. |
| `push_navigation_history(text, before_index, after_index)` | 6066 | Implements push navigation history. |
| `format_image_list_entry(index)` | 6077 | Formats image list entry. |
| `populate_image_list()` | 6088 | Implements populate image list. |
| `update_image_list_annotations(rows=None)` | 6096 | Updates image list annotations. |
| `sync_image_list_selection()` | 6110 | Synchronizes image list selection. |
| `handle_image_list_selection(index)` | 6153 | Handles image list selection. |
| `handle_image_list_current_changed(current, previous)` | 6167 | Handles image list current changed. |
| `update_document_interface_state()` | 6216 | Updates document interface state. |
| `get_selected_image_rows()` | 6265 | Returns selected image rows. |
| `navigate_to_image(index, history_text='Change Frame')` | 6275 | Implements navigate to image. |
| `build_freeze_count_timeseries_image_counts(sample_groups, count_mode='cumulative')` | 6406 | Builds freeze count timeseries image counts. |
| `build_freeze_count_timeseries_blank_selection(sample_groups, blank_sample_names=None)` | 6472 | Builds freeze count timeseries blank selection. |
| `build_standard_image_timing_context(parsed_timeseries, image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME, image_timestamp_style=TIMESTAMP_STYLE_AUTO, generated_start_text='', frame_interval_seconds=None, reset_temperature=None)` | 6651 | Builds standard image timing context. |
| `write_csv_table(file_path, headers, rows)` | 7621 | Writes CSV table. |
| `write_freeze_count_timeseries_csv(file_path)` | 7628 | Writes freeze count timeseries CSV. |
| `update_flaggedframe_list(is_flagging)` | 7796 | Updates flaggedframe list. |
| `grid_horizontal_pitch_shortcut_label()` | 7944 | Implements grid horizontal pitch shortcut label. |
| `grid_vertical_pitch_shortcut_label()` | 7947 | Implements grid vertical pitch shortcut label. |
| `grid_tilt_shortcut_label()` | 7950 | Implements grid tilt shortcut label. |
| `is_caps_lock_pressed()` | 7953 | Returns whether caps lock pressed. |
| `is_grid_horizontal_pitch_modifier_active(modifiers)` | 7961 | Returns whether grid horizontal pitch modifier active. |
| `is_grid_tilt_modifier_active(modifiers)` | 7966 | Returns whether grid tilt modifier active. |
| `showAboutDialog()` | 7972 | Implements show about dialog. |
| `showPreferencesDialog()` | 7976 | Implements show preferences dialog. |
| `log(message)` | 7988 | Implements log. |
| `show_detailed_error_dialog(title, summary_text, err, detail_text='')` | 7992 | Implements show detailed error dialog. |
| `show_detailed_information_dialog(title, summary_text, detail_text='')` | 8004 | Implements show detailed information dialog. |
| `file_dialog_options()` | 8016 | Implements file dialog options. |
| `reset_transient_interaction_state()` | 8036 | Hard-clear unfinished preview/edit state without changing the active tool. |
| `cancel_edit_state()` | 8055 | Cancel any active or remembered edit workflow before switching tools. |
| `preserve_edit_state_for_pan()` | 8088 | Remember the current edit workflow so pan can return to it. |
| `is_pan_interaction_active()` | 8181 | Returns whether pan interaction active. |
| `enter_temporary_pan_mode()` | 8187 | Enters temporary pan mode. |
| `get_image_paths_from_folder(input_dirpath)` | 8263 | Returns image paths from folder. |
| `natural_sort_key(file_path)` | 8279 | Implements natural sort key. |
| `get_exif_sort_value(file_path)` | 8285 | Returns exif sort value. |
| `is_sort_mode_available(mode, file_paths=None)` | 8296 | Returns whether sort mode available. |
| `get_sort_availability(file_paths=None)` | 8316 | Returns sort availability. |
| `sort_image_paths(file_paths, mode=None)` | 8326 | Implements sort image paths. |
| `openSortImagesDialog()` | 8343 | Implements open sort images dialog. |
| `open_add_images_dialog()` | 8401 | Implements open add images dialog. |
| `loadFolder()` | 8416 | Implements load folder. |
| `loadImages()` | 8426 | Implements load images. |
| `relink_images_folder(checked=False)` | 8488 | Implements relink images folder. |
| `load_aux(input_imagePath)` | 8744 | Loads aux. |
| `remove_selected_image()` | 8820 | Removes selected image. |
| `remove_selected_list_images()` | 8829 | Removes selected list images. |
| `reset_pending_frame_navigation_state(stop_timer=False)` | 9035 | Resets pending frame navigation state. |
| `finalize_frame_update(index)` | 9172 | Implements finalize frame update. |
| `handle_frame_navigation_shortcut(key)` | 9283 | Handles frame navigation shortcut. |
| `resize_image_textbox()` | 9307 | Implements resize image textbox. |
| `updateRadiusTextbox()` | 9490 | Implements update radius textbox. |
| `updateCircleRadius_from_textedit()` | 9504 | Implements update circle radius from textedit. |
| `updateZoomTextbox()` | 9516 | Implements update zoom textbox. |
| `updateZoomLevel()` | 9520 | Implements update zoom level. |
| `updateButtonStates()` | 9529 | Implements update button states. |
| `undo()` | 9573 | Implements undo. |
| `redo()` | 9586 | Implements redo. |
| `keyPressEvent(event)` | 9599 | Qt key-press event handler. |
| `keyReleaseEvent(event)` | 9680 | Qt key-release event handler. |
| `outputData()` | 9723 | Implements output data. |
| `out_put_interpolation()` | 9772 | Implements out put interpolation. |
| `onThreadFinished()` | 9785 | Implements on thread finished. |
| `key_press_button_highlight(button)` | 9853 | Implements key press button highlight. |
| `reset_button_stylesheet(theme=None)` | 9933 | Resets button stylesheet. |
| `update_toggle_flagging_button_icon(theme=None)` | 10027 | Updates toggle flagging button icon. |
| `reset_button_icon(theme=None)` | 10040 | Resets button icon. |
| `switch_light_dark_mode(theme=None)` | 10060 | Implements switch light dark mode. |
| `resizeEvent(event)` | 10068 | Qt resize event handler for this widget. |
| `closeEvent(event)` | 10073 | Implements close event. |
| `load_preferences_from_xml()` | 10076 | Loads preferences from xml. |

### Image display and cache

| Method | Line | Explanation |
| --- | --- | --- |
| `format_numeric_display(value, decimals=1)` | 862 | Formats numeric display. |
| `get_raw_image_dimensions(index)` | 1719 | Returns raw image dimensions. |
| `get_current_raw_image_dimensions()` | 1741 | Returns current raw image dimensions. |
| `clear_image_caches()` | 9044 | Clears image caches. |
| `get_cached_raw_image(image_path)` | 9051 | Returns cached raw image. |
| `updateImage(index, preview=False)` | 9222 | Implements update image. |
| `updateImageFromTextbox()` | 9298 | Implements update image from textbox. |
| `get_cached_image(index, *, apply_crop=None)` | 9321 | Returns cached image. |
| `get_cached_pixmap(index, *, apply_crop=None)` | 9348 | Returns cached pixmap. |
| `get_display_slots(current_index)` | 9367 | Returns display slots. |
| `clear_context_pixmaps()` | 9386 | Clears context pixmaps. |
| `update_display_pixmaps(current_index, *, apply_crop=None)` | 9394 | Updates display pixmaps. |
| `displayMarkedRegions()` | 9472 | Implements display marked regions. |
| `interpolate_and_displayMarkedRegions(index, preview=False)` | 9477 | Implements interpolate and display marked regions. |

### Image edit

| Method | Line | Explanation |
| --- | --- | --- |
| `apply_image_edit_state(state, *, invalidate_results=False, refresh_display=True, sync_controls=True)` | 1465 | Applies image edit state. |
| `refresh_current_image_edit_visuals()` | 1576 | Refreshes current image edit visuals. |
| `prewarm_current_image_edit_render_cache()` | 1597 | Implements prewarm current image edit render cache. |
| `get_image_edit_histogram_interval_ms()` | 1607 | Returns image edit histogram interval ms. |
| `request_image_edit_histogram_refresh(q_image=None, *, immediate=False, apply_crop=None)` | 1610 | Implements request image edit histogram refresh. |
| `flush_pending_image_edit_histogram()` | 1624 | Implements flush pending image edit histogram. |
| `normalize_image_edit_uniform_exposure_area_state(area_state=None, *, raw_width=None, raw_height=None)` | 1631 | Normalizes image edit uniform exposure area state. |
| `current_image_edit_uniform_exposure_area_state(*, index=None)` | 1636 | Returns the current image edit uniform exposure area state. |
| `current_image_edit_uniform_exposure_state()` | 1654 | Returns the current image edit uniform exposure state. |
| `compose_image_edit_state(*, exposure=None, contrast=None, uniform_exposure=None, crop=None)` | 1665 | Implements compose image edit state. |
| `has_image_edit_uniform_exposure_area()` | 1673 | Returns whether image edit uniform exposure area. |
| `has_image_edit_uniform_exposure()` | 1684 | Returns whether image edit uniform exposure. |
| `get_image_edit_uniform_exposure_offset(*, index=None, image_path=None)` | 1687 | Returns image edit uniform exposure offset. |
| `current_image_edit_total_exposure(*, index=None, image_path=None)` | 1700 | Returns the current image edit total exposure. |
| `current_image_edit_crop_state(*, index=None)` | 1706 | Returns the current image edit crop state. |
| `normalize_image_edit_crop_state(crop_state=None, *, raw_width=None, raw_height=None)` | 1746 | Normalizes image edit crop state. |
| `should_apply_crop_in_display()` | 1751 | Returns whether apply crop in display. |
| `current_image_edit_crop_transform(index=None, *, apply_crop=None)` | 1754 | Returns the current image edit crop transform. |
| `sync_image_edit_controls()` | 1806 | Synchronizes image edit controls. |
| `refresh_image_edit_histogram(q_image=None, *, apply_crop=None)` | 1842 | Refreshes image edit histogram. |
| `begin_image_edit_history(text)` | 1910 | Begins image edit history. |
| `commit_image_edit_history(text=None)` | 1918 | Commits image edit history. |
| `log_image_edit_change(history_text)` | 1929 | Implements log image edit change. |
| `get_image_edit_preview_interval_ms()` | 1954 | Returns image edit preview interval ms. |
| `reset_pending_image_edit_preview_state(stop_timer=False)` | 1957 | Resets pending image edit preview state. |
| `compose_pending_image_edit_preview_state(*, exposure=None, contrast=None)` | 1963 | Implements compose pending image edit preview state. |
| `queue_image_edit_preview_state(state)` | 1975 | Implements queue image edit preview state. |
| `flush_pending_image_edit_preview()` | 1981 | Implements flush pending image edit preview. |
| `handle_image_edit_exposure_slider_changed(slider_value)` | 2000 | Handles image edit exposure slider changed. |
| `handle_image_edit_exposure_spinbox_changed(exposure_value)` | 2019 | Handles image edit exposure spinbox changed. |
| `handle_image_edit_exposure_slider_released()` | 2032 | Handles image edit exposure slider released. |
| `handle_image_edit_contrast_slider_changed(contrast_value)` | 2044 | Handles image edit contrast slider changed. |
| `handle_image_edit_contrast_spinbox_changed(contrast_value)` | 2063 | Handles image edit contrast spinbox changed. |
| `handle_image_edit_contrast_slider_released()` | 2076 | Handles image edit contrast slider released. |
| `is_image_edit_uniform_exposure_area_active()` | 2088 | Returns whether image edit uniform exposure area active. |
| `begin_image_edit_uniform_exposure_area()` | 2091 | Begins image edit uniform exposure area. |
| `end_image_edit_uniform_exposure_area()` | 2112 | Ends image edit uniform exposure area. |
| `handle_image_edit_uniform_exposure_area_button()` | 2121 | Handles image edit uniform exposure area button. |
| `handle_image_edit_uniform_exposure_overlay_changed(area_state, finalize=False)` | 2127 | Handles image edit uniform exposure overlay changed. |
| `ensure_image_edit_uniform_exposure_overlay()` | 2158 | Ensures image edit uniform exposure overlay. |
| `sync_image_edit_uniform_exposure_overlay()` | 2169 | Synchronizes image edit uniform exposure overlay. |
| `show_image_edit_progress_frame(index)` | 2208 | Implements show image edit progress frame. |
| `compute_image_edit_uniform_exposure_solution(area_state, reference_index, progress_callback=None)` | 2268 | Computes image edit uniform exposure solution. |
| `run_image_edit_uniform_exposure()` | 2328 | Implements run image edit uniform exposure. |
| `reset_image_edit_uniform_exposure()` | 2366 | Resets image edit uniform exposure. |
| `is_image_edit_crop_active()` | 2385 | Returns whether image edit crop active. |
| `get_image_edit_crop_draft_state()` | 2388 | Returns image edit crop draft state. |
| `discard_image_edit_crop_draft()` | 2394 | Implements discard image edit crop draft. |
| `reset_image_edit_crop()` | 2398 | Resets image edit crop. |
| `begin_image_edit_crop()` | 2426 | Begins image edit crop. |
| `handle_image_edit_crop_primary_button()` | 2456 | Handles image edit crop primary button. |
| `apply_image_edit_crop()` | 2462 | Applies image edit crop. |
| `trigger_image_edit_crop_apply_button()` | 2483 | Implements trigger image edit crop apply button. |
| `cancel_image_edit_crop()` | 2491 | Cancels image edit crop. |
| `handle_image_edit_crop_overlay_changed(crop_state, finalize=False)` | 2503 | Handles image edit crop overlay changed. |
| `ensure_image_edit_crop_overlay()` | 2512 | Ensures image edit crop overlay. |
| `sync_image_edit_crop_overlay()` | 2523 | Synchronizes image edit crop overlay. |
| `reset_image_edit_slider_to_default(slider)` | 4704 | Resets image edit slider to default. |
| `push_image_edit_history(text, before_state)` | 6057 | Implements push image edit history. |
| `apply_image_edit_tool_ui()` | 8110 | Applies image edit tool UI. |

### Session and state

| Method | Line | Explanation |
| --- | --- | --- |
| `serialize_cell_records()` | 566 | Serializes cell records. |
| `deserialize_cell_records(payload)` | 569 | Deserializes cell records. |
| `serialize_sample_catalog()` | 599 | Serializes sample catalog. |
| `deserialize_sample_catalog(payload)` | 602 | Deserializes sample catalog. |
| `restore_add_defaults(include_grid=False)` | 1307 | Restores add defaults. |
| `serialize_session_metadata()` | 1429 | Serializes session metadata. |
| `serialize_image_edit_state()` | 1438 | Serializes image edit state. |
| `apply_session_metadata(metadata)` | 2542 | Applies session metadata. |
| `format_session_metadata_status_text()` | 2551 | Formats session metadata status text. |
| `update_session_metadata_status_label()` | 2567 | Updates session metadata status label. |
| `has_session_content()` | 2576 | Returns whether session content. |
| `has_session_save_payload()` | 2603 | Returns whether session save payload. |
| `prompt_save_before_replacing_session(next_action_label='starting a new session')` | 2606 | Implements prompt save before replacing session. |
| `prompt_new_session_metadata(*, window_title='New Session')` | 2628 | Implements prompt new session metadata. |
| `editSessionMetadata(checked=False)` | 2638 | Implements edit session metadata. |
| `newSession(checked=False)` | 2647 | Implements new session. |
| `restore_window()` | 4647 | Restores window. |
| `capture_session_state()` | 5054 | Captures session state. |
| `capture_cell_state(include_analysis=False)` | 5093 | Captures cell state. |
| `capture_data_state()` | 5131 | Captures data state. |
| `capture_image_edit_history_state()` | 5161 | Captures image edit history state. |
| `capture_image_session_state()` | 5167 | Captures image session state. |
| `capture_timeline_marker_state()` | 5204 | Captures timeline marker state. |
| `capture_loaded_images_state()` | 5213 | Captures loaded images state. |
| `get_active_tool_for_restore()` | 5235 | Return the user-facing tool to preserve across undo/redo. |
| `restore_tool_mode_ui(restored_tool_mode=None)` | 5269 | Reapply cursor/drag/action state after undo/redo restores data. |
| `restore_image_session_state(state, preserve_active_tool=False)` | 5303 | Restores image session state. |
| `restore_loaded_images_state(state, preserve_active_tool=False)` | 5436 | Restores loaded images state. |
| `restore_session_state(state, preserve_active_tool=False)` | 5553 | Restores session state. |
| `restore_cell_state(state, preserve_active_tool=False)` | 5695 | Restores cell state. |
| `restore_timeline_marker_state(state, preserve_active_tool=False)` | 5847 | Restores timeline marker state. |
| `restore_data_state(state, preserve_active_tool=False)` | 5906 | Restores data state. |
| `restore_image_edit_history_state(state, preserve_active_tool=False)` | 5960 | Restores image edit history state. |
| `restore_navigation_index(index, preserve_active_tool=False)` | 5978 | Restores navigation index. |
| `push_image_session_history(text, before_state)` | 6030 | Implements push image session history. |
| `push_loaded_images_history(text, before_state)` | 6039 | Implements push loaded images history. |
| `update_session_actions_state()` | 6174 | Updates session actions state. |
| `restore_after_edit_mode()` | 8029 | Restore controls that are temporarily disabled during single-edit. |
| `resort_current_session()` | 8362 | Implements resort current session. |
| `openSession()` | 8437 | Implements open session. |
| `get_missing_session_image_paths()` | 8478 | Returns missing session image paths. |
| `handle_save_session_action()` | 8680 | Handles save session action. |
| `persist_session_to_path(file_path, *, show_errors=True)` | 8684 | Implements persist session to path. |
| `persist_session_to_current_file(*, show_errors=True)` | 8706 | Implements persist session to current file. |
| `saveSession()` | 8712 | Implements save session. |
| `saveSessionAs()` | 8723 | Implements save session as. |
| `remove_images_from_session(rows)` | 8848 | Removes images from session. |
| `clear_loaded_images(checked=False, confirm=True, log_message='Cleared all loaded images from this session')` | 8915 | Clears loaded images. |
| `clear_session(checked=False, confirm=True, log_message='Cleared session', record_history=True, new_metadata=None, activate_session=False)` | 8977 | Clears session. |

### Temperature import

| Method | Line | Explanation |
| --- | --- | --- |
| `build_tamu_freeze_count_timeseries_sample_groups()` | 6463 | Builds tamu freeze count timeseries sample groups. |
| `normalize_temperature_reset_threshold(reset_temperature)` | 6513 | Normalizes temperature reset threshold. |
| `detect_cycle_start_indexes_from_temperatures(temperatures, reset_temperature)` | 6516 | Detects cycle start indexes from temperatures. |
| `build_cycle_ids_from_start_indexes(total_count, cycle_start_indexes)` | 6523 | Builds cycle ids from start indexes. |
| `cycle_index_for_position(position_value, cycle_start_positions)` | 6526 | Implements cycle index for position. |
| `build_tamu_image_timing_context(parsed_timeseries, reset_temperature=None)` | 6532 | Builds tamu image timing context. |
| `build_tamu_cycle_reset_image_counts(sample_groups, image_cycle_ids)` | 6571 | Builds tamu cycle reset image counts. |
| `reconcile_counts_by_cycle(raw_counts, anchor_counts, maximum_count, cycle_ids)` | 6608 | Implements reconcile counts by cycle. |
| `corrected_temperature_for_cell(measured_temperature, cell_id, calibration_by_well)` | 6616 | Implements corrected temperature for cell. |
| `corrected_temperature_for_group(measured_temperature, group, calibration_by_well)` | 6635 | Implements corrected temperature for group. |
| `build_csu_freeze_count_timeseries_results(parsed_data, blank_sample_names=None, reset_temperature=None)` | 6885 | Builds csu freeze count timeseries results. |
| `build_tamu_freeze_count_timeseries_results(parsed_timeseries, calibration_by_well=None, blank_sample_names=None, reset_temperature=None)` | 7077 | Builds tamu freeze count timeseries results. |
| `import_standard_temperature_csv(checked=False)` | 7215 | Imports standard temperature CSV. |
| `import_csu_is_dat(checked=False)` | 7378 | Imports csu is dat. |
| `import_tamu_linkam_xlsx(checked=False)` | 7478 | Imports tamu linkam xlsx. |

### Timeline

| Method | Line | Explanation |
| --- | --- | --- |
| `get_slider_handle_rect(slider)` | 4691 | Returns slider handle rect. |
| `push_timeline_marker_history(text, before_state)` | 6021 | Implements push timeline marker history. |
| `commit_slider_release_navigation()` | 6308 | Commits slider release navigation. |
| `update_keyframe_list(is_adding)` | 7779 | Updates keyframe list. |
| `keyframe_interpolation(frame_number)` | 7866 | Implements keyframe interpolation. |
| `zoom_slider_set_maximum()` | 7980 | Implements zoom slider set maximum. |
| `handle_preview_image_slider_value(index)` | 9072 | Handles preview image slider value. |
| `handle_image_slider_pressed()` | 9088 | Handles image slider pressed. |
| `handle_image_slider_released()` | 9099 | Handles image slider released. |
| `handle_committed_image_slider_value(index)` | 9149 | Handles committed image slider value. |
| `ensure_slider_window_contains_index(index)` | 9190 | Ensures slider window contains index. |
| `decreaseSliderValue()` | 9263 | Implements decrease slider value. |
| `increaseSliderValue()` | 9273 | Implements increase slider value. |
| `sync_zoom_slider_row_geometry()` | 9875 | Synchronizes zoom slider row geometry. |
| `reset_slider_stylesheet(theme=None)` | 9907 | Resets slider stylesheet. |
| `update_toggle_keyframe_button_icon(theme=None)` | 10014 | Updates toggle keyframe button icon. |

### UI shell

| Method | Line | Explanation |
| --- | --- | --- |
| `set_cursor_display_field_locked(field, locked)` | 870 | Sets cursor display field locked. |
| `refresh_cursor_selection_info(selected_items=None)` | 1107 | Refreshes cursor selection info. |
| `update_cursor_record_edit_state(selected_items=None)` | 1184 | Updates cursor record edit state. |
| `initUI()` | 2667 | Implements init UI. |
| `finalize_initial_dock_layout()` | 3159 | Implements finalize initial dock layout. |
| `enforce_initial_right_dock_tab()` | 3162 | Implements enforce initial right dock tab. |
| `current_preview_absolute_coordinates()` | 3171 | Returns the current preview absolute coordinates. |
| `clamp_preview_absolute_coordinates(x_value, y_value)` | 3183 | Implements clamp preview absolute coordinates. |
| `set_preview_absolute_coordinates(x_value, y_value)` | 3203 | Sets preview absolute coordinates. |
| `build_tool_options_panel()` | 3224 | Builds tool options panel. |
| `sync_tool_options_panel()` | 4119 | Synchronizes tool options panel. |
| `update_preview_shortcut_enabled_state()` | 4179 | Updates preview shortcut enabled state. |
| `sync_circle_tool_panel(radius, is_edit=False)` | 4245 | Synchronizes circle tool panel. |
| `sync_grid_tool_panel(is_edit=False)` | 4284 | Synchronizes grid tool panel. |
| `sync_active_preview_coordinate_controls()` | 4345 | Synchronizes active preview coordinate controls. |
| `handle_preview_offset_change(*_args)` | 4386 | Handles preview offset change. |
| `update_grid_preview_from_scene_pos(scene_pos, pin=False)` | 4443 | Updates grid preview from scene pos. |
| `get_grid_preview_definitions()` | 4446 | Returns grid preview definitions. |
| `focus_is_tool_options_editor()` | 4478 | Implements focus is tool options editor. |
| `focus_allows_preview_shortcut()` | 4514 | Implements focus allows preview shortcut. |
| `handle_preview_confirm_shortcut()` | 4536 | Handles preview confirm shortcut. |
| `handle_preview_cancel_shortcut()` | 4548 | Handles preview cancel shortcut. |
| `create_dock_widget(title, widget, object_name)` | 4651 | Creates dock widget. |
| `show_dock_widget(dock_widget)` | 4673 | Implements show dock widget. |
| `store_default_dock_state()` | 4682 | Implements store default dock state. |
| `reset_panel_layout()` | 4685 | Resets panel layout. |
| `set_active_image_panel(panel_name)` | 6262 | Sets active image panel. |
| `set_tools_highlight(tool_mode)` | 8019 | Sets tools highlight. |
| `cancel_unfinished_tool_workflow()` | 8070 | Drop any transient add/edit/grid interaction before a real tool switch. |
| `set_view_cursor_shape(cursor_shape)` | 8093 | Sets view cursor shape. |
| `apply_cursor_tool_ui()` | 8099 | Applies cursor tool UI. |
| `finalize_tool_mode_after_commit()` | 8122 | Clear transient override state without changing the active tool. |
| `apply_select_tool_ui(preserve_preview=False)` | 8128 | Applies select tool UI. |
| `apply_grid_tool_ui(preserve_preview=False)` | 8140 | Applies grid tool UI. |
| `apply_deselect_tool_ui()` | 8155 | Applies deselect tool UI. |
| `reset_cursor_tool(checked)` | 8166 | Resets cursor tool. |
| `panTool(checked)` | 8171 | Implements pan tool. |
| `imageEditTool(checked)` | 8195 | Implements image edit tool. |
| `selectTool(checked)` | 8200 | Implements select tool. |
| `gridTool(checked)` | 8206 | Implements grid tool. |
| `editTool(checked)` | 8240 | Implements edit tool. |
| `deselectTool(checked)` | 8255 | Implements deselect tool. |
| `remove_current_viewer_image()` | 8843 | Removes current viewer image. |
| `get_preview_frame_interval_ms()` | 9122 | Returns preview frame interval ms. |
| `flush_pending_preview_image()` | 9125 | Implements flush pending preview image. |
| `is_viewer_split_vertical()` | 9383 | Returns whether viewer split vertical. |
| `set_undo_status()` | 9551 | Sets undo status. |
| `set_redo_status()` | 9562 | Sets redo status. |
| `key_press_toolbutton_highlight(an_action)` | 9840 | Implements key press toolbutton highlight. |
| `reset_toolbar_stylesheet(theme=None)` | 9866 | Resets toolbar stylesheet. |
| `reset_status_bar_stylesheet(theme=None)` | 9921 | Resets status bar stylesheet. |
| `toolbar_icon(mode_folder, icon_name)` | 9945 | Implements toolbar icon. |
| `reset_toolbar_icon(theme=None)` | 9948 | Resets toolbar icon. |
| `update_viewer_mode_actions()` | 9975 | Updates viewer mode actions. |
| `update_viewer_orientation_toggle_action(mode_folder=None)` | 9981 | Updates viewer orientation toggle action. |
| `set_viewer_image_count(count)` | 9999 | Sets viewer image count. |
| `toggle_viewer_split_orientation()` | 10006 | Toggles viewer split orientation. |
