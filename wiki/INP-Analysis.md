# INP analysis

Icescopy sends its Freeze Count Timeseries to a separately installed **INP toolkit** executable. The toolkit calculates concentrations and uncertainty; Icescopy provides the controls, plots, and saved session. INP toolkit is not included in the Icescopy installer.

## Open the analysis

In **Settings → INP toolkit client**, browse to the executable, choose **Test connection**, then save. The client requires CLI protocol **2**, saved format **4**, and support for in-memory import and result references. Update INP toolkit if the connection test reports missing capabilities.

After importing temperatures and reviewing freeze events, open **Analysis → INP Analysis…**. Icescopy connects and loads the counts automatically. Drag the title bar to move this resizable window. It has a normal window title bar, while editing in other Icescopy windows is blocked until analysis closes. Enter commits the field being edited without activating an unrelated button. Closing it retains your analysis choices and results.

## Group samples and assign blanks

A **sample group** contains the independent samples or dilutions you want to combine into one concentration curve. Start with the **Sample groups** list on the left. That same selection controls the settings and plot; there is no separate plot selector.

1. Select a group, or choose **New…** beside **Sample groups**. Double-click its name to rename it.
2. In **Samples**, check **Use** beside each sample that belongs to the group. Checking a sample moves it from its previous group; empty previous groups are removed. Unchecking a sample returns it to an individual group. No observations are deleted.
3. Check **Blank** beside water-control samples. These cannot also be group members. Select a sample row, then choose its controls under **Blank correction → Water blanks for…**. Blank roles are never inferred from names. When a blank map is supplied, every sample included in the calculation needs an assignment; leave all assignments empty for analysis without blanks. Samples outside the requested groups and unassigned blanks do not enter the calculation.
4. If a sample has several freezing cycles, select its row and choose **Cycle for [sample]** below the table. The selector and legend cycle suffix are hidden for samples with only one cycle. Repeated cycles are not pooled as independent droplets.

**Remove** removes the selected group from the output, not the source samples. They remain available in the Samples table. Hold Ctrl/Cmd or Shift to select several groups for comparison; select one group to change its membership or request automatic ranges. The heading above the results identifies the selected group and number of samples.

Dilution factors are shown beside sample names (for example, **10×**). The **Show** checkbox hides or shows each sample, including its uncertainty and range guides, without changing calculation membership or exports. **Show combined curve** controls the combined concentration line. These display choices are saved with the session; hidden curves disappear from the compact legend. To change dilution, well volume, or other physical metadata, choose **Edit sample metadata…**. This closes the analysis window without discarding its choices. On reopening, Icescopy refreshes the counts and metadata automatically.

In **Settings → INP toolkit client → Table columns**, choose fields separately for **Samples tab** and **Combine tab · temperature limits**, including custom catalog fields. Each table keeps its own selection. Dilution is shown by default. Sample identity and the Use, Blank, and Show controls stay visible. Additional columns scroll horizontally inside the table; they do not widen the analysis window. These preferences affect display only.


Turning **Apply blank correction** off retains the blank assignments. Unchecking a sample's **Blank** role removes its assignments to other samples; Undo restores both the role and assignments.

## Combine dilutions and set ranges

In **Combine**, choose the calculation method and concentration basis: suspension, sampled air, or dry soil. These calculation settings apply to all groups; each basis needs its corresponding physical metadata.

- **MLE**, maximum likelihood estimation, finds the concentration curve that maximizes the probability of the measured freezing counts across samples and assigned water blanks. It uses the additional droplets frozen between consecutive temperature observations and the number still liquid at the end. Each droplet contributes once; repeated frames do not add droplets. Optional fit spacing controls the fitted curve shape. Confidence limits are found by testing each concentration while refitting the other concentrations and blank background.
- **Average** directly converts frozen fractions to concentrations, subtracts the assigned water background, corrects for dilution, and averages eligible concentrations at each temperature. Where only one dilution is eligible, it contributes its own estimate. Wilson binomial bounds describe uncertainty in the sample and blank frozen fractions. The toolkit transforms those bounds into concentration error widths and propagates them by squaring, adding, and taking the square root. Blank subtraction reverses the direction of the blank errors. A shared blank contributes once with the combined weights of the samples using it.

Expand **Equations and uncertainty** under Combine for the formulas and assumptions. The limits describe uncertainty at each temperature, conditional on the selected ranges; they are not a confidence band for the entire curve and do not include uncertainty from choosing those ranges.

