# Cell System

A cell is the circular region whose brightness is measured. The code separates its identity and results, its geometry, and the interaction that edits it. This page is for contributors; drawing instructions are in [Annotation Workflow](Annotation-Workflow.md).

## State ownership

| State | Owner | Why it is separate |
| --- | --- | --- |
| Cell ID, sample ID, grayscale series, freeze events | [`CellRecord`](API-Class-CellRecord.md) in `cell_records_by_id` | Results survive graphics redraws. |
| Centers, radius, ID, interaction flags | [`CellSnapshot`](API-Class-CellSnapshot.md) or [`CellCircle`](API-Class-CellCircle.md) in current/keyframe geometry | Geometry can vary across frames without changing identity. |
| Selection, single/group edits, floating or pinned previews | [`CellEditController`](API-Class-CellEditController.md) | A preview is cancellable before commit. |
| Outline, label, hover and mouse handling | `CellCircle`, a Qt graphics item | Display objects are separate from analysis records. |
| Sample names and fields | [Sample catalog/schema](API-Module-icescopy-sample-metadata.md) | Many cells can refer to one sample ID. |

The window owns these collections. `CellStateManager` and `CellEditController` coordinate changes through it; neither is a second store of the complete session.

## Cell IDs connect geometry and results

Use the numeric cell ID to match geometry to a record or result column. Do not use scene-item order, selection order, or sample name. Sample names are editable, and several cells may belong to one sample.

`allocate_cell_id()` uses the lowest available non-negative ID, checking current geometry, keyframes, and records. Deleted IDs can be reused; IDs are not globally increasing across a project's lifetime.

[`rename_cell_id()`](API-Class-CellStateManager.md) rejects negative or conflicting IDs and updates geometry, records, grayscale headers, freeze labels, and controller references. Do not change only the record ID or the painted label. The Edit Cell action captures analysis as well as geometry so renaming can be undone consistently.

## Coordinates and keyframes

`circle_pixel_positions` is the center in original-image coordinates. `circle_positions` is the scene center. `circle_sizes` is the radius. A crop or rotated crop maps original pixels into the displayed/measured image; scene placement adds another offset. Use the window's coordinate conversions instead of subtracting a guessed origin.

[`keyframe_interpolation()`](../src/Icescopy.py#L8062) matches endpoint geometry by cell ID. Between two keyframes, matching cells have linearly interpolated centers and radii. A cell present at only one endpoint uses that endpoint's geometry. Outside the keyframe span, the nearest keyframe is used; without keyframes, current geometry is used.

Interpolation returns geometry for a frame. It does not rename cells, interpolate sample metadata, or calculate freeze events. The worker uses these positions to measure circular regions.

## Preview and commit

Single-cell and grid tools share a preview workflow:

1. A floating preview follows the pointer.
2. Pinning fixes the anchor while tool values are adjusted.
3. Apply adds or replaces real geometry and records one history operation.
4. Cancel discards the preview.

Grid settings include rows, columns, spacing, radius, angle, and anchor. Group editing uses selected IDs and a reference layout. [`PreviewAnchorHandle`](API-Class-PreviewAnchorHandle.md) moves the pinned layout without creating saved records.

The controller's [`apply_grid_add()`](../src/icescopy_cell_controller.py#L1193) demonstrates the commit pattern: capture before-state, allocate IDs, add geometry, synchronize keyframes/registry, refresh views, and push history. Use existing commit methods where possible. Rebuilding the scene alone does not complete a data edit.

## Results and manual freeze annotations

`sync_cell_analysis_from_results()` reconstructs per-cell result fields from grayscale and freeze tables. The matching pruning method removes obsolete columns/event rows after cell deletion. Missing measurements are `nan`, not zero brightness.

Manual freeze changes go through the window's `apply_manual_freeze_event_indices()` or batch method. They rebuild event rows, update flags/plots, and invalidate temperature/count results as needed. A timeline freeze flag is an event annotation, not an independent bookmark. Freeze-annotation history captures event changes separately from a full geometry edit.

Changed measurement geometry requires analysis to run again. A redraw or save is not recomputation. When adding an edit that changes scientific inputs, decide which results to invalidate and include the affected state in undo/redo. See [Architecture Overview](Architecture-Overview.md) for the dependency chain.

## Making a cell-related change

Trace the field through its owner, serialization, history, and editor before changing it:

- Display changes belong in graphics/plot code and should preserve measurements.
- Sample-field changes normally belong in the schema/catalog, not every circle.
- Geometry changes belong in the controller/current/keyframe path and need a result-invalidation decision.
- ID changes must update dependent references through `CellStateManager`.

Use [test_cell_controller.py](../tests/test_cell_controller.py) for preview/commit behavior, [test_roi_mean.py](../tests/test_roi_mean.py) for measurement, [test_sample_metadata.py](../tests/test_sample_metadata.py) for catalog fields, and [test_session_io.py](../tests/test_session_io.py) for persistence/history. Add focused cases for the invariant being changed. For interaction changes, also check selection, Apply, Cancel, undo/redo, navigation, and reopening in the native app.
