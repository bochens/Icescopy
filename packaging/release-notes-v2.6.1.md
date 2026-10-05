# Icescopy 2.6.1

For INP concentration calculations, use **[INP-toolkit 0.4.4](https://github.com/bochens/inptk/releases/tag/v0.4.4)**. Install it separately and select its executable in **Preferences → INP toolkit client**.

- Compare the combined MLE result with directly calculated individual dilution concentrations and sample/blank binomial uncertainty.
- Mark water blanks in the sample catalog. Blank correction uses their counts and well volumes; unrelated dilution and air/soil fields are ignored.
- Set shared water-blank temperature limits and optionally apply correction only after the first blank freezes.
- Full range and manual limits follow the toolkit's calculation grid. Dragging one range endpoint preserves the other.
- The plot stays in place when switching between Samples, Combine, and Advanced.

## Downloads

- **Windows 10 (1809 or later) / 11, x64:** run `Icescopy-windows-installer.exe`.
- **macOS, Apple Silicon:** unzip `Icescopy-macos-arm64.zip` and move **Icescopy.app** to **Applications**.

The macOS app is ad-hoc signed, not notarized. If macOS blocks it, see the [opening instructions](https://github.com/bochens/Icescopy/blob/v2.6.1/wiki/Installation-and-Setup.md#install-on-macos).

Save your work and close Icescopy before installing the update.
