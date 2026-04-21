# Tool Options Layout Review

## Scope

This document lists the parameters and code paths that actually affect the `Tool Options` panel layout in `/Users/C832577250/Project/Icescopy/src/Icescopy.py`.

It is limited to the active layout path for:

- `Tool Options` outer panel
- `ToolOptionsFormPage`
- `ToolOptionsInfoPage`
- current `cursor`, `grid`, `single circle`, `edit circle`, and `edit grid` tool pages

It also calls out parameters that look relevant but currently do **not** affect the active layout.

## Active Layout Pipeline

The active layout chain is:

1. `build_tool_options_panel()`
2. `QStackedWidget` page selection
3. either `ToolOptionsInfoPage` or `ToolOptionsFormPage`
4. per-row construction through `ToolOptionsFormPage.add_row()`
5. button row construction through `ToolOptionsFormPage.add_action_row()` or the cursor-specific single-button row

Current page usage:

- `none` / `edit-choose` uses `ToolOptionsInfoPage`
- `cursor` uses `ToolOptionsFormPage`
- `single circle` uses `ToolOptionsFormPage`
- `grid` uses `ToolOptionsFormPage`
- `edit circle` uses `ToolOptionsFormPage`
- `edit grid` uses `ToolOptionsFormPage`

## Parameters That Actually Affect Layout

### 1. Outer panel width and padding

These control the dock panel size and the blank padding around the inner stacked pages.

- `TOOL_OPTIONS_PANEL_DEFAULT_WIDTH = TOOL_OPTIONS_CONTENT_WIDTH + 20`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:58`
  - applied at: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1722`
  - effect:
    - controls the minimum width of the whole `Tool Options` panel
    - does **not** change row geometry inside a form page

- `layout.setContentsMargins(10, 10, 10, 10)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1720`
  - effect:
    - outer padding between the panel border and the title/stack

- `layout.setSpacing(8)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1721`
  - effect:
    - vertical gap between outer panel children
    - mainly title to stacked-page spacing

### 2. Inner column width and centering

These control how the actual form content is centered inside the page.

- `TOOL_OPTIONS_CONTENT_WIDTH = 252`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:52`
  - consumed by `ToolOptionsFormPage` at:
    - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:105`
    - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:123`
  - effect:
    - fixed width of the centered content column
    - this is the most important width knob for row layout

- `self.root_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:120`
  - effect:
    - horizontally centers the inner content column inside the page

- `self.column_widget.setFixedWidth(self.content_width)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:123`
  - effect:
    - hard-locks the centered form column to `TOOL_OPTIONS_CONTENT_WIDTH`

### 3. Vertical spacing between rows

- `self.column_layout.setSpacing(10)`
  - source:
    - `ToolOptionsInfoPage`: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:84`
    - `ToolOptionsFormPage`: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:126`
  - effect:
    - vertical gap between rows, hints, and action rows inside a page

### 4. Per-row horizontal geometry

These determine the internal row shape.

- `TOOL_OPTIONS_LABEL_WIDTH = 84`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:55`
  - applied at: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:144`
  - effect:
    - width of the left label column

- `TOOL_OPTIONS_FIELD_WIDTH = 96`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:56`
  - applied at: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:147`
  - effect:
    - width of the editor control area

- `TOOL_OPTIONS_SHORTCUT_WIDTH = 56`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:57`
  - applied at: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:153`
  - effect:
    - width of the right shortcut/hint column
    - even for rows without visible shortcut text, this still reserves space

- `row_layout.setSpacing(8)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:140`
  - effect:
    - horizontal gap between:
      - label and field
      - field and shortcut column

Current row width math:

- label: `84`
- field: `96`
- shortcut: `56`
- horizontal spacing: `8 + 8`
- total: `84 + 96 + 56 + 16 = 252`

That exactly matches `TOOL_OPTIONS_CONTENT_WIDTH`.

### 5. Action row button sizing

- `TOOL_OPTIONS_BUTTON_SPACING = 8`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:53`
  - used at:
    - grid/add/edit action rows: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:167`, `/Users/C832577250/Project/Icescopy/src/Icescopy.py:171`
    - cursor `New Sample` row: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1774`
  - effect:
    - spacing between action buttons

- `button_width = int((self.content_width - (2 * TOOL_OPTIONS_BUTTON_SPACING)) / 3)`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:167`
  - effect:
    - width of `Apply`, `Float`, `Cancel`
    - current value: `int((252 - 16) / 3) = 78`

- cursor `New Sample` width:
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1777`
  - effect:
    - currently also `78`
    - centered by stretch spacers at lines 1780-1782

### 6. Control height

- panel stylesheet:
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1974-1981`
  - effect:
    - sets `min-height: 24px` for:
      - `QSpinBox`
      - `QPushButton`
      - `QLineEdit`
      - `QComboBox`
      - `QDoubleSpinBox`

- cursor line edits:
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1751`
  - effect:
    - explicit fixed height `24`

- cursor sample combo:
  - source:
    - outer combo: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1767`
    - inner line edit: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1766`
  - effect:
    - explicit fixed height `24`

## Parameters That Change Content But Not Core Geometry

These do not change the row geometry itself, but they change what the user sees.

### 1. Widget class

This is one of the biggest visual differences and it is **not** a simple width constant.

- cursor display rows use `QLineEdit`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1749`

- cursor sample picker uses `QComboBox`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1760`

