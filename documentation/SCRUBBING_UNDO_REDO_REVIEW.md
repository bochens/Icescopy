# Scrubbing + Undo/Redo Review

## Scope
- Verify recent undo/redo refactor did not break frame navigation behavior.
- Document what runs during scrubbing (`sliderMoved`) and after commit (`valueChanged`).
- Identify real overhead sources and concrete optimization opportunities.

## Current Undo/Redo Architecture
- `SessionSnapshotCommand`: full session state (used for full-session operations).
- `SessionImageListCommand`: image list + selection + analysis state (add/remove/clear images).
- `SessionLoadedImagesCommand`: loaded image set operations.
- `SessionSelectionCommand`: selection/keyframe/flag state only.
- `SessionDataCommand`: analysis tables + analysis paths only.
- `FrameNavigationCommand`: frame index only.

Relevant code:
- `/Users/C832577250/Project/Icescopy/icescopy_session.py`
- `/Users/C832577250/Project/Icescopy/Icescopy.py` (`push_*_history`, `restore_*_state`)

## Scrubbing Call Flow (While Dragging)
1. `handle_preview_image_slider_value(index)` stores pending preview index.
2. Single-shot timer triggers `flush_pending_preview_image()`.
3. `flush_pending_preview_image()` calls `updateImage(index, preview=True)`.
4. `updateImage(..., preview=True)` does:
   - image/pixmap lookup and scene pixmap update (`update_display_pixmaps`)
   - selection interpolation and redraw (`interpolate_and_displayMarkedRegions`)
   - optional edit-preview rebase/update
   - updates plot current-frame line (`update_grayscale_plot_current_frame`)
   - does **not** call `finalize_frame_update` in preview mode

## Commit Call Flow (After Slider Release / value commit)
1. `handle_committed_image_slider_value(index)` runs.
2. Calls `updateImage(index, preview=False)` if frame changed.
3. `updateImage(..., preview=False)` then calls `finalize_frame_update(index)`.
4. `finalize_frame_update(index)` updates:
   - slider value/window sync
   - image label/textbox
   - button states
   - keyframe/flag icons
   - image list selection sync
5. If frame changed and not history-restoring, pushes `FrameNavigationCommand`.

## Undo/Redo Frame-Navigation Behavior
- Undo/redo frame commands call `restore_navigation_index(index)`.
- `restore_navigation_index` calls `updateImage(target_index, preview=False)`.
- `finalize_frame_update` now syncs the slider handle/window to the restored frame when slider is not actively dragged.

## Fixes Applied In This Pass
1. **Slider did not reflect undo/redo frame restore**
   - Fixed by syncing slider value/window in `finalize_frame_update`.
   - This ensures command-based frame restore updates UI handle position.

2. **Selection undo could reset slider zoom window**
   - `restore_selection_state` now preserves current slider window and only adjusts window if needed to include target index.

3. **Stale navigation-start could leak across drags**
   - If slider drag ended without a committed frame change, pending navigation start could remain and contaminate the next change log/history.
   - Fixed by clearing pending preview/navigation state on slider release when no committed frame change occurred.

4. **Release-time false cleanup when preview already matched final frame**
   - A real drag could be misclassified as "no change" if preview had already reached the release frame.
   - Fix: release cleanup now compares against drag start index, not current previewed `image_index`.

## Overhead Sources During Scrubbing (Biggest First)
1. **Selection interpolation + scene sync per preview tick**
   - `keyframe_interpolation()` allocates/copies selection objects each frame.
   - `_sync_scene_items_from_models()` scans/sorts scene items every frame.
   - Cost grows with selection count.

2. **Viewer context pixmap churn**
   - `update_display_pixmaps()` removes/recreates context pixmap/placeholder items on each frame.
   - In 2/3-view mode this adds scene churn every tick.

3. **Scene-rect recompute every frame**
   - Union of active/context/placeholder bounds on each update.

4. **Image list sync on commit**
   - `sync_image_list_selection()` may scroll list if target row not visible.
   - Not preview-costly, but commit can still feel heavy on long lists.

5. **Any active grid/edit preview rebase**
   - Rebuilds preview overlays when pinned edit/grid workflows are active.

## What Is No Longer the Main Scrubbing Overhead
- Frame navigation undo/redo no longer deep-copies full session state.
- Navigation history is now index-only (`FrameNavigationCommand`).

## Suggested Next Optimization Pass (High ROI)
1. Cache current `CellCircle` scene-item list in controller (avoid `scene.items()` scan/sort each frame).
2. Add fast interpolation path that updates numeric geometry in reusable objects (avoid per-frame deep object recreation).
3. Reuse context `QGraphicsPixmapItem`s in 2/3-view mode instead of remove/add every frame.
4. Update scene rect only when layout mode changes or when context slots change, not every preview tick.
5. Keep plot updates at `setPos` only during preview (already mostly true) and defer non-essential plot work to commit.

## Suggested Instrumentation
- Add timing probes around:
  - `update_display_pixmaps`
  - `keyframe_interpolation`
  - `_sync_scene_items_from_models`
  - `update_grayscale_plot_current_frame`
  - `finalize_frame_update`
- Log p50/p95 per block over ~200 scrub updates to identify dominant block on your dataset.

## Notes
- This review is static/code-path based in the current workspace; no live GUI benchmark is included here.
