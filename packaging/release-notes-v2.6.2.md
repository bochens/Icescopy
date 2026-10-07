# Icescopy 2.6.2

## Concentration plot correction

Fixed a serious display bug that could change concentration-axis numbers by a factor of 1,000 after **Calculate** or a plot redraw, while leaving the unit label unchanged. Axis numbers now stay in the stated units, with no hidden multiplier. Calculated concentrations and CSV exports were unaffected.

**If you downloaded the earlier Mac build of 2.6.2, replace it with the updated download below. Regenerate any plots made with the affected build before using them.**

## Changes

For INP concentration analysis, install [INP-toolkit 0.4.6](https://github.com/bochens/inptk/releases/tag/v0.4.6) separately and select its executable in **Preferences → INP toolkit client**.

- Added **Export INP-toolkit concentration CSV** below a divider in the export menu. It preserves the toolkit’s full table format and uncertainty columns; compact CSV exports remain available.
- INP analysis now uses each sample’s calibrated TAMU temperatures and skips observations without usable temperatures.
- Improved loading of default preferences and reporting of toolkit errors.
- Added warnings for image timestamps that are out of order or use a different time convention from the temperature file.

## Download

**[macOS, Apple Silicon](https://github.com/bochens/Icescopy/releases/download/v2.6.2/Icescopy-macos-arm64.zip):** save your work and close Icescopy, unzip the download, then replace **Icescopy.app** in Applications. See [installation help](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md) if macOS blocks opening it.

**[Windows, x64](https://github.com/bochens/Icescopy/releases/download/v2.6.2/Icescopy-windows-installer.exe):** save your work and close Icescopy, then run the installer.
