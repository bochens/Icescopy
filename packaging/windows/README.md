# Windows installer

`Icescopy.iss` packages a completed Windows PyInstaller folder with Inno Setup 6.7.3. It installs for the current user in `%LOCALAPPDATA%\Programs\Icescopy`, provides a Start Menu shortcut and an optional desktop shortcut, and registers the standard Inno uninstaller. The installer requires Windows 10 version 1809 (build 17763) or later, or Windows 11, on an x64-compatible system. It does not close or restart applications; close Icescopy before upgrading or uninstalling.

The complete bundle, including `_internal`, is copied. Upgrades remove only two known obsolete ICU files, and only when the target already contains Icescopy and its Qt runtime. Uninstall removes files recorded by Inno; there is no recursive deletion of the selected installation folder. User preferences and session files are not installer cleanup targets. This installer does not change `.icescopy` associations or migrate the older machine-wide custom installer.

## Build

First build and validate the versioned application with `Icescopy.windows.spec`. `SourceDir` must be the resulting directory containing `Icescopy.exe` and `_internal`; `OutputDir` is the release asset directory. Pass the same version as `src/icescopy_version.py`.

The compiler can be kept in a project-local portable installation; no global installation is required. From the repository root, for example:

```powershell
& 'F:\Icescopy\tools\innosetup-6.7.3\ISCC.exe' `
    '/DAppVersion=2.3.7' `
    '/DSourceDir=F:\Icescopy\dist\v2.3.7\Icescopy-windows' `
    '/DOutputDir=F:\Icescopy\dist\v2.3.7' `
    '.\packaging\windows\Icescopy.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
```

The output is `Icescopy-windows-installer.exe`. Use the app's bundled ICO for the setup executable and `Icescopy.exe` for installed shortcut and uninstall icons. Signing is not configured by this script.

## Isolated smoke installation

The following uses a disposable application directory and disables both shortcut types. It still creates a normal current-user uninstall registration; uninstall it when finished so later installs do not inherit the smoke directory.

```powershell
New-Item -ItemType Directory -Path 'F:\Icescopy\tmp' -Force | Out-Null
$smokeInstall = Start-Process `
    -FilePath 'F:\Icescopy\dist\v2.3.7\Icescopy-windows-installer.exe' `
    -WindowStyle Hidden -Wait -PassThru `
    -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART',
        '/NOCLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS',
        '/DIR=F:\Icescopy\tmp\installer-smoke-v2.3.7',
        '/GROUP=Icescopy-Smoke-2.3.7', '/NOICONS', '/TASKS=',
        '/LOG=F:\Icescopy\tmp\installer-smoke-v2.3.7-install.log'
    )
if ($smokeInstall.ExitCode -ne 0) { throw "Smoke install failed: $($smokeInstall.ExitCode)" }
```

Verify the installed application's startup and preferences with an isolated `ICESCOPY_CONFIG_DIR`, and close it before uninstalling. To exercise cleanup, place a harmless extra file in the smoke directory and check that uninstall leaves it intact.

```powershell
$smokeUninstall = Start-Process `
    -FilePath 'F:\Icescopy\tmp\installer-smoke-v2.3.7\unins000.exe' `
    -WindowStyle Hidden -Wait -PassThru `
    -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        '/LOG=F:\Icescopy\tmp\installer-smoke-v2.3.7-uninstall.log'
    )
if ($smokeUninstall.ExitCode -ne 0) { throw "Smoke uninstall failed: $($smokeUninstall.ExitCode)" }
```

## Official references

- [Compiler and preprocessor parameters](https://jrsoftware.org/ishelp/topic_compilercmdline.htm)
- [Setup command-line parameters](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)
- [Current-user privileges](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)
- [Architecture selection](https://jrsoftware.org/ishelp/topic_setup_architecturesallowed.htm)
- [Application closing behavior](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm)
- [Optional Start Menu shortcuts](https://jrsoftware.org/ishelp/topic_setup_allownoicons.htm)
- [File deletion and uninstall guidance](https://jrsoftware.org/ishelp/topic_uninstalldeletesection.htm)
