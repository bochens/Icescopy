# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


project_root = Path(SPECPATH).resolve()
resources_dir = project_root / "resources"
app_icon = resources_dir / "app_icons" / "IcescopyApp.ico"
env_root = Path(sys.prefix).resolve()
runtime_dll_dirs = [
    env_root / "Library" / "bin",
    env_root / "DLLs",
]
runtime_dll_names = [
    "ffi.dll",
    "sqlite3.dll",
    "libssl-3-x64.dll",
    "libcrypto-3-x64.dll",
    "libexpat.dll",
    "liblzma.dll",
    "libbz2.dll",
]


def resolve_runtime_dll(name):
    for dll_dir in runtime_dll_dirs:
        candidate = dll_dir / name
        if candidate.exists():
            return candidate
    return None


resolved_runtime_dlls = []
missing_runtime_dlls = []
for dll_name in runtime_dll_names:
    dll_path = resolve_runtime_dll(dll_name)
    if dll_path is None:
        missing_runtime_dlls.append(dll_name)
    else:
        resolved_runtime_dlls.append((str(dll_path), "."))

if missing_runtime_dlls:
    raise FileNotFoundError(
        "Missing required Windows runtime DLLs: " + ", ".join(sorted(missing_runtime_dlls))
    )

block_cipher = None


a = Analysis(
    ["src/Icescopy.py"],
    pathex=[str(project_root / "src")],
    binaries=resolved_runtime_dlls + collect_dynamic_libs("av"),
    datas=[
        (str(resources_dir), "resources"),
    ],
    hiddenimports=collect_submodules("av"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "rthook_windows_dll_path.py")],
    excludes=["matplotlib", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
# Qt 6.11 uses the Windows ICU API. A same-named ICU DLL on PATH
# (for example from Poppler/Conda) can expose only versioned symbols and
# shadow the system library, preventing QtWidgets from importing.
a.binaries = [
    entry for entry in a.binaries
    if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Icescopy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(app_icon)],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Icescopy-windows",
)
