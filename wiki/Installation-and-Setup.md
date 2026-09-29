# Installation and Setup

## Download the app

Download the version listed for your computer below. All releases are available on [GitHub Releases](https://github.com/bochens/Icescopy/releases). The packaged app includes Python and the libraries it needs; you do not need to install Python or conda to use it.

The Mac app is [v2.3.8](https://github.com/bochens/Icescopy/releases/tag/v2.3.8); the current Windows installer remains [v2.3.7](https://github.com/bochens/Icescopy/releases/tag/v2.3.7).

| Computer | Download |
| --- | --- |
| Windows 10 version 1809 or later, or Windows 11; 64-bit x64 | [Icescopy-windows-installer.exe](https://github.com/bochens/Icescopy/releases/download/v2.3.7/Icescopy-windows-installer.exe) — v2.3.7 |
| Mac with Apple Silicon | [Icescopy-macos-arm64.zip](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-macos-arm64.zip) — v2.3.8 |

These releases do not include an Intel Mac or Linux app download. GitHub's **Source code** downloads are the program's source files, not installers.

## Install on Windows

1. Download **Icescopy-windows-installer.exe**.
2. Close Icescopy if an older version is running.
3. Open the installer and follow its steps. It installs for your Windows account and normally does not need administrator access.
4. Open **Icescopy** from the Start menu, or use the desktop shortcut if you selected that option.

The default installation folder is `%LOCALAPPDATA%\Programs\Icescopy`. This build requires the Windows versions listed above and does not support 32-bit Windows. See the [release notes](https://github.com/bochens/Icescopy/releases/tag/v2.3.7) and [Windows installer details](../packaging/windows/README.md).

## Install on macOS

1. Download **Icescopy-macos-arm64.zip**.
2. Open the ZIP file to extract **Icescopy.app**.
3. Copy **Icescopy.app** to **Applications**. Close an older running copy before replacing it.
4. Open Icescopy from Applications.

macOS may ask for extra approval the first time you open this release. If you trust the downloaded copy, try opening it, then use **System Settings → Privacy & Security → Open Anyway** if that option appears. Follow [Apple's instructions for opening downloaded apps](https://support.apple.com/en-us/102445).

The current Mac download is for Apple Silicon only. See the [Mac release notes](https://github.com/bochens/Icescopy/releases/tag/v2.3.8) for changes and build details.

## Start an analysis

Open **File → New Session**, then add an image sequence or video recording. Temperature files are optional and can be imported after reviewing freeze events. Follow the [Quick Start](Quick-Start.md) for the full workflow.

Save sessions and exports in a writable folder of your choice. Keep them outside the installed application folder. The app saves preferences in your account's configuration folder, so normal preference changes do not modify the installation.

If a file cannot be saved, keep the session open and use the offered **Retry**, **Cancel**, or session **Save As** options. See [Troubleshooting](Troubleshooting.md) for save and startup problems.

## Optional: check a downloaded file

Each platform's release provides a checksum file, which contains a number you can compare with your download to check that it arrived unchanged:

- [SHA256SUMS.txt](https://github.com/bochens/Icescopy/releases/download/v2.3.7/SHA256SUMS.txt) covers the Windows v2.3.7 installer.
- [Icescopy-macos-arm64.zip.sha256](https://github.com/bochens/Icescopy/releases/download/v2.3.8/Icescopy-macos-arm64.zip.sha256) covers the Mac v2.3.8 ZIP file.

## Run from source

Use this section if you want to develop Icescopy or run the repository directly. Python 3.11 or newer is required. The conda environment below uses Python 3.11 and installs the project with its development tools.

From a terminal with Git and conda available:

```bash
git clone https://github.com/bochens/Icescopy.git
cd Icescopy
conda env create -f environment.yml
conda activate icescopy-dev
icescopy-validate
icescopy
```

If you already have the repository, start with `conda env create` from its root folder.

Alternatively, with a Python 3.11-or-newer environment already activated, run these commands from the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
icescopy-validate
icescopy
```

The `-e` option keeps the installed program connected to this checkout, so edits to the source take effect without reinstalling it. Keep the repository's `resources/` folder available.

## Check a development installation

`icescopy-validate` checks installed libraries, the package version, and required resources. Check video support separately with:

```bash
icescopy --check-video-dependencies
```

Run the automated tests from the repository root:

```bash
python run_tests.py
```

The main project folders are `src/` for application code, `resources/` for bundled assets and defaults, `tests/` for checks, and `wiki/` for documentation.

## Build a packaged app

Build on the target operating system with the development environment active.

On Windows:

```powershell
python -m PyInstaller --clean --noconfirm Icescopy.windows.spec
```

The output is `dist/Icescopy-windows/`. Keep `Icescopy.exe` and `_internal/` together. The build expects the runtime DLLs from the project's conda environment. Follow the [Windows packaging instructions](../packaging/windows/README.md) to create the installer.

On macOS:

```bash
python -m PyInstaller --clean --noconfirm Icescopy.spec
```

The app is written to `dist/Icescopy.app`. Follow the [macOS packaging instructions](../packaging/macos/README.md) for a separate release build, signing, and ZIP creation. The build changes files after PyInstaller's initial signing step, so those final signing instructions matter.

## Developer preference isolation

Bundled `resources/preferences.xml` supplies defaults. Saved preferences use `Icescopy/preferences.xml` inside the platform's user configuration directory. Set `ICESCOPY_CONFIG_DIR` to a separate directory when testing without changing your normal preferences.
