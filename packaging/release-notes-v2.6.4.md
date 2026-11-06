# Icescopy 2.6.4

## Changes

For INP concentration analysis, install [INP-toolkit 0.4.6](https://github.com/bochens/inptk/releases/tag/v0.4.6) separately and select its executable in **Preferences → INP toolkit client**.

- New **Rows** settings in all five temperature import dialogs (Standard, UTK, CSU, TAMU, PKU), both on by default:
  - **Stop at the last loaded image** leaves out CSU .dat records logged after the last loaded image, such as a picture taken after the stage warmed back up. Before, the last image's count was held to the end of the .dat file, which drew a flat line at the top of the **Number frozen** plot.
  - **Leave out warming** leaves out readings more than the warming tolerance above the coldest temperature reached so far in their cycle, once the cycle is below 0 °C. Set the tolerance in **Preferences → Analysis → Freeze Finding → Warming Tolerance (°C)** (default 0.2 °C).
- Rows recorded after warm-up could also make maximum likelihood (MLE) concentrations empty or infinite. The import summary and log report how many rows each setting left out, per cycle.
- Refined app icon: clearer shading and outlines, and an icy-blue background in light mode.
- The README now says plainly that the optional neural network only places droplets and does not detect freezing.

Reimport the temperature file and save the session to apply these changes to an existing analysis.

## Download

**[macOS, Apple Silicon](https://github.com/bochens/Icescopy/releases/download/v2.6.4/Icescopy-macos-arm64.zip):** save your work and close Icescopy, unzip the download, then replace **Icescopy.app** in Applications. See [installation help](https://github.com/bochens/Icescopy/blob/main/wiki/Installation-and-Setup.md) if macOS blocks opening it.

**[Windows, x64](https://github.com/bochens/Icescopy/releases/download/v2.6.4/Icescopy-windows-installer.exe):** save your work and close Icescopy, then run the installer.
