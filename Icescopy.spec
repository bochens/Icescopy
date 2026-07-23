# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import importlib.util
import shutil
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


project_root = Path(SPECPATH).resolve()
resources_dir = project_root / "resources"
app_icon = resources_dir / "app_icons" / "IcescopyApp.icns"
document_icon = resources_dir / "app_icons" / "IcescopyDocument.icns"
version_module_spec = importlib.util.spec_from_file_location(
    "icescopy_version",
    project_root / "src" / "icescopy_version.py",
)
version_module = importlib.util.module_from_spec(version_module_spec)
version_module_spec.loader.exec_module(version_module)
app_version = version_module.__version__

block_cipher = None


def patch_cv2_loader_configs(collect_root):
    collect_root = Path(collect_root)
    candidate_dirs = [
        collect_root / "cv2",
        collect_root / "_internal" / "cv2",
        collect_root / "Contents" / "Resources" / "cv2",
        collect_root / "Contents" / "Frameworks" / "cv2",
    ]

    for cv2_dir in candidate_dirs:
        if not cv2_dir.is_dir():
            continue

        config_path = cv2_dir / "config.py"
        if config_path.exists():
            config_path.write_text(
                "import os\n\n"
                "BINARIES_PATHS = [\n"
                "    os.path.join(LOADER_DIR, '.dylibs')\n"
                "] + BINARIES_PATHS\n",
                encoding="utf-8",
            )

        versioned_config_path = cv2_dir / f"config-{sys.version_info[0]}.{sys.version_info[1]}.py"
        if versioned_config_path.exists():
            versioned_config_path.write_text(
                "import os\n\n"
                "PYTHON_EXTENSIONS_PATHS = [\n"
                "    LOADER_DIR\n"
                "] + PYTHON_EXTENSIONS_PATHS\n",
                encoding="utf-8",
            )


def patch_glib_runtime_conflicts(collect_root):
    collect_root = Path(collect_root)
    runtime_dirs = [
        collect_root / "_internal",
        collect_root / "Contents" / "Frameworks",
        collect_root / "Contents" / "Resources",
    ]
    conda_lib_dir = Path(sys.prefix) / "lib"
    glib_runtime_names = [
        "libglib-2.0.0.dylib",
        "libgobject-2.0.0.dylib",
        "libpcre2-8.0.dylib",
        "libintl.8.dylib",
        "libiconv.2.dylib",
    ]

    for runtime_dir in runtime_dirs:
        if not runtime_dir.is_dir():
            continue
        for library_name in glib_runtime_names:
            source_path = conda_lib_dir / library_name
            target_path = runtime_dir / library_name
            if not source_path.exists() or not target_path.exists():
                continue
            if target_path.is_symlink() or target_path.is_file():
                target_path.unlink()
            shutil.copy2(source_path, target_path)


def optional_pyav_bundle_entries():
    if importlib.util.find_spec("av") is None:
        return [], []
    try:
        return collect_dynamic_libs("av"), collect_submodules("av")
    except Exception:
        return [], []


pyav_binaries, pyav_hiddenimports = optional_pyav_bundle_entries()

a = Analysis(
    ['src/Icescopy.py'],
    pathex=[str(project_root / 'src')],
    binaries=pyav_binaries,
    datas=[
        (str(resources_dir), 'resources'),
        (str(document_icon), '.'),
    ],
    hiddenimports=pyav_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Icescopy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='Icescopy',
)
patch_cv2_loader_configs(project_root / "dist" / "Icescopy")
patch_glib_runtime_conflicts(project_root / "dist" / "Icescopy")
app = BUNDLE(
    coll,
    name='Icescopy.app',
    icon=str(app_icon),
    bundle_identifier='org.icescopy.app',
    info_plist={
        'CFBundleIdentifier': 'org.icescopy.app',
        'CFBundleShortVersionString': app_version,
        'CFBundleVersion': app_version,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Icescopy Session',
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Owner',
                'CFBundleTypeExtensions': ['icescopy'],
                'CFBundleTypeIconFile': 'IcescopyDocument.icns',
            }
        ],
        'UTExportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'org.icescopy.session',
                'UTTypeDescription': 'Icescopy Session',
                'UTTypeConformsTo': ['public.data'],
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['icescopy'],
                },
            }
        ],
    },
)
patch_cv2_loader_configs(project_root / "dist" / "Icescopy")
patch_cv2_loader_configs(project_root / "dist" / "Icescopy.app")
patch_glib_runtime_conflicts(project_root / "dist" / "Icescopy")
patch_glib_runtime_conflicts(project_root / "dist" / "Icescopy.app")
