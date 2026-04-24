# API Class: `ToolOptionsFormPage`

Tool Options Form Page class.

## Source

- Module: [`icescopy_tool_options`](API-Module-icescopy-tool-options)
- File: `src/icescopy_tool_options.py`
- Line: `97`

## Inheritance

- Bases: `QWidget`

## Purpose

Tool Options Form Page class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `apply_button` | `__init__` | 139 | Button widget for apply button. |
| `cancel_button` | `__init__` | 141 | Button widget for cancel button. |
| `column_layout` | `__init__` | 130 | Stores column layout. |
| `column_widget` | `__init__` | 128 | Qt widget reference for column widget. |
| `content_width` | `__init__` | 108 | Geometry value for content width. |
| `field_width` | `__init__` | 110 | Geometry value for field width. |
| `float_button` | `__init__` | 140 | Button widget for float button. |
| `hint_label` | `__init__` | 138 | Label widget for hint label. |
| `label_width` | `__init__` | 109 | Geometry value for label width. |
| `native_button_height` | `__init__` | 143 | Geometry value for native button height. |
| `native_combo_height` | `__init__` | 142 | Geometry value for native combo height. |
| `root_layout` | `__init__` | 113 | Stores root layout. |
| `scroll_area` | `__init__` | 116 | Stores scroll area. |
| `scroll_contents` | `__init__` | 122 | Stores scroll contents. |
| `scroll_contents_layout` | `__init__` | 123 | Stores scroll contents layout. |
| `shortcut_width` | `__init__` | 111 | Geometry value for shortcut width. |

## Methods

### Computation and construction

| Method | Line | Explanation |
| --- | --- | --- |
| `create_combo_box(*, index_handler=None)` | 168 | Creates combo box. |
| `create_spin_box(minimum, maximum, *, step=1, value_handler=None)` | 180 | Creates spin box. |
| `create_double_spin_box(minimum, maximum, *, decimals=1, step=0.5, value_handler=None)` | 189 | Creates double spin box. |
| `_create_button(text, parent, handler)` | 207 | Implements create button. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None, *, content_width=TOOL_OPTIONS_CONTENT_WIDTH, label_width=TOOL_OPTIONS_LABEL_WIDTH, field_width=TOOL_OPTIONS_FIELD_WIDTH, shortcut_width=TOOL_OPTIONS_SHORTCUT_WIDTH)` | 98 | Initializes the instance. |
| `_probe_native_combo_height()` | 145 | Implements probe native combo height. |
| `_probe_native_button_height()` | 151 | Implements probe native button height. |
| `standard_button_width()` | 157 | Implements standard button width. |
| `_configure_control(control)` | 160 | Implements configure control. |
| `add_row(label_text, editor, shortcut_text='')` | 214 | Implements add row. |
| `add_row_with_button(label_text, editor, button_text, handler)` | 237 | Implements add row with button. |
| `add_section_label(text)` | 262 | Implements add section label. |
| `add_separator()` | 269 | Implements add separator. |
| `add_value_row(label_text, value_text='-')` | 278 | Implements add value row. |
| `add_hint(text)` | 301 | Implements add hint. |
| `add_action_row(apply_handler, float_handler, cancel_handler)` | 308 | Implements add action row. |
| `add_centered_button_row(button_text, handler)` | 326 | Implements add centered button row. |
| `add_bottom_stretch()` | 341 | Implements add bottom stretch. |
