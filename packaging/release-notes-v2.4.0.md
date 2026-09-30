# Icescopy 2.4.0

This release adds synchronized image comparison, faster cell and freeze-event review, and support for newer CSU cold-stage records.

## Compare and review

- Two- and three-image views now have separate Previous, Current, and Next panels with linked pan and zoom. Each panel shows the cell positions and sizes for its own frame, and image adjustments apply across the panels.
- The Cells list has **Auto-center** and **Show freeze frame** options. Selecting a row, clicking it again, or moving with the arrow keys applies the enabled options. Selecting cells directly in the image does not trigger automatic navigation.
- Use the Cells event selector to move between a cell's freeze events and cooling cycles. Timeline event arrows move through events for selected cells, or all cells when none are selected.
- Imported cycle information remains available after manual freeze-event corrections and when restoring sessions or undoing changes.

## CSU temperature import

- The CSU importer accepts either `Sample_Temp` or `Avg_Temp`, in °C. The `Picture` column matches images to their recorded times and temperatures.
- Choose **Icescopy detections**, **CSU recorded counts**, or **Icescopy + CSU**. Image counts work without instrument count columns. Recorded counts preserve decreases and do not create individual cell freeze events.
- Invalid counts, ambiguous image matches, and image-order problems produce clear errors or warnings. Recorded counts above the assigned cell total are rejected rather than clipped.
- The dialog explains sample naming and places the temperature-column information beside those instructions. The user guide covers the count choices and their limits.

## Download for Mac

Download **Icescopy-macos-arm64.zip**, extract it, and copy **Icescopy.app** to **Applications**. This build is for Apple Silicon Macs and includes Python and the required libraries. The matching **Icescopy-macos-arm64.zip.sha256** file provides the download checksum.

Save open work and close the installed app before replacing it. Keep previous sessions and exports under their original names.

The app is signed locally for integrity, without Apple notarization. See the [Mac installation guide](https://github.com/bochens/Icescopy/blob/v2.4.0/wiki/Installation-and-Setup.md#install-on-macos) if macOS asks for approval on first launch.

## Windows

The Windows installer for 2.4.0 will be added separately. The [2.3.8 Windows installer](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-windows-installer.exe) remains available in its original release.

Windows maintainers should build from tag `v2.4.0` using [the packaging instructions](https://github.com/bochens/Icescopy/blob/v2.4.0/packaging/windows/README.md) and add the installer and its checksum to this release.
