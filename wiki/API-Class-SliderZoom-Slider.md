# API Class: `SliderZoom_Slider`

Secondary slider used to control timeline resolution and zoom granularity.

## Source

- Module: [`icescopy_frameslider`](API-Module-icescopy-frameslider)
- File: `src/icescopy_frameslider.py`
- Line: `505`

## Inheritance

- Bases: `QSlider`

## Purpose

Secondary slider used to control timeline resolution and zoom granularity.

## Instance Attributes

| Attribute | First assigned in | Line | Explanation |
| --- | --- | --- | --- |
| `main_window` | `__init__` | 508 | Stores main window. |

## Methods

### General

| Method | Line | Explanation |
| --- | --- | --- |
| `__init__(orientation=Qt.Horizontal, main_window=None, parent=None)` | 506 | Initializes the instance. |

### Qt event handlers

| Method | Line | Explanation |
| --- | --- | --- |
| `mousePressEvent(event)` | 519 | Qt mouse-press event handler. |
