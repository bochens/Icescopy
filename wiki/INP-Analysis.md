# INP analysis

Icescopy sends its Freeze Count Timeseries to a separately installed **INP toolkit** executable. The toolkit calculates concentrations and uncertainty; Icescopy provides the controls, plots, and saved session. INP toolkit is not included in the Icescopy installer.

## Open the analysis

In **Settings → INP toolkit**, browse to the executable, choose **Test connection**, then save. The client requires CLI protocol **2** and saved format **4**, provided by INP toolkit **0.4.0**.

After importing temperatures and reviewing freeze events, open **Analysis → INP Analysis…**. Icescopy connects and loads the counts automatically. This resizable window blocks editing in the main window while open. Closing it retains your analysis choices and results.

## Group samples and assign blanks

A **sample group** contains the independent samples or dilutions you want to combine into one concentration curve. Start with the **Sample groups** list on the left. That same selection controls the settings, plot, and results table; there is no separate plot selector.

1. Select a group, or choose **New…** beside **Sample groups**. Double-click its name to rename it.
2. In **Samples**, check **Use** beside each sample that belongs to the group. Checking a sample moves it from its previous group; empty previous groups are removed. Unchecking a sample returns it to an individual group. No observations are deleted.
3. Check **Blank** beside water-control samples. These cannot also be group members. Select a sample row, then choose its controls under **Blank correction → Water blanks for…**. Without an assigned blank, that sample is not corrected. Blank roles are never inferred from names.
4. If a sample has several freezing cycles, choose its cycle below the table. Repeated cycles are not pooled as independent droplets.

**Remove** removes the selected group from the output, not the source samples. They remain available in the Samples table. Hold Ctrl/Cmd or Shift to select several groups for comparison; select one group to change its membership or request automatic ranges. The heading above the results identifies the selected group and number of samples.

Dilution factors are shown beside sample names. To change dilution, well volume, or other physical metadata, choose **Edit sample metadata…**. This closes the analysis window without discarding its choices. On reopening, Icescopy refreshes the counts and metadata automatically.

Turning **Apply blank correction** off retains the blank assignments. Unchecking a sample's **Blank** role removes its assignments to other samples; Undo restores both the role and assignments.

## Combine dilutions and set ranges

In **Combine**, choose the calculation method and concentration basis: suspension, sampled air, or dry soil. These calculation settings apply to all groups; each basis needs its corresponding physical metadata.

- **MLE**, maximum likelihood estimation, jointly fits the sample and blank freezing counts over the cooling curve. Optional fit spacing controls the fitted curve shape.
- **Average** takes an equal-weight mean of eligible concentration estimates at each temperature.

Each sample has cold/warm handles on the temperature axis, with faint vertical dashed guides. Colors match Icescopy's sample catalog. Select a row in the limits table to bring that sample's handles forward, then drag them or type temperatures into the table. This also lets you choose which sample to edit when limits overlap. Dragging elsewhere in the plot pans the view. Both endpoints are included. Gray italic numbers show the measured endpoints when a limit is unrestricted. Clear a field to return that boundary to the measured range, or choose **Full range** to clear limits for all samples in the selected groups. Full range can be undone.

For **Average**, choose **Auto range** to suggest limits for the selected group. The minimum frozen and unfrozen counts control the suggestion. A complete suggestion fills the editable limits. An incomplete suggestion leaves your limits unchanged and explains which inputs need attention. Its full report is available under **Table → Range suggestions**. MLE ranges are set manually.

Choose **Calculate** to generate concentrations, or **Recalculate** after changing inputs or settings. Errors remain visible. The last successful result is retained and identified as out of date until a new calculation succeeds.

The status shows elapsed calculation time. The console reports toolkit and display time separately. Recalculate reuses the current result when the inputs and settings are unchanged in the same toolkit connection.

## Read the plots

In the **Plot** tab, use the quantity control to switch between:

- **Number frozen:** original counts, with a vertical range covering zero through the samples' total well counts.
- **Fraction frozen:** original fractions on a 0–1 scale, with a small margin for endpoint symbols.
- **Concentration:** calculated values on a logarithmic axis by default, with the concentration unit on the axis. A solid black line shows the combined group; colored dashed lines show its individual samples, labeled with their dilution factors. Sample colors match the temperature handles and sample catalog. Faint crosses identify excluded points. Turn on **Uncertainty** to show the group's confidence limits and gray shading; the axes expand to include them.

Individual concentration curves use the same calculation method, blank assignments, units, and temperature limits as the group. Selecting a group shows its samples automatically. Individual error widths are available in **Table**. Adding these curves does not count the droplets again in the combined fit.

Switching quantity, selecting groups, or receiving a new result fits the axes to that view. Pan and zoom to inspect details; **Fit axes** restores the appropriate extent. Temperature increases from left to right.

Concentration opens with **Log scale** enabled and **Uncertainty** off so that wide intervals do not obscure comparison of the curves. These controls only change the display. Zero values and nonpositive bounds cannot appear on a logarithmic axis. When uncertainty is shown, shading is drawn only where both bounds can be displayed, without bridging missing intervals. An all-zero or unavailable result shows an explanation instead of an unexplained blank plot. The **Table** retains the original values, including infinite bounds. Older saved results need one recalculation to include individual sample curves.

**Lower error** and **Upper error** are distances from the concentration to its confidence limits. INP toolkit supplies these values. Its Average method uses conservative intervals that allow for shared blank uncertainty; adding samples does not necessarily narrow them.

## Advanced settings, undo, and export

The **Advanced** tab contains count selection on a temperature grid, handling of decreases, and the uncertainty setting. New analyses use a **0.5 °C temperature grid**. Turn **Use a temperature grid** off to use every measured temperature. Existing saved grid settings are preserved. Count-selection spacing and MLE fit spacing are separate controls; changing either requires recalculation. The results table puts temperature and scientific values first; exported column names and values remain those supplied by INP toolkit.

**Undo/Redo** and Ctrl/Cmd+Z use a separate history for INP analysis. Moving a temperature handle creates one undo entry. Closing and reopening preserves this history; starting or loading a session clears it. Main-window undo affects image, cell, and sample edits without reverting INP choices. The **Console** tab shares Icescopy's console messages.

Save the `.icescopy` session to retain choices, suggestion reports, and the last successful result. **Export** saves a native `.inptk` result folder or CSV files containing all calculated counts, fractions, concentrations, or excluded points. Export uses the last successful calculation, even if newer edits have not been calculated. Choose a new destination; existing exports are preserved.

A **Stop** button appears only while the toolkit is working. Stopping or closing during a calculation retains the last successful result. Choosing Calculate again restarts the separate toolkit process automatically.