Each sample retains its own cold and warm limits. Faint vertical dashed lines show all limits in the selected group, using the sample catalog colors. Select a row in the limits table or click an individual sample's curve to show its two draggable tags in a single row **below the plot**. Only that sample's controls are active, so overlapping limits cannot silently edit a different sample. You can also type temperatures into the table. Dragging elsewhere in the plot pans the view.

Both endpoints are included. Gray italic numbers show the default endpoints: the sample's measured cold limit and a **0 °C warm limit**. Clear a field to return that boundary to its default, or choose **Full range** to reset limits for all samples in the selected groups. These defaults are also sent to the toolkit; readings above 0 °C are omitted from the concentration calculation unless you explicitly set a warmer limit. Full range can be undone.

The limits table displays two decimal places. Dragging, calculations, and saved sessions retain the original precision; only editing a value changes it.

For **Average**, choose **Auto range** to suggest limits for the selected group. The minimum frozen and unfrozen counts control the suggestion. A complete suggestion fills the editable limits. An incomplete suggestion leaves your limits unchanged and explains which inputs need attention in Icescopy's console. Repeating Auto range with unchanged inputs and settings reuses the summary from the current toolkit connection. MLE ranges are set manually.

Choose **Calculate** to generate concentrations. Every click runs the group calculations, including when the result is already up to date. Errors remain visible. The last successful result is retained and identified as out of date until a new calculation succeeds.

The status shows elapsed calculation time. The console reports toolkit and display time separately. Uploaded counts and unchanged full-range individual comparisons are reused to keep group calculations responsive.

Counts are transferred from Icescopy's memory to one persistent toolkit process. Each calculation sends the requested groups' samples and their assigned blanks; Auto range sends only the selected group's inputs. The complete count table remains available for raw plots. Changing limits, method, or grid reuses uploaded counts; changing the source data, requested samples, metadata, or blank assignments transfers a new input. Calculating does not create temporary CSVs or save result folders. Superseded toolkit results are released after the replacement succeeds.

## Read the plots

Use the quantity control above the plot to switch between:

- **Number frozen:** original counts, with a vertical range covering zero through the samples' total well counts.
- **Fraction frozen:** original fractions on a 0–1 scale, with a small margin for endpoint symbols.
- **Concentration:** calculated values on a logarithmic axis by default, with the concentration unit on the axis. A solid black line shows the combined group; colored dashed lines show its individual samples, labeled with their dilution factors. Turn on **Uncertainty** to show the group's confidence limits and gray shading; the axes expand to include them.

Every sample marked **Blank** appears in the counts and fraction plots as a dotted line labeled **water blank**, even before you assign it for correction or while correction is switched off. Assigned blanks follow the selected samples' cycles; unassigned blanks use their own cycle choice. These plots show measured values before correction. Displaying a blank does not assign it to a sample.

Checking **Use** in a new or existing group updates both raw plots and their axes immediately. No calculation is needed to show counts or fractions; concentration updates require **Calculate**.

Individual concentration curves are independent **full-range calculations**, using the same method, blank assignments, grid, and units as the group. They remain visible outside the selected limits, with those portions muted. Selecting a group shows its samples automatically. The legend stays inside the top-right corner of the plot when switching views, panning, or zooming. Changing limits updates the muting immediately; choose Calculate to update the combined result. Full-range calculations are reused when only limits change. These comparison curves do not add droplets to the combined calculation. Individual comparison plots also show excluded estimates for visual inspection, faded in the sample color along with their uncertainty. Points outside the selected limits are faded in the same way. Concentration CSVs use only the toolkit's final `cumulative` tables: existing grid points from each curve's first through last sample freezing event. Blank events do not extend that interval. The toolkit retains earlier and later observations for the MLE curve fit and its uncertainty; valid zero concentrations within the interval remain. Curves with different reporting intervals leave empty cells in the wide CSV.

If a full-range comparison fails, the successful calculation within your selected limits remains visible and exportable. The status and console explain the comparison failure. Choose **Calculate** to retry it.

Switching quantity, selecting groups, or receiving a new result fits the axes to that view. Pan and zoom to inspect details; **Fit axes** restores the cold extent through **0 °C**. Warmer original-count readings remain accessible by panning. Temperature increases from left to right.

Concentration uses a logarithmic axis by default. **Uncertainty** starts on and can be toggled above the plot. It shows confidence limits for both the combined result and individual samples; individual bands use their sample colors and are muted outside the selected limits. This toggle changes the display only. Zero values and nonpositive bounds cannot appear on a logarithmic axis. Shading is drawn only where both bounds can be displayed, without bridging missing intervals. An all-zero or unavailable result shows an explanation instead of an unexplained blank plot. Exports retain the original values, including infinite bounds. Older saved results need one recalculation to include full-range individual sample curves.