- grid numeric rows use `QSpinBox` / `QDoubleSpinBox`
  - source examples:
    - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1855`
    - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1861`

Even with the same `TOOL_OPTIONS_FIELD_WIDTH` and the same `24px` height:

- a `QLineEdit` shows almost all of that width as white entry area
- a `QComboBox` uses part of that width for the arrow button and frame
- a `QSpinBox` / `QDoubleSpinBox` uses part of that width for the spin buttons

So equal width constants do **not** mean equal visible white-box width.

### 2. Combo content text

- `refresh_cursor_sample_combo_catalog()` builds the displayed item text
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:576-589`

Current behavior:

- empty sample shows `None`
- sample items show only the sample ID text

This affects clipping and perceived width, but not the underlying geometry.

### 3. Read-only state helper

- `set_cursor_display_field_locked()`
  - source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:619-624`

Current effect:

- sets `readOnly`
- sets focus policy
- does **not** change width or spacing

## Parameters That Look Relevant But Currently Do Not Affect Active Layout

### 1. `SIDE_PANEL_DEFAULT_WIDTH`

- source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:51`

This is **not** the active `Tool Options` width knob anymore.

The `Tool Options` panel uses:

- `TOOL_OPTIONS_PANEL_DEFAULT_WIDTH`
  - applied at `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1722`

So changing `SIDE_PANEL_DEFAULT_WIDTH` will not fix `Tool Options`.

### 2. `TOOL_OPTIONS_FORM_WIDTH`

- source: `/Users/C832577250/Project/Icescopy/src/Icescopy.py:54`
- stored in `ToolOptionsFormPage.__init__` at `/Users/C832577250/Project/Icescopy/src/Icescopy.py:111`

Current status:

- it is stored
- it is never used afterward

So changing `TOOL_OPTIONS_FORM_WIDTH` currently has **no effect** on the active layout.

### 3. Old helper builders

- `build_tool_action_row()`
  - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1668`
- `build_tool_option_row()`
  - `/Users/C832577250/Project/Icescopy/src/Icescopy.py:1691`

These are not referenced anywhere in the file right now.

So changing them does **nothing** for the current `Tool Options` UI.

## Exact Difference Between "Panel Width" and "Row Width"

This has been the main source of confusion.

### Panel width

Controlled by:

- `TOOL_OPTIONS_PANEL_DEFAULT_WIDTH`
- outer panel margins

This affects:

- how much blank space exists around the centered form column

It does **not** change:

- label width
- field width
- shortcut width
- button width

### Row width

Controlled by:

- `TOOL_OPTIONS_CONTENT_WIDTH`
- `TOOL_OPTIONS_LABEL_WIDTH`
- `TOOL_OPTIONS_FIELD_WIDTH`
- `TOOL_OPTIONS_SHORTCUT_WIDTH`
- row spacing `8`

This affects:

- the actual shape of the form rows
- whether the white boxes look narrow or wide
- whether labels and fields feel cramped or balanced

## Current Source of the Remaining Visual Differences

As of this review, the remaining visual differences are mainly:

1. `QLineEdit` vs `QComboBox` vs `QSpinBox` drawing differences
2. cursor page has a single centered `New Sample` button, while grid has a 3-button action row
3. cursor page rows have no shortcut text, but the shortcut column is still reserved
4. the cursor hint text is different content and wraps differently than the grid hint text

So if the goal is "make them look the same", the next decision must be explicit:

- either make the `Sample ID` control look like a true text field through explicit combo styling
- or accept native combo appearance and only match geometry

## Check Process Before Changing Layout Again

This is the process that should be followed before touching layout:

1. Confirm the active page class.
   - `ToolOptionsInfoPage` or `ToolOptionsFormPage`
   - never change dead helpers first

2. Confirm whether the issue is:
   - outer panel width
   - centered column width
   - per-row geometry
   - control class appearance
   - button width
   - hint wrapping

3. Change exactly one active knob.
   - panel width: `TOOL_OPTIONS_PANEL_DEFAULT_WIDTH`
   - row width: `TOOL_OPTIONS_CONTENT_WIDTH`
   - label width: `TOOL_OPTIONS_LABEL_WIDTH`
   - field width: `TOOL_OPTIONS_FIELD_WIDTH`
   - shortcut width: `TOOL_OPTIONS_SHORTCUT_WIDTH`
   - row spacing: `row_layout.setSpacing(8)` or `column_layout.setSpacing(10)`

4. Do not change:
   - `SIDE_PANEL_DEFAULT_WIDTH` for `Tool Options`
   - `TOOL_OPTIONS_FORM_WIDTH`
   - dead helper methods
   unless the active path is changed first

5. After each change, compare:
   - grid row
   - cursor row
   - grid button row
   - cursor sample row
   - grid hint block
   - cursor hint block

## Review Passes

### Review 1

Checked constants and outer panel wiring:

- confirmed active width constant for `Tool Options` is `TOOL_OPTIONS_PANEL_DEFAULT_WIDTH`
- confirmed `SIDE_PANEL_DEFAULT_WIDTH` is not active for `Tool Options`

### Review 2

Checked active form-page path:

- confirmed `cursor` now uses `ToolOptionsFormPage`
- confirmed `grid` uses the same page class and row builder

### Review 3

Checked misleading and dead knobs:

- confirmed `TOOL_OPTIONS_FORM_WIDTH` is currently unused
- confirmed old helper builders are not active
- confirmed widget class difference still matters even when heights and widths match numerically
