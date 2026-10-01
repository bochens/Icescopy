# Installation and Setup

Install a packaged app to use Icescopy without installing Python. Use a source checkout if you want to develop the application.

## Download the app

Use the release for your platform. All releases and their notes are on [GitHub Releases](https://github.com/bochens/Icescopy/releases).

| Computer | Download | Version |
| --- | --- | --- |
| Windows 10 version 1809 or later, or Windows 11; 64-bit x64 | [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-windows-installer.exe) | 2.3.8 |
| Mac with Apple Silicon (M-series) | [Icescopy-macos-arm64.zip](https://github.com/bochens/Icescopy/releases/download/v2.4.0/Icescopy-macos-arm64.zip) | 2.4.0 |

These releases do not include an Intel Mac or Linux app. Windows x64 means 64-bit Intel/AMD Windows. The Mac arm64 download targets Apple Silicon. GitHub's **Source code** ZIP/TAR downloads contain program source, not an installer.

The Mac download is **2.4.0**; the Windows download remains **2.3.8** until a new Windows installer is published. Check platform-specific assets when installing a release; a release need not contain a build for every platform.

## Install on Windows

1. Download **Icescopy-windows-installer.exe** from the link above.
2. Save any open work and close an older running copy of Icescopy.
3. Open the installer and follow its steps. It installs for your Windows account and normally does not require administrator access.
4. Open **Icescopy** from the Start menu or the desktop shortcut, if selected during installation.
5. Open **About** and check the installed version.

The default destination is `%LOCALAPPDATA%\Programs\Icescopy`. Keep session files and exports in your own writable analysis folders, outside the application directory.

For the installation layout and maintainer build steps, see [Windows packaging](../packaging/windows/README.md). This release does not support 32-bit Windows.

## Install on macOS

1. Download **Icescopy-macos-arm64.zip**.
2. Open the ZIP to extract **Icescopy.app**.
3. Save any open work and close an older running copy.
4. Copy **Icescopy.app** to **Applications**. Keep a copy of the previous app before replacing it if you need to return to that version.
5. Open Icescopy from Applications, then check **About Icescopy**.

The Mac build is signed locally for bundle integrity. It does not have an Apple Developer ID signature or Apple notarization. macOS may therefore require extra approval on first launch. If you trust the downloaded copy, try opening it, then use **System Settings → Privacy & Security → Open Anyway** when offered. Follow [Apple's downloaded-app instructions](https://support.apple.com/en-us/102445).

Do not use the Apple Silicon app on an Intel Mac. See [macOS release notes](https://github.com/bochens/Icescopy/releases/tag/v2.4.0) and [packaging details](../packaging/macos/README.md).

## Upgrade without losing earlier analyses

Application files, user Preferences, and analysis files are separate.

1. Save the active session and retain the previous app or installer.
2. Close the app before replacing or updating it.
3. Install the new build for your platform.
4. Open a copy of a saved session and inspect the source frames, cell positions, and result tables.
5. Use **Save Session As...** for work you continue in the new version.

Installing a new app does not bundle or move your source images/videos. Do not delete original recordings after saving a session. Retain a copy of important Preferences and record the version/settings used for published results; global detector settings are not all stored in the session.

## Optional: check a downloaded file

A checksum is a number calculated from a file's bytes. Matching the release checksum verifies that the download is unchanged; it does not replace trusting the release's source.

Download the matching checksum:

- Windows 2.3.8: [Icescopy-windows-installer.exe.sha256](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-windows-installer.exe.sha256).
- macOS 2.4.0: [Icescopy-macos-arm64.zip.sha256](https://github.com/bochens/Icescopy/releases/download/v2.4.0/Icescopy-macos-arm64.zip.sha256).

On Windows, open PowerShell in the download folder:

```powershell
Get-FileHash .\Icescopy-windows-installer.exe -Algorithm SHA256
```

Compare the hash with the installer's entry in `Icescopy-windows-installer.exe.sha256`, ignoring letter case.

On macOS, with the ZIP and checksum in the same folder:

```bash
shasum -a 256 -c Icescopy-macos-arm64.zip.sha256
```

Expected result: `Icescopy-macos-arm64.zip: OK`. If it does not match, download both files from the same release again before installing.

## Start an analysis

1. Choose **File → New Session**.
2. Enter the session information and load an image sequence or video source.
3. Confirm the order, draw cells, and follow [Quick Start](Quick-Start.md).

Temperature input is optional for brightness and freeze-event review. Add it afterward if you need temperature-aligned counts.

Save sessions and exports in a writable folder. If saving fails, keep the session open and use the offered recovery options; see [save troubleshooting](Troubleshooting.md#cannot-save-a-session-preferences-or-csv).

## Run from source

Python 3.11 or newer is required. The provided conda environment uses Python 3.11. With Git and conda available:

```bash
git clone https://github.com/bochens/Icescopy.git
cd Icescopy
conda env create -f environment.yml
conda activate icescopy-dev
icescopy-validate
icescopy
```

An editable install keeps the installed program connected to the checkout so code edits take effect without reinstalling. Keep the repository's `resources/` directory with the source. See [Developer Guide](Developer-Guide.md) for an existing Python environment, the source layout, and development practices.

The development source includes experimental [droplet detection](Droplet-Detection.md). The bundled model detects cells in the current image or video frame; selected cells guide its appearance and size.

## Check a development installation

Run `icescopy-validate` and `icescopy --check-video-dependencies` in the active environment. They check installation/resources and the video dependency import; they do not validate an experimental result or exercise every GUI operation.

See [Developer Guide](Developer-Guide.md) for automated checks and targeted native-app validation.

## Build a packaged app

Build on the target operating system. Follow [Windows packaging](../packaging/windows/README.md) or [macOS packaging](../packaging/macos/README.md), including the final signing and archive checks. Keep new build outputs separate from older releases.

## Developer preference isolation

Set `ICESCOPY_CONFIG_DIR` to a separate directory for a test run. This directs the app to test Preferences instead of your normal saved configuration. [Developer Guide](Developer-Guide.md) provides commands.

Related: [Quick Start](Quick-Start.md) · [Sessions, Export, and Preferences](Sessions-Export-and-Preferences.md) · [Troubleshooting](Troubleshooting.md)
