# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve()
resources_dir = project_root / "resources"
app_icon = resources_dir / "app_icons" / "IcescopyApp.icns"
document_icon = resources_dir / "app_icons" / "IcescopyDocument.icns"

block_cipher = None


a = Analysis(
    ['src/Icescopy.py'],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(resources_dir), 'resources'),
        (str(document_icon), '.'),
    ],
    hiddenimports=[],
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
app = BUNDLE(
    coll,
    name='Icescopy.app',
    icon=str(app_icon),
    bundle_identifier='org.icescopy.app',
    info_plist={
        'CFBundleIdentifier': 'org.icescopy.app',
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
