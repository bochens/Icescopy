# Frame Slider Implementation Notes (NLE-style)

## Source-backed behavior pattern

1. **Separate drag lifecycle signals**
- Qt documents that:
  - `sliderPressed()` marks drag start,
  - `sliderMoved()` is emitted while dragging (even with tracking off),
  - `sliderReleased()` marks drag end,
  - `valueChanged()` emission during drag depends on `tracking`.
- Reference: Qt `QAbstractSlider` docs.

2. **Preview movement should be smooth and deterministic**
- Premiere docs describe scrubbing where the playhead follows gesture movement with a direct mapping, including a 1:1 scrub relationship in monitor/thumb contexts.
- Reference: Adobe Premiere touch/gesture docs.

3. **Preview cursor vs committed playhead is a valid model**
- Final Cut explicitly separates skimmer preview from playhead position.
- Even if we keep a single visible playhead in Icescopy, this pattern supports robust “preview vs commit” state internally.
- Reference: Apple Final Cut skimmer docs.

## Practical implementation rules

1. On `sliderPressed`, capture a stable drag origin (`drag_start_index`).
2. On `sliderMoved`, update preview only (no history push).
3. On `valueChanged` (commit), push exactly one history entry from `drag_start_index -> committed_index`.
4. On `sliderReleased`, clear pending state **only** if no actual move occurred from drag origin.
5. Keep heavy work outside high-frequency drag path where possible.

## Why this matters

- If cleanup is based on current preview frame instead of drag origin, a real drag can be misclassified as “no-change” when preview already caught up to release frame.
- That causes wrong `before -> after` history/log entries and unstable undo behavior.

## References

- Qt `QAbstractSlider`: https://doc.qt.io/qt-6/qabstractslider.html
- Final Cut skimmer: https://support.apple.com/guide/final-cut-pro/skimmer-ver8e3f32f0/mac
- Premiere Source/Program monitor overview: https://helpx.adobe.com/ph_en/premiere/desktop/get-started/source-and-program-monitor-adjustments/about-source-monitor-and-program-monitor.html
- Premiere touch/gesture scrub behavior: https://helpx.adobe.com/premiere/desktop/get-started/use-touch-and-gesture-controls/control-premiere-through-touch-and-gesture-in-microsoft-surface-pro-and-windows.html
