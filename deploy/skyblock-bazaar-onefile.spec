# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 单文件配置（Windows）。

用法：
    pyinstaller deploy/skyblock-bazaar-onefile.spec
产物是 dist/SkyBlockBazaar.exe。
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
    a.binaries,
    a.datas,
    [],
    name="SkyBlockBazaar",
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
    icon=str(ROOT / "bazaar.ico"),
    version=str(ROOT / "deploy" / "version_info.txt"),
)
