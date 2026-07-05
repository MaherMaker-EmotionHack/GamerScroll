# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

root = Path(SPECPATH).resolve()

a = Analysis(
    [str(root / 'gamerscroll' / '__main__.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'assets' / 'icon.ico'), 'assets'),
    ],
    hiddenimports=[
        'win32api',
        'win32con',
        'win32gui',
        'winreg',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'loguru',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GamerScroll',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets' / 'icon.ico'),
)
