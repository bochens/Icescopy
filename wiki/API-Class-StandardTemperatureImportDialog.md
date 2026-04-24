# API Class: `StandardTemperatureImportDialog`

Standard Temperature Import Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `508`

## Inheritance

- Bases: `QDialog`

## Purpose

Standard Temperature Import Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `blank_sample_list` | `__init__` | 723 | Ordered list used for blank sample list. |
| `button_box` | `__init__` | 774 | Stores button box. |
| `file_path_edit` | `__init__` | 595 | Stores file path edit. |
| `frame_interval_spinbox` | `__init__` | 647 | Spin box widget for frame interval spinbox. |
| `generated_frame_interval_widget` | `__init__` | 660 | Qt widget reference for generated frame interval widget. |
| `generated_start_edit` | `__init__` | 642 | Stores generated start edit. |
| `image_form` | `__init__` | 567 | Stores image form. |
| `image_timestamp_source_combo` | `__init__` | 614 | Combo box widget for image timestamp source combo. |
| `image_timestamp_style_combo` | `__init__` | 628 | Combo box widget for image timestamp style combo. |
| `image_timestamp_test_label` | `__init__` | 663 | Label widget for image timestamp test label. |
| `main_window` | `__init__` | 526 | Stores main window. |
| `ok_button` | `__init__` | 775 | Button widget for ok button. |
| `reset_temperature_spinbox` | `__init__` | 735 | Spin box widget for reset temperature spinbox. |
| `scroll_area` | `__init__` | 537 | Stores scroll area. |
| `scroll_contents` | `__init__` | 543 | Stores scroll contents. |
| `scroll_contents_layout` | `__init__` | 544 | Stores scroll contents layout. |
| `temperature_celsius_radio` | `__init__` | 696 | Stores temperature celsius radio. |
| `temperature_form` | `__init__` | 583 | Stores temperature form. |
| `temperature_kelvin_radio` | `__init__` | 697 | Stores temperature kelvin radio. |
| `temperature_timestamp_style_combo` | `__init__` | 681 | Combo box widget for temperature timestamp style combo. |
| `temperature_unit_group` | `__init__` | 695 | Stores temperature unit group. |
| `use_image_timestamp_style_checkbox` | `__init__` | 674 | Stores use image timestamp style checkbox. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window, initial_path, sample_names, initial_reset_temperature=None, initial_blank_sample_names=None, initial_image_timestamp_source=IMAGE_TIMESTAMP_SOURCE_FILENAME, initial_image_timestamp_style=TIMESTAMP_STYLE_AUTO, initial_temperature_timestamp_style=TIMESTAMP_STYLE_AUTO, initial_use_image_timestamp_style=True, initial_generated_start_text='', initial_frame_interval_seconds=1.0, initial_temperature_unit=TEMPERATURE_UNIT_CELSIUS, parent=None)` | 509 | Initializes the instance. |
| `selected_image_timestamp_source()` | 804 | Returns selected image timestamp source. |
| `selected_image_timestamp_style()` | 809 | Returns selected image timestamp style. |
| `selected_temperature_timestamp_style()` | 812 | Returns selected temperature timestamp style. |
| `selected_temperature_unit()` | 819 | Returns selected temperature unit. |
| `evaluate_image_timestamp_test()` | 852 | Implements evaluate image timestamp test. |
| `accept()` | 887 | Accepts the dialog state and closes the widget. |
| `get_values()` | 929 | Returns values. |

### IO

| Method | Line | Explanation |
| --- | --- | --- |
| `browse_file()` | 785 | Implements browse file. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `refresh_dynamic_state()` | 826 | Refreshes dynamic state. |
