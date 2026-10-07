# Icescopy 2.6.2

For INP concentration analysis, install [INP-toolkit 0.4.5](https://github.com/bochens/inptk/releases/tag/v0.4.5) separately and select its executable in **Preferences → INP toolkit client**.

- Added **Export INP-toolkit concentration CSV** below a divider in the export menu. It preserves the toolkit’s full table format and uncertainty columns; compact CSV exports remain available.
- INP analysis now uses each sample’s calibrated TAMU temperatures and skips observations without usable temperatures.
- Improved loading of default preferences and reporting of toolkit errors.
- Added warnings for image timestamps that are out of order or use a different time convention from the temperature file.

## Download

**[macOS, Apple Silicon](https://github.com/bochens/Icescopy/releases/download/v2.6.2/Icescopy-macos-arm64.zip):** save your work and close Icescopy, unzip the download, then replace **Icescopy.app** in Applications. See [installation help](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md) if macOS blocks opening it.

The latest Windows installer is available on the [2.6.1 release](https://github.com/bochens/Icescopy/releases/tag/v2.6.1).
