# Cell System

This page explains the difference between the three files that define the cell subsystem.

## The short answer

- `src/icescopy_cell.py` = what a cell is
- `src/icescopy_cell_controller.py` = how cell editing works
- `src/icescopy_cell_items.py` = how a cell is drawn and clicked

These files solve different problems and should stay separate.

## `src/icescopy_cell.py`

This file is the persistent data layer.

Main classes:

- `CellRecord`
- `CellStateManager`

It owns:

- stable cell IDs
- sample IDs
- grayscale timeseries
- freeze event indices
- freeze rows
- serialization and deserialization
- rename and allocation rules

This is the canonical data model for a cell.

## `src/icescopy_cell_controller.py`

This file is the edit workflow layer.

Main classes:

- `PreviewAnchorHandle`
- `CellEditController`

It owns:

- edit-mode behavior
- selection coordination
- group editing
- preview-handle behavior
- scene synchronization from model geometry

It does not own the long-term meaning of a cell.
It owns how editing should behave right now.

## `src/icescopy_cell_items.py`

This file is the scene item layer.

Main classes:

- `CellSnapshot`
- `CellCircle`

It owns:

- ellipse painting
- label painting
- hover state
- pressed state
- item-level mouse handling

These objects are disposable scene objects.
They can be rebuilt repeatedly as the displayed frame changes.

## Why this split is correct

Without this split, one file would have to mix:

- saved cell meaning
- edit workflow rules
- low-level graphics item behavior

That usually leads to brittle code and accidental coupling.

The current split is defensible because it follows the actual responsibilities:

- data
- controller
- view item
