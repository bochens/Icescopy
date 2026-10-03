# INP analysis

Icescopy sends its Freeze Count Timeseries to a separately installed **INP toolkit** executable. The toolkit calculates concentrations and uncertainty; Icescopy provides the controls, plots, and saved session. INP toolkit is not included in the Icescopy installer.

## Open the analysis

In **Settings → INP toolkit**, browse to the executable, choose **Test connection**, then save. The client requires CLI protocol **2**, saved format **4**, and support for in-memory import and result references. Update INP toolkit if the connection test reports missing capabilities.

After importing temperatures and reviewing freeze events, open **Analysis → INP Analysis…**. Icescopy connects and loads the counts automatically. This resizable window blocks editing in the main window while open. Closing it retains your analysis choices and results.

## Group samples and assign blanks

A **sample group** contains the independent samples or dilutions you want to combine into one concentration curve. Start with the **Sample groups** list on the left. That same selection controls the settings and plot; there is no separate plot selector.

1. Select a group, or choose **New…** beside **Sample groups**. Double-click its name to rename it.
2. In **Samples**, check **Use** beside each sample that belongs to the group. Checking a sample moves it from its previous group; empty previous groups are removed. Unchecking a sample returns it to an individual group. No observations are deleted.
3. Check **Blank** beside water-control samples. These cannot also be group members. Select a sample row, then choose its controls under **Blank correction → Water blanks for…**. Blank roles are never inferred from names. The toolkit requires a blank assignment for every nonblank input when a blank map is supplied; leave all assignments empty for analysis without blanks.
4. If a sample has several freezing cycles, choose its cycle below the table. Repeated cycles are not pooled as independent droplets.

**Remove** removes the selected group from the output, not the source samples. They remain available in the Samples table. Hold Ctrl/Cmd or Shift to select several groups for comparison; select one group to change its membership or request automatic ranges. The heading above the results identifies the selected group and number of samples.

Dilution factors are shown beside sample names. To change dilution, well volume, or other physical metadata, choose **Edit sample metadata…**. This closes the analysis window without discarding its choices. On reopening, Icescopy refreshes the counts and metadata automatically.

Turning **Apply blank correction** off retains the blank assignments. Unchecking a sample's **Blank** role removes its assignments to other samples; Undo restores both the role and assignments.

## Combine dilutions and set ranges

In **Combine**, choose the calculation method and concentration basis: suspension, sampled air, or dry soil. These calculation settings apply to all groups; each basis needs its corresponding physical metadata.

- **MLE**, maximum likelihood estimation, jointly fits the sample and blank freezing counts over the cooling curve. It uses first-freezing intervals and surviving droplets; repeated frames are not new droplets. Optional fit spacing controls the fitted curve shape. Confidence limits are found by testing each concentration while refitting the other concentrations and blank background.
- **Average** fits each eligible sample with its assigned blanks, then takes an equal-weight mean at each temperature. Where only one dilution is eligible, it contributes its own estimate. The toolkit widens the individual confidence limits to allow for shared blanks, then averages their endpoints. Adding samples therefore does not necessarily narrow the limits.

Expand **Equations and uncertainty** under Combine for the formulas and assumptions. The limits describe uncertainty at each temperature, conditional on the selected ranges; they are not a confidence band for the entire curve and do not include uncertainty from choosing those ranges.

Each sample retains its own cold and warm limits. Faint vertical dashed lines show all limits in the selected group, using the sample catalog colors. Select a row in the limits table or click an individual sample's curve to show its two draggable tags in a single row **below the plot**. Only that sample's controls are active, so overlapping limits cannot silently edit a different sample. You can also type temperatures into the table. Dragging elsewhere in the plot pans the view.

Both endpoints are included. Gray italic numbers show the measured endpoints when a limit is unrestricted. Clear a field to return that boundary to the measured range, or choose **Full range** to clear limits for all samples in the selected groups. Full range can be undone.

For **Average**, choose **Auto range** to suggest limits for the selected group. The minimum frozen and unfrozen counts control the suggestion. A complete suggestion fills the editable limits. An incomplete suggestion leaves your limits unchanged and explains which inputs need attention in Icescopy's console. **Export → Export range-suggestion summary (JSON)…** saves the proposed limits, reasons, and completeness status. Repeating Auto range with unchanged inputs and settings reuses the summary from the current toolkit connection. MLE ranges are set manually.

Choose **Calculate** to generate concentrations, or **Recalculate** after changing inputs or settings. Errors remain visible. The last successful result is retained and identified as out of date until a new calculation succeeds.

The status shows elapsed calculation time. The console reports toolkit and display time separately. Recalculate reuses the current result when the inputs and settings are unchanged in the same toolkit connection.