In **Settings → INP toolkit client**, display controls are grouped by their scope:

- **All INP plots:** horizontal grid opacity, legend text size, sample line width, and point size. Sample line width applies to samples and blanks in count/fraction plots, and individual dilutions in concentration plots. Set point size or grid opacity to zero to hide them.
- **Concentration plots:** logarithmic or linear axes, group-result line width, uncertainty shading opacity, and opacity outside selected limits. Group-result width controls the combined curve, or the sole sample when a group has one member. Outside-limit opacity affects individual concentration curves and their uncertainty bands.

These controls change the INP display only. Number and fraction frozen always use linear axes. Calculations, exports, and Icescopy's separate brightness Timeseries plot are unchanged.

## Advanced settings, undo, and export

The **Advanced** tab contains count selection on a temperature grid, handling of decreases, and the uncertainty setting. The default grid runs from **0 to −35 °C in 0.5 °C steps**. The warm and cold endpoint fields are directly below the step field; clearing either restores its default. Explicit saved endpoints are preserved. The toolkit uses available measurements at these grid temperatures; it does not invent measurements beyond the recording. Turn **Use a temperature grid** off to use measured temperatures. Count-selection spacing and MLE fit spacing are separate controls; changing either requires recalculation.

**Undo/Redo** and Ctrl/Cmd+Z use a separate history for INP analysis. Moving a temperature tag creates one undo entry. Closing and reopening preserves this history; starting or loading a session clears it. Main-window undo affects image, cell, and sample edits without reverting INP choices. **Show console** opens Icescopy's existing read-only console while the rest of the main window remains locked. The console returns to its previous position when analysis closes.

Save the `.icescopy` session to retain choices, suggestion summaries, and the last successful result. At Save, Icescopy captures the complete native toolkit result in the session; reopening and exporting it does not repeat the calculation. The analysis window has no separate results-table or console tabs; data remain available under **Export results**:

- **Save .inptk session:** an `.inptk` folder containing the toolkit's `analysis.json`. Separate full-range calculations, when needed, are included in `individual-samples.inptk`. Save the `.icescopy` session as well to retain the Icescopy controls.
- **Export frozen fraction CSV:** one temperature column and one frozen-fraction column per input, including water blanks selected by the toolkit. Fractions come from the same observations the toolkit selected on the calculation grid, before blank correction.
- **Export combined concentration CSV:** one temperature column and concentration, lower-bound, and upper-bound columns per calculated sample group. Individual dilution curves are excluded from this file.
- **Export individual sample concentrations CSV:** one temperature column and concentration, lower-bound, and upper-bound columns per individual sample or dilution, using its full-range comparison calculation. This is a direct menu action that exports all individual samples together.

Concentration headers state the saved units: **INP/mL suspension**, **INP/L air**, or **INP/g dry soil**. Both concentration files contain only temperatures, concentrations, and lower and upper uncertainty bounds. Bounds use the uncertainty level selected for the calculation and are exported even when plot uncertainty is hidden. They are concentration limits, not error distances; an unbounded upper limit is written as `inf`. The `.inptk` session retains the full result, including uncertainty. Rows run from warm to cold on the calculation grid; empty cells mean there is no calculated value at that temperature. A zero is an actual toolkit estimate. When the grid is explicitly disabled, exports use native calculation temperatures; measured frozen fractions use a compact sample/cycle layout.

Calculate after changing analysis inputs or settings before exporting CSVs. A stored result remains exportable when the current count table is unavailable; the file chooser identifies it as a saved calculation. CSVs are written only when Export is chosen. Choose a new destination; existing files are preserved and an incomplete new output is removed if writing fails.

Selecting a group changes the plot, not the export scope. The **Export results** menu names the calculated groups; combined CSVs cover all of them, while individual CSVs cover their member samples. Calculate to export a different normalization.

A **Stop** button appears only while the toolkit is working. Stopping or closing during a calculation retains the last successful result. Choosing Calculate again restarts the separate toolkit process automatically.

Stopping the toolkit or a process failure discards its unsaved native results. Concentration CSVs remain available from Icescopy's retained calculation tables. Native session and frozen-fraction exports need a previously saved native result or a new calculation. The displayed plot and choices can still be saved in `.icescopy`.

Edits to freeze events or sample metadata update Icescopy's tables in memory. CSV files inside a `.icescopy` archive are written when you save that session; separate CSV files are written when you choose Export. An earlier CSV export is never automatically rewritten.

These calculation descriptions follow **INP-toolkit 0.4.1**.
