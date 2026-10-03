# INP analysis

Icescopy can send its Freeze Count Timeseries to a separately installed **INP toolkit** executable. The toolkit calculates concentrations and uncertainty; Icescopy supplies the controls, plots, and saved session. INP toolkit is not included in the Icescopy installer.

## Connect the toolkit

In **Settings → INP toolkit**, browse to the executable, choose **Test connection**, then save the settings. This client requires CLI protocol **2** and saved format **4**, provided by INP toolkit **0.4.0**. An incompatible executable produces a connection error.

After importing temperatures and reviewing freeze events, open **Analysis → INP Analysis…** and choose **Connect**. This resizable window blocks editing in the main window while it is open. Close it to return to the images or sample metadata; the analysis remains available when reopened.

## Choose inputs, groups, and blanks

The **Samples & blanks** tab lists the physical inputs read from the count table. Counts and frozen fractions can be viewed before all concentration metadata is complete.

1. Give dilutions of the same original sample the same **Sample group** value. Similar names do not cause automatic grouping.
2. Choose a cycle for each input. Multiple freezing cycles are not pooled as independent droplets.
3. Check **Blank** for a water-blank input. Select a sample input and use **Blanks for selected input** to assign its blank. No blank is inferred from its name.
4. Define the output curves. **Add input** creates an individual curve; **Add group** combines the inputs in the selected original-sample group. Double-click a curve name to rename it. Use the selector below the list to edit its inputs.

Turning **Apply blank correction** off retains the assignments. To change well volume, dilution, or sample normalization metadata, choose **Edit sample metadata…**. This closes the analysis window without discarding its choices.

## Combine dilutions and set limits

In **Combine dilutions**, choose **MLE** or **Average** and the concentration basis: suspension, sampled air, or dry soil. The selected basis needs the corresponding physical metadata.

- **MLE**, maximum likelihood estimation, jointly fits the sample and blank freezing counts over the cooling curve. Optional fit spacing controls the fitted curve shape.
- **Average** takes an equal-weight mean of eligible concentration estimates at each temperature.

Every input in the selected output curve has its own colored cold/warm handle pair, shown together in separate strips along the bottom of the plot. This keeps pairs accessible even when limits overlap. Drag a pair or enter temperatures in that input's table row. Both endpoints are included. An empty field leaves that boundary unrestricted. An input's limits apply to every output curve using it.

For **Average**, choose the output curve in **Combine dilutions**, then choose **Suggest limits**. The minimum frozen and unfrozen counts control the suggestion. A complete suggestion fills the editable limits. An incomplete suggestion leaves existing limits unchanged and reports which inputs need attention. Inspect the report in **Table → Range suggestions**.

Choose **Recalculate** to apply changes. The last successful result remains visible until a new calculation succeeds; a status message identifies results that no longer match the current choices or source data.

## Inspect, undo, and save

The plot offers **Number frozen**, **Fraction frozen**, and **Concentration**, with a curve selector and optional logarithmic vertical axis. Counts and fractions show the original observations from the latest data refresh. Concentrations show the calculated result, with uncertainty bands. Hover over points for details; faint crosses identify excluded points. Temperature increases from left to right.

The **Advanced** tab contains optional count selection on a temperature grid, handling of decreases, and the uncertainty setting. Count-selection spacing and MLE fit spacing are separate controls; changing either requires recalculation.

**Undo/Redo** and Ctrl/Cmd+Z use a separate history for INP analysis choices. Moving a temperature handle creates one undo entry. Closing and reopening this window preserves its history; starting or loading a session clears it. Undo in the main window affects image, cell, and sample edits without reverting INP analysis choices. Both histories use the configured Undo History Limit. The **Console** tab shows the same messages as Icescopy's main console.

Save the `.icescopy` session to retain choices, the latest suggestion report, and the last successful result. **Export** can save a native `.inptk` result folder or calculated counts, fractions, concentrations, and excluded points as CSV. Exports always use the last successful calculation, including when newer edits have not been calculated. Choose a new destination: existing exports are preserved.

**Cancel** stops the separate toolkit process and retains the last successful result. Closing the window during a calculation also cancels it. Use **Connect** to start the toolkit again.
