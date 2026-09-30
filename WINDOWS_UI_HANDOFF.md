# Temporary Windows layout handoff

This file is for the PC Codex working on Icescopy after the Mac layout changes.
Windows appearance has **not** been verified by the Mac work.

## Start from the shared changes

- Fetch and inspect `codex/synchronized-image-panels`; the open draft is [PR #5](https://github.com/bochens/Icescopy/pull/5).
- Check local changes before switching or pulling. Preserve user work and make a Git checkpoint before edits.
- Start from the latest pushed branch commit containing this handoff, including the Mac checkbox-spacing and event-row alignment fixes; do not start from an older release.
- Inspect `build_cells_panel`, `update_freeze_event_button_appearance`, and `sync_zoom_slider_row_geometry` in `src/Icescopy.py`.
- Inspect `FreezeEventButton` and `FreezeEventSelector` in `src/icescopy_event_navigation.py`, plus the button styles in `src/icescopy_stylesheet.py`.
- The Mac correction uses `timeline=False` for the Cells buttons, removing the timeline's downward margin beside the event dropdown. Preserve that correction.
- Windows startup selects Qt's `Fusion` style in `main()`. Run the real Windows entry point when checking appearance; a test-created window may use a different style.

## Check on Windows

- Keep **Auto-center** and **Show freeze frame** on one line, with a visible gap between them. The Mac change uses `navigation_controls.setSpacing(12)`; Qt scales these layout units with the display setting.
- Keep the previous-event button, event dropdown, and next-event button together on one line below the checkboxes.
- Align the visible button centers with the dropdown's visible center, not just their outer widget rectangles.
- Keep timeline event buttons in the existing timeline row, aligned with the ordinary frame arrows. Do not add another row.
- Check narrow and wide Cells docks, both themes, enabled and disabled buttons, keyboard focus, and an open event dropdown.
- Check Windows display scaling at 100%, 125%, 150%, and 200% where available, plus the user's normal font/text scaling. Record any settings that could not be checked.
- Use several events, a long frame number, a cell without an event, and a multiple-cell selection to expose clipping and unwanted row-height changes.
- Make the smallest change supported by a visible problem. Prefer Qt layout/style measurements; avoid a global offset that breaks Mac alignment.
- Capture the app only, without the computer-use cursor. Use synthetic examples or a new unsaved session; never publish private data or overwrite saved sessions/results.

## Preserve behavior and verify

- These are layout changes. Keep list-only automatic navigation, re-click behavior, remembered cycles, and multiple-selection behavior unchanged.
- Timeline event arrows still visit the nearest earlier/later event for selected cells, or all cells when none are selected; they do not auto-center or change the chosen Cells cycle.
- Run the existing comparison checks with the project's Python environment: `python -m unittest discover -s tests -p test_comparison_viewer.py`.
- If changing timeline sizing or toolbar state, also run `test_toolbar_modes.py` using the same discovery command. Broaden checks only when the edits require it.
- Use the real Windows app to verify appearance and interaction; passing automated or offscreen checks alone does not establish native alignment.
- Run `git diff --check`. If public signatures change, run `python tools/update_api_reference.py`, then `python tools/update_api_reference.py --check` and `python tools/wiki_docs.py check`.
- Build on Windows with `Icescopy.windows.spec` and follow `packaging/windows/README.md`. Give build, distribution, configuration, and validation outputs new paths; preserve older builds.
- Verify the packaged app's controls too. Record the source commit, Windows version, display scaling, screenshots, checks, and any remaining limitations in the PR.

## Push and remove this handoff

- Review and commit only the intended Windows-compatible fixes, then push the feature branch and update PR #5 with the Windows evidence.
- After checks are complete, **delete this tracked handoff file in a normal deletion commit and push that commit before merging to `main`**.
- Ensure the final version of the PR and `main` contain the fixes but not `WINDOWS_UI_HANDOFF.md`. If it already reached `main`, remove it there through the normal review/merge workflow too.
- Do not rewrite published history merely to erase this handoff. Preserve the readable commit history and remove the file from the final tree.
- Merge only after the combined Mac/Windows changes are ready and applicable checks pass. Do not replace a user's running installation or publish a release as part of a layout-only check.
