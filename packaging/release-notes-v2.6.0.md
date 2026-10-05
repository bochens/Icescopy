# Icescopy 2.6.0

## INP toolkit client

Calculate INP concentrations from Freeze Count Timeseries in **Analysis → INP Analysis…**. Group dilution series, apply water-blank correction, and combine results using **maximum likelihood estimation (MLE)** or **Average**. Calculate concentrations in suspension, sampled air, or dry soil.

- Inspect freezing counts, frozen fractions, and individual and combined concentration curves with uncertainty.
- Adjust each sample’s temperature limits in the plot or table.
- Export concentration CSVs with lower and upper uncertainty bounds, frozen-fraction CSVs, and native `.inptk` sessions.
- Retain analysis settings and results in the `.icescopy` session.

Install [**INP-toolkit 0.4.2**](https://github.com/bochens/inptk/releases/tag/v0.4.2) separately and select its executable in **Preferences → INP toolkit client**.

## Improvements

- Freeze Count Timeseries updates after freeze-frame and sample-metadata edits.
- Uniform Exposure reduces brightness variation between images.
- Correct freeze-frame detection when **Convolution Half Window Points** is set to zero.

## Downloads

Save your work and close Icescopy before updating.

- **macOS, Apple Silicon:** [Icescopy-macos-arm64.zip](https://github.com/bochens/Icescopy/releases/download/v2.6.0/Icescopy-macos-arm64.zip). Unzip and move **Icescopy.app** to **Applications**. See [macOS opening instructions](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md#install-on-macos).
- **Windows 10 (1809 or later) / 11, x64:** [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.6.0/Icescopy-windows-installer.exe). Run the installer.
