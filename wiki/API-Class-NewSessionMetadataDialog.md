# API Class: `NewSessionMetadataDialog`

New Session Metadata Dialog class.

## Source

- Module: [`icescopy_dialogs`](API-Module-icescopy-dialogs)
- File: `src/icescopy_dialogs.py`
- Line: `72`

## Inheritance

- Bases: `QDialog`

## Purpose

New Session Metadata Dialog class.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `date_edit` | `__init__` | 122 | Stores date edit. |
| `institution_edit` | `__init__` | 98 | Stores institution edit. |
| `project_name_edit` | `__init__` | 96 | Stores project name edit. |
| `user_name_edit` | `__init__` | 97 | Stores user name edit. |
| `well_volume_edit` | `__init__` | 99 | Stores well volume edit. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(parent=None, metadata=None, *, window_title='New Session')` | 73 | Initializes the instance. |
| `accept()` | 139 | Accepts the dialog state and closes the widget. |
| `get_metadata()` | 153 | Returns metadata. |
