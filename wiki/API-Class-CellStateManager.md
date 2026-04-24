# API Class: `CellStateManager`

Persistent cell-state manager that owns stable cell bookkeeping and analysis synchronization.

## Source

- Module: [`icescopy_cell`](API-Module-icescopy-cell)
- File: `src/icescopy_cell.py`
- Line: `50`

## Inheritance

- Bases: `object`

## Purpose

Persistent cell-state manager that owns stable cell bookkeeping and analysis synchronization.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `main_window` | `__init__` | 54 | Stores main window. |

## Methods

### Computation and construction

| Method | Line | Explanation |
| --- | --- | --- |
| `recompute_next_cell_id(preserve_if_larger=True)` | 148 | Recomputes next cell ID. |

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(main_window)` | 53 | Initializes the instance. |
| `extract_cell_id_from_analysis_header(header_text)` | 56 | Implements extract cell ID from analysis header. |
| `extract_cell_id_from_label(label_text)` | 66 | Implements extract cell ID from label. |
| `ensure_cell_record(cell_id)` | 99 | Ensures cell record. |
| `ensure_cell_registry_matches_scene_cells()` | 110 | Ensures cell registry matches scene cells. |
| `_used_cell_ids()` | 121 | Implements used cell ids. |
| `_lowest_available_cell_id()` | 141 | Implements lowest available cell ID. |
| `allocate_cell_id()` | 159 | Allocates cell ID. |
| `cell_id_exists(cell_id, exclude_cell_id=None)` | 165 | Implements cell ID exists. |
| `rename_cell_id(old_cell_id, new_cell_id)` | 198 | Renames cell ID. |
| `prune_analysis_results_for_deleted_cells(deleted_cell_ids)` | 346 | Prunes analysis results for deleted cells. |

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `clear_cell_analysis()` | 286 | Clears cell analysis. |
| `sync_cell_analysis_from_results()` | 290 | Synchronizes cell analysis from results. |

### State serialization

| Method | Line | Explanation |
| --- | --- | --- |
| `serialize_cell_records()` | 75 | Serializes cell records. |
| `deserialize_cell_records(payload)` | 82 | Deserializes cell records. |