Counts are transferred from Icescopy's memory to one persistent toolkit process. Changing limits, method, or grid reuses those counts; changing the source data, metadata, or blank assignments transfers a new input. Calculating does not create temporary CSVs or save result folders. Superseded toolkit results are released after the replacement succeeds.

## Read the plots

Use the quantity control above the plot to switch between:

- **Number frozen:** original counts, with a vertical range covering zero through the samples' total well counts.
- **Fraction frozen:** original fractions on a 0–1 scale, with a small margin for endpoint symbols.
- **Concentration:** calculated values on a logarithmic axis by default, with the concentration unit on the axis. A solid black line shows the combined group; colored dashed lines show its individual samples, labeled with their dilution factors. Turn on **Uncertainty** to show the group's confidence limits and gray shading; the axes expand to include them.

Assigned water blanks appear in the counts and fraction plots as dotted lines labeled **water blank**, including when correction is switched off. These plots show measured values before correction and use the selected sample's freezing cycle for its blank.

Individual concentration curves are independent **full-range fits**, using the same method, blank assignments, grid, and units as the group. They remain visible outside the selected limits, with those portions muted. Selecting a group shows its samples automatically. Changing limits updates the muting immediately; choose Recalculate to update the combined result. Full-range fits are reused when only limits change. These comparison curves do not add droplets to the combined fit.

Switching quantity, selecting groups, or receiving a new result fits the axes to that view. Pan and zoom to inspect details; **Fit axes** restores the appropriate extent. Temperature increases from left to right.

Concentration opens with **Log scale** enabled and **Uncertainty** off so that wide intervals do not obscure comparison of the curves. These controls only change the display. Zero values and nonpositive bounds cannot appear on a logarithmic axis. When uncertainty is shown, shading is drawn only where both bounds can be displayed, without bridging missing intervals. An all-zero or unavailable result shows an explanation instead of an unexplained blank plot. Exports retain the original values, including infinite bounds. Older saved results need one recalculation to include full-range individual sample curves.

In **Settings → INP toolkit → Plot appearance**, adjust sample and combined line widths, point size, and the opacity outside selected limits. These preferences change the display only.

## Advanced settings, undo, and export

The **Advanced** tab contains count selection on a temperature grid, handling of decreases, and the uncertainty setting. New analyses use a **0.5 °C temperature grid**. Turn **Use a temperature grid** off to use every measured temperature. Existing saved grid settings are preserved. Count-selection spacing and MLE fit spacing are separate controls; changing either requires recalculation.

**Undo/Redo** and Ctrl/Cmd+Z use a separate history for INP analysis. Moving a temperature tag creates one undo entry. Closing and reopening preserves this history; starting or loading a session clears it. Main-window undo affects image, cell, and sample edits without reverting INP choices. **Show console** opens Icescopy's existing read-only console while the rest of the main window remains locked. The console returns to its previous position when analysis closes.

Save the `.icescopy` session to retain choices, suggestion summaries, and the last successful result. At Save, Icescopy captures the complete native toolkit result in the session; reopening and exporting it does not repeat the fit. The analysis window has no separate results-table or console tabs; detailed data remain available under **Export**:

- **Native result:** an `.inptk` folder containing the toolkit's `analysis.json`. Separate full-range fits, when needed, are included in `individual-samples.inptk`; the calculation's range-suggestion report is included as JSON when available.
- **CSV:** counts, fractions, concentrations, and excluded points from the last calculation. **Export individual concentrations** saves a selected full-range comparison curve. **Lower error** and **Upper error** are distances from the estimate to its confidence limits.
- **Range-suggestion summary (JSON):** the latest proposed limits, reasons, and completeness status. Individual observation decisions are omitted to keep interactive requests small. JSON is a structured text format readable by analysis scripts.

The toolkit's excluded-points export contains estimates omitted from its final concentration curve, for example by its decrease policy. This differs from the muted portions outside the user-selected ranges. Original-count exports can contain the original recording temperatures rather than the calculation grid.

Calculation exports use the last successful result, even if newer edits have not been calculated. Choose a new destination; existing exports are preserved.

A **Stop** button appears only while the toolkit is working. Stopping or closing during a calculation retains the last successful result. Choosing Calculate again restarts the separate toolkit process automatically.

Stopping the toolkit or a process failure discards its unsaved native results. The displayed plot and choices remain available and can still be saved in `.icescopy`, but a result not captured by an earlier Save needs recalculation before native or CSV export. Already saved native results remain exportable.

Edits to freeze events or sample metadata update Icescopy's tables in memory. CSV files inside a `.icescopy` archive are written when you save that session; separate CSV files are written when you choose Export. An earlier CSV export is never automatically rewritten.
