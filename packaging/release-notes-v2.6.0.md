# Icescopy 2.6.0

## INP toolkit client

Analyze Freeze Count Timeseries directly in **Analysis → INP Analysis…**. Group samples and dilutions, assign water blanks, and calculate concentration in suspension, air, or dry soil. Choose maximum likelihood (MLE) or Average, inspect individual and combined curves with uncertainty, and adjust each sample’s temperature limits using the plot or table.

- Interactive number-frozen and fraction-frozen plots include water blanks.
- Concentration plots show combined groups in black and individual samples in their Icescopy colors. Individual values outside selected limits are faded.
- Calculation defaults to a 0 to −35 °C grid in 0.5 °C steps. Cycle selection, separate analysis undo/redo, and configurable plot and table appearance are supported.
- Combined and individual concentration CSV exports contain temperature, concentration, and lower/upper uncertainty bounds. Missing values remain empty. Frozen-fraction CSV and native `.inptk` session exports are also available.
- Analysis choices and results are retained in the `.icescopy` session.

Install [INP-toolkit 0.4.2](https://github.com/bochens/inptk/releases/tag/v0.4.2) separately and select its executable in **Preferences → INP toolkit client**. Icescopy communicates with the toolkit as a separate process; the toolkit executable and calculation code are not bundled. This release was checked against 0.4.2, including its corrected Average blank subtraction, uncertainty, and handling of unavailable values outside each spectrum’s freezing interval.

## Updated Mac download

The Mac archive includes [automatic blank assignment and sample-type concentration choices](https://github.com/bochens/Icescopy/commit/5c73f4b) and [fixed-position display controls](https://github.com/bochens/Icescopy/commit/2890b83), in addition to the original 2.6.0 source:

- Marking **Blank** applies that control to all non-blank analysis samples when **Apply blank correction** is enabled; no second dropdown assignment is needed.
- Air samples offer **Suspension** and **Sampled air**. Soil samples offer **Suspension** and **Dry soil**. Calculations containing different sample types offer suspension concentration.
- **Show combined curve** and **Uncertainty** remain visible and are disabled when they do not apply, keeping the layout stable.

- Decorative middle-dot separators have been removed from interface headings, legends, event selectors, status messages, and documentation links.

## Other improvements

- Freeze Count Timeseries updates after freeze-frame and sample-metadata edits, using retained temperature inputs.
- Temperature-import summaries use consistent wording and identify unassigned samples. Blank correction is performed during toolkit analysis rather than temperature import.
- Uniform Exposure now uses original frame brightness to reduce exposure variation between images.
- Fixed freeze-frame mapping when the convolution half-window setting is zero.
- Improved sample metadata labels, units, and update messages.

## Download

**macOS, Apple Silicon:** download `Icescopy-macos-arm64.zip`, unzip it, and replace `Icescopy.app` in Applications after saving work and closing the app. The bundle is ad-hoc signed for integrity, not Apple-notarized.

**Windows:** download [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.6.0/Icescopy-windows-installer.exe) for 64-bit x64 Windows 10 (1809 or later) or Windows 11. Save work and close Icescopy before upgrading, run the installer, then open Icescopy from the Start menu. It installs for your Windows account and includes Python, the required libraries, and the General droplets 1.0.0 model. No separate Python installation or GPU is required. Install INP-toolkit 0.4.2 separately as described above.

GitHub displays a SHA-256 checksum beside each uploaded file under Assets.

The bundled General droplets 1.0.0 model is unchanged. Standalone inference and training weights remain available on the [2.5.0 release](https://github.com/bochens/Icescopy/releases/tag/v2.5.0).
