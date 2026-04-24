# API Class: `SampleCatalogTreeDelegate`

Sample Catalog Tree Delegate class.

## Source

- Module: [`Icescopy`](API-Module-Icescopy)
- File: `src/Icescopy.py`
- Line: `180`

## Inheritance

- Bases: `QStyledItemDelegate`

## Purpose

Sample Catalog Tree Delegate class.

## Class Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `SAMPLE_ID_ROLE` | 181 | Stores sample ID role. |
| `FIELD_NAME_ROLE` | 182 | Stores field name role. |
| `EDITABLE_ROLE` | 183 | Stores editable role. |
| `NUMERIC_FIELDS` | 184 | Stores numeric fields. |

## Methods

### Computation and construction

| Method | Line | Explanation |
| --- | --- | --- |
| `createEditor(parent, option, index)` | 192 | Implements create editor. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `setEditorData(editor, index)` | 239 | Implements set editor data. |
| `setModelData(editor, model, index)` | 263 | Implements set model data. |

### Interaction and commands

| Method | Line | Explanation |
| --- | --- | --- |
| `commit_combo_data(*_args)` | 229 | Commits combo data. |
| `commit_line_edit_data()` | 234 | Commits line edit data. |
