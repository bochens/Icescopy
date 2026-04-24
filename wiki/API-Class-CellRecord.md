# API Class: `CellRecord`

Persistent per-cell metadata and analysis payload.

## Source

- Module: [`icescopy_cell`](API-Module-icescopy-cell)
- File: `src/icescopy_cell.py`
- Line: `12`

## Inheritance

- Bases: `object`

## Purpose

Persistent per-cell metadata and analysis payload.

## Dataclass Fields

| Field | Line | Explanation |
| --- | --- | --- |
| `cell_id` | 18 | Stores cell ID. |
| `sample_id` | 19 | Stores sample ID. |
| `grayscale_timeseries` | 20 | Stores grayscale timeseries. |
| `freeze_event_indices` | 21 | Collection of indices for freeze event indices. |
| `freeze_rows` | 22 | Row-oriented data for freeze rows. |

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `freeze_event_indices` | `clear_analysis` | 26 | Collection of indices for freeze event indices. |
| `freeze_rows` | `clear_analysis` | 27 | Row-oriented data for freeze rows. |
| `grayscale_timeseries` | `clear_analysis` | 25 | Stores grayscale timeseries. |

## Methods

### Refresh and sync

| Method | Line | Explanation |
| --- | --- | --- |
| `clear_analysis()` | 24 | Clears analysis. |

### State serialization

| Method | Line | Explanation |
| --- | --- | --- |
| `to_dict()` | 29 | Implements to dict. |
| `from_dict(payload)` | 39 | Implements from dict. |
