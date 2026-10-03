# INP analysis

Icescopy sends its Freeze Count Timeseries to a separately installed **INP toolkit** executable. The toolkit calculates concentrations and uncertainty; Icescopy provides the controls, plots, and saved session. INP toolkit is not included in the Icescopy installer.

## Open the analysis

In **Settings → INP toolkit**, browse to the executable, choose **Test connection**, then save. The client requires CLI protocol **2** and saved format **4**, provided by INP toolkit **0.4.0**.

After importing temperatures and reviewing freeze events, open **Analysis → INP Analysis…**. Icescopy connects and loads the counts automatically. This resizable window blocks editing in the main window while open. Closing it retains your analysis choices and results.

## Group samples and assign blanks

A **sample group** contains the independent samples or dilutions you want to combine into one concentration curve. Start with the **Sample groups** list on the left. That same selection controls the settings, plot, and results table; there is no separate plot selector.

1. Select a group, or choose **New group**. Double-click its name to rename it.
2. In **Samples**, check **Use** beside each sample that belongs to the group. Checking a sample moves it from its previous group; empty previous groups are removed. Unchecking a sample returns it to an individual group. No observations are deleted.
3. Check **Blank** beside water-control samples. These cannot also be group members. Select a sample row, then choose its controls under **Blanks for…**. Blank roles are never inferred from names.
4. If a sample has several freezing cycles, choose its cycle below the table. Repeated cycles are not pooled as independent droplets.

**Remove group** removes that output, not the source samples. They remain available in the Samples table. Hold Ctrl/Cmd or Shift to select several groups for comparison; select one group to change its membership or request automatic ranges.

Dilution factors are shown beside sample names. To change dilution, well volume, or other physical metadata, choose **Edit sample metadata…**. This closes the analysis window without discarding its choices. On reopening, Icescopy refreshes the counts and metadata automatically.

Turning **Apply blank correction** off retains the blank assignments.

## Combine dilutions and set ranges

In **Combine**, choose the calculation method and concentration basis: suspension, sampled air, or dry soil. These calculation settings apply to all groups; each basis needs its corresponding physical metadata.

- **MLE**, maximum likelihood estimation, jointly fits the sample and blank freezing counts over the cooling curve. Optional fit spacing controls the fitted curve shape.
- **Average** takes an equal-weight mean of eligible concentration estimates at each temperature.

Each sample in the selected group has its own colored cold/warm handle pair along the bottom of the plot. Separate strips keep the pairs accessible when their temperatures overlap. Drag the handles or type temperatures into the matching table row. Both endpoints are included. Empty fields leave that boundary unrestricted.

For **Average**, choose **Auto range** to suggest limits for the selected group. The minimum frozen and unfrozen counts control the suggestion. A complete suggestion fills the editable limits. An incomplete suggestion leaves your limits unchanged and explains which inputs need attention. Its full report is available under **Table → Range suggestions**. MLE ranges are set manually.

Choose **Calculate** to generate concentrations, or **Recalculate** after changing inputs or settings. Errors remain visible. The last successful result is retained and identified as out of date until a new calculation succeeds.

## Read the plots

Use the quantity control above the plot to switch between:

- **Number frozen:** original counts, with a vertical range covering zero through the samples' total well counts.
- **Fraction frozen:** original fractions on a 0–1 scale, with a small margin for endpoint symbols.
- **Concentration:** calculated values and finite uncertainty bounds, with the concentration unit on the axis. Shading shows uncertainty; faint crosses identify excluded points.

Switching quantity, selecting groups, or receiving a new result fits the axes to that view. Pan and zoom to inspect details; **Fit axes** restores the appropriate extent. Temperature increases from left to right.

**Log scale** is available for concentration. Zero values and nonpositive bounds cannot appear on a logarithmic axis. Shading is drawn only where both bounds can be displayed, without bridging missing intervals. An all-zero or unavailable result shows an explanation instead of an unexplained blank plot. The **Table** retains the original values, including infinite bounds.

## Advanced settings, undo, and export

The **Advanced** tab contains optional count selection on a temperature grid, handling of decreases, and the uncertainty setting. Count-selection spacing and MLE fit spacing are separate controls; changing either requires recalculation.

**Undo/Redo** and Ctrl/Cmd+Z use a separate history for INP analysis. Moving a temperature handle creates one undo entry. Closing and reopening preserves this history; starting or loading a session clears it. Main-window undo affects image, cell, and sample edits without reverting INP choices. The **Console** tab shares Icescopy's console messages.

Save the `.icescopy` session to retain choices, suggestion reports, and the last successful result. **Export** saves a native `.inptk` result folder or CSV files containing all calculated counts, fractions, concentrations, or excluded points. Export uses the last successful calculation, even if newer edits have not been calculated. Choose a new destination; existing exports are preserved.

A **Stop** button appears only while the toolkit is working. Stopping or closing during a calculation retains the last successful result. Choosing Calculate again restarts the separate toolkit process automatically.
