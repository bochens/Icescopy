# INP-toolkit client contract: water-blank controls

Scientific calculations remain in the external INP-toolkit CLI.
Implemented toolkit source: `fe3d3b7` (package version 0.4.3).
Query capabilities rather than relying on the displayed version.

## CLI interface

Both `analyze` and `suggest-ranges` advertise these options:

- `--water-blank-after-first-freeze`: boolean, off by default.
- `--water-blank-temperature-range`: one JSON object containing inclusive `min_C` / `max_C` limits shared by all assigned water controls.
- Sample combination limits continue to use `--temperature-ranges` by measurement ID.
- Resolved controls are returned in `settings.water_blank_controls`, keyed by curve. Each entry identifies the run, cycle, measurement IDs, original first-freeze temperature, effective temperature limits, and whether background is zero throughout.
- Saved native analyses retain these settings and resolved controls.

## Scientific behavior supplied by the toolkit

- Assigned blanks in each run/cycle share one water background and retain their actual well volumes.
- The first-freeze option fixes background and its uncertainty contribution at zero before the earliest observed freeze in that assigned control set. Never-frozen controls give zero background throughout.
- Onset is resolved from original observations before grid selection and sample exclusions.
- The rule applies to joint MLE, Average, direct individual concentrations, and uncertainty.
- Manual blank limits filter control observations. They do not imply zero correction outside the limits. Latest selection can retain a warmer state at a colder target; missing required direct-control states give unavailable concentrations. MLE uses retained trajectories.
- Raw blank counts and fractions remain unchanged.

## Icescopy controls

- The Samples page retains Apply blank correction, Start correction at first blank freeze, and plot visibility.
- Blank range rows remain visible in the concentration limits table as read-only references; blank concentration is not plotted.
- Edit shared blank limits in Number frozen or Fraction frozen. Changing one blank row updates the shared limit for all controls.
- With first-freeze correction enabled, warm fields/tags remain visible but locked at onset. Cold limits remain adjustable in raw views.
- Full range in concentration clears sample cuts only. Full range in raw views also clears manual blank cuts; it retains the first-freeze checkbox.
- Method-dependent controls remain in a separate native Qt box, without redundant MLE/Average options titles.
- Unsupported controls are disabled according to the executable's advertised capabilities.

## Relevant client files

`src/icescopy_inptk_state.py`, `src/icescopy_inptk_panel.py`, `src/icescopy_inptk_plot.py`, and `tests/test_inptk.py`.

Checks cover actual CLI flags, both methods, direct uncertainty before onset, shared control ranges, multiple blanks, locked/read-only controls, saving, raw-count preservation, and grid-based useful spectrum endpoints.
