# Icescopy 2.3.8

This release updates the Windows app and the macOS app for Apple Silicon.

## Fixes

- Keep the Grayscale Plot's current-frame marker aligned with the selected frame when the plot scale or size changes.
- Keep toolbar tool selections and one-, two-, or three-image views synchronized with the active mode, including changes made through accessibility controls.

The README and user guide also include updated workflow instructions and screenshots.

## Windows download

Download [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-windows-installer.exe) for 64-bit x64 Windows 10 (1809 or later) or Windows 11. Run the installer, which installs for your Windows account, then open Icescopy from the Start menu. Python and the required libraries are included.

The matching [Icescopy-windows-installer.exe.sha256](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-windows-installer.exe.sha256) file provides the download checksum.

Windows verification: 173 automated tests passed. Installation, upgrade, uninstall, and packaged dependency checks passed using a disposable installation.

## Mac download

Download **Icescopy-macos-arm64.zip**, extract it, and copy **Icescopy.app** to **Applications**. This build is for Apple Silicon Macs; no Intel Mac binary is included. The matching **Icescopy-macos-arm64.zip.sha256** file provides the download checksum.

macOS may ask for extra approval on first launch. See the [installation guide](https://github.com/bochens/Icescopy/blob/v2.3.8/wiki/Installation-and-Setup.md#install-on-macos).
