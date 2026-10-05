# Icescopy INP-toolkit client handoff

Current goal: use native grid-range selection consistently; prepare the next
Icescopy release after client verification. Do not edit INP-toolkit here.

## Verified toolkit contract

- Installed CLI: `/Applications/INP-toolkit/inptk`, source `84ffe3e`, version 0.4.3.
- Sample limits select calculation targets after counts have been selected.
- Original source rows supplying retained grid states remain unchanged.
- Full and explicitly selecting the full useful grid span are equivalent.
- MLE retains observations outside useful reporting support as fit constraints.
- `settings.resolved_temperature_ranges_C` is keyed by curve, then input.
- Each input reports `run_id`, `cycle_id`, `full_range_C`, `selected_range_C`,
  and `calculation_limits_C`. A missing useful span is null.
- `source_observations` includes selected frozen/total counts and source identity.
- Average suggestions use the same grid domain.

## Client decisions

- Forward only explicit sample limits; Full sends an empty range map.
- The configured count grid stays 0 to −35 °C in 0.5 °C steps by default.
- Display sample Full endpoints from native `full_range_C`, not finite estimates.
- After calculation, sample guides use these same native endpoints in all plots.
- Before calculation, raw views can show acquisition extents. Concentration
  never substitutes original observations or an outdated grid for native limits.
- A warm-only drag changes only the warm choice, matching a numeric edit.
- Combined cuts never alter direct individual reference calculations or exports.
- Blank limits remain shared observation limits, editable only in raw views.
- First-blank-freeze gating locks the warm blank control; the CLI enforces it.

## Files and checks

- `src/icescopy_inptk_state.py`: CLI arguments; no implicit sample cutoff.
- `src/icescopy_inptk_panel.py`: native Full guides and range editing.
- `tests/test_inptk.py`: real CLI checks for grid equivalence and UI controls.
- `/tmp/icescopy-inp-ui-review/reproduce-toolkit-grid-cut.py`: original CLI case.
- `/tmp/icescopy-inp-ui-review/audit-warm-only-range.py`: read-only M1 check.
- Use Icescopy conda Python, `PYTHONPATH=src:tests`, `QT_QPA_PLATFORM=offscreen`,
  and `INPTK_TEST_EXECUTABLE=/Applications/INP-toolkit/inptk`.
- Native comparison passed for MLE/Average and latest/max/window selection:
  same full points, concentrations, uncertainty and sources; cold states retained.
- M1 warm text/tag comparison retained −28.5 °C and preserved the saved recording.

Client verification passed: 12 choice checks and seven real-CLI integration
checks, plus the read-only M1 comparison. Reviewed diff and checked whitespace.
Next: push/merge and release/install when requested. Preview `05daa4a` does not
contain these latest client edits.
