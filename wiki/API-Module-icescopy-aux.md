# API Module: `icescopy_aux`

Auxiliary Qt widgets, dialogs, and the image-analysis worker thread.

## Source

- File: `src/icescopy_aux.py`

## Classes

| Class | Purpose | Page |
| --- | --- | --- |
| `ColorPreferenceButton` | Color Preference Button class. | [ColorPreferenceButton](API-Class-ColorPreferenceButton) |
| `CustomGraphicsView` | Custom Graphics View class. | [CustomGraphicsView](API-Class-CustomGraphicsView) |
| `Image_analysis_thread` | Image analysis thread class. | [Image_analysis_thread](API-Class-Image-analysis-thread) |
| `AboutDialog` | About Dialog class. | [AboutDialog](API-Class-AboutDialog) |
| `PreferencesDialog` | Dialog for editing persisted application preferences. | [PreferencesDialog](API-Class-PreferencesDialog) |
| `SortImagesDialog` | Dialog for choosing the image sort mode and previewing ordering. | [SortImagesDialog](API-Class-SortImagesDialog) |

## Module Variables

| Variable | Line | Explanation |
| --- | --- | --- |
| `DEFAULT_VISUAL_COLORS` | 57 | Default value for visual colors. |
| `PLOT_PALETTE_LABELS` | 67 | Stores plot palette labels. |
| `GRID_CELL_ID_DIRECTION_LABELS` | 74 | Stores grid cell ID direction labels. |
| `DEFAULT_PREFERENCE_VALUES` | 79 | Default value for preference values. |
| `module_dir` | 119 | Stores module dir. |
| `resources_dir` | 120 | Stores resources dir. |

## Top-level Functions

| Function | Line | Explanation |
| --- | --- | --- |
| `create_circular_mask(h, w, center, radius)` | 175 | Creates circular mask. |
