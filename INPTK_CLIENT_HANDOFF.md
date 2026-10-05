# INP-toolkit handoff: water-blank limits and first-freeze rule

Icescopy remains a GUI client of the external CLI. Make scientific changes in INP-toolkit; do not duplicate its calculations in Icescopy.

## Requested behavior

- Keep joint MLE estimation of sample concentration and water background as the default.
- Add an optional **Start correction at first blank freeze** checkbox, off by default.
- Apply the option to joint MLE, Average, direct individual concentrations, and their uncertainty.
- Before the first observed freeze in the assigned water controls, use water background B = 0 with no blank uncertainty contribution. Include blank correction from that first freeze onward.
- Enforce this in the MLE fit and confidence-limit calculation. Removing earlier blank observations alone does not enforce B = 0.
- Use original observations to determine onset; changing the count grid or a sample's combination limits must not move the onset.
- Preserve raw water-blank counts and fractions, including zero counts before onset.
- Keep existing dilution/normalization rules: water blanks use their actual well volumes; sample dilution, air volume, suspension volume, and soil mass do not apply to blank metadata.

## Water-blank ranges

- Support explicit cold/warm limits for water-control observations, separately from sample combination limits.
- With the first-freeze option enabled, the client locks the blank warm limit at the onset. The cold limit remains adjustable.
- Resolve onset within each run and selected cycle, without pooling different runs or cycles. For multiple controls sharing one background, use the first observed freeze in that assigned control set; confirm this pooling rule with Bo before implementation.
- **Unresolved:** Bo has not yet chosen what manually excluded blank temperatures mean for corrected results. Agree whether these temperatures disable correction, make corrected results unavailable, or only exclude control observations from fitting. Do not silently assume zero background outside a manual range.
- If assigned blanks never freeze, the first-freeze option leaves B = 0 and its uncertainty contribution zero throughout.

## Proposed CLI contract (not yet provided by installed toolkit 0.4.3)

Expose on both `analyze` and `suggest-ranges`, and advertise through `capabilities.commands.<command>.options`:

- `--water-blank-after-first-freeze`: boolean, default false.
- `--water-blank-temperature-ranges`: JSON object keyed by measurement ID, with inclusive `min_C` / `max_C` limits. Omission uses all available blank observations. Keep sample `--temperature-ranges` semantics unchanged.
- Return the resolved first-freeze temperature and effective blank limits by run, cycle, and assigned control set, so the client can display the toolkit's actual decisions.
- Retain these choices with native saved analyses and reuse them consistently during further processing.

The client will enable each control only when its option is advertised. Unsupported requested settings must fail clearly rather than being ignored. Confirm this interface before releasing the executable; the names above are a proposal.

## Icescopy presentation

- Plot water controls only in **Number frozen** and **Fraction frozen**. Do not add water-blank concentration curves.
- Keep **Show** checkboxes on the Samples page.
- Include water-blank rows/limits in Combine only when viewing a plot containing those controls. No dilution field for blank rows.
- Keep warm-limit fields and handles visible but disabled when onset controls their value.
- Put method-specific Average controls and MLE/Average explanations in a separate box below shared controls.

## Scientific checks for the toolkit agent

Verify both methods and direct individual curves with zero blank freezes, the first blank freeze, several blank controls, unequal well volumes, separate cycles/runs, manual cold limits, and sample-range/grid changes. Verify concentrations and both uncertainty bounds, including shared-blank uncertainty. Raw counts/fractions must remain unchanged.

Current Icescopy files: `src/icescopy_inptk_state.py`, `src/icescopy_inptk_panel.py`, `src/icescopy_inptk_plot.py`, and `tests/test_inptk.py`.
