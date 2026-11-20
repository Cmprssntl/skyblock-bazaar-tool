# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows / Linux）。

用法：
    pyinstaller deploy/skyblock-bazaar.spec
产物在 dist/SkyBlockBazaar/。
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "deploy" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "craft_recipe"), "craft_recipe"),
        (str(ROOT / "forge_recipe"), "forge_recipe"),
        (str(ROOT / "enchanted_book_recipe"), "enchanted_book_recipe"),
        (str(ROOT / "bazaar.ico"), "."),
        (str(ROOT / "bazaar.png"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "pytest_qt"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SkyBlockBazaar",
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
    icon=str(ROOT / "bazaar.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SkyBlockBazaar",
)
