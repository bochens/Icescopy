# macOS release packaging

Build on an Apple Silicon Mac with the project's Python environment. The v2.3.7 archive was built from tag `v2.3.7` (commit `534de72a354b759448ceb07ef6541fd49024c153`) using Python 3.11.15, PyInstaller 6.19.0, PySide6 6.11.0, and PyAV 17.0.1.

## Build an exact release without replacing older local builds

From a clean repository checkout with the intended tag available, activate the project environment, then create a separate source snapshot:

```sh
release_build=$(mktemp -d "$TMPDIR/icescopy-v2.3.7.XXXXXX")
git archive v2.3.7 | tar -x -C "$release_build"
cd "$release_build"
PYINSTALLER_CONFIG_DIR="$release_build/pyinstaller-cache" python -m PyInstaller --clean --noconfirm Icescopy.spec
```

Keep the default `build/` and `dist/` directories inside this snapshot. `Icescopy.spec` currently patches files at those locations; changing only PyInstaller's `--distpath` would miss those patches.

The spec adjusts OpenCV configuration and GLib libraries after PyInstaller signs the app. Those changes invalidate the earlier signature. For an ad-hoc build, sign the finished bundle again and verify it before archiving:

```sh
codesign --force --deep --sign - dist/Icescopy.app
codesign --verify --deep --strict dist/Icescopy.app
file dist/Icescopy.app/Contents/MacOS/Icescopy
plutil -extract CFBundleShortVersionString raw -o - dist/Icescopy.app/Contents/Info.plist
dist/Icescopy.app/Contents/MacOS/Icescopy --check-video-dependencies
```

Ad-hoc signing verifies bundle integrity; it is not an Apple Developer ID signature or notarization. Do not describe this build as notarized or as an Intel/universal binary.

## Archive and verify

Use `ditto` so the app's symbolic links and metadata survive packaging:

```sh
ditto -c -k --sequesterRsrc --keepParent dist/Icescopy.app Icescopy-macos-arm64.zip
shasum -a 256 Icescopy-macos-arm64.zip > Icescopy-macos-arm64.zip.sha256
ditto -x -k Icescopy-macos-arm64.zip archive-check
codesign --verify --deep --strict archive-check/Icescopy.app
```

Also check ZIP integrity and confirm that the archive contains only the app, not test settings, logs, or local research files. Upload the archive and its checksum to the matching existing release. Preserve the Windows installer and its checksum asset; do not move the release tag to a later documentation/test commit.

## v2.3.7 validation and limitations

- The application source in the archive matches `v2.3.7`; the subsequent test fixes do not change the application.
- The macOS suite passed 164 tests, with the Windows-only file-lock test skipped. The original suite expected message-box titles that macOS intentionally ignores, and used F2 to start table editing. Tests now check visible recovery instructions and open the editor through Qt's table API while retaining the pending-edit Save/Cancel checks.
- Verified arm64 executable, version 2.3.7, PyAV dependency import, ZIP integrity, and the extracted app's ad-hoc signature.
- Native startup and Preferences Save/Cancel closing were observed. The GUI check did not establish changed-value persistence through a packaged-app restart. The automated preference tests cover saving/reopening values and application failures separately.
- The packaged dependency check prints duplicate AVFoundation receiver warnings from the OpenCV and PyAV libraries. No library was removed to hide the warnings; full video analysis and live camera/audio capture were not validated in this build check.
- macOS desktop-service access is needed for native testing; a command sandbox can fail before normal startup. Keep a single identified test process and use an isolated `ICESCOPY_CONFIG_DIR`. Confirm the UI targets that process before changing values; identifying an app only by its bundle name can select another instance.

The temporary Windows-agent README has been retired. The Windows investigation and recovery details remain in `wiki/Windows-Preferences-Investigation.md` and `wiki/Windows-Save-Recovery.md`.
