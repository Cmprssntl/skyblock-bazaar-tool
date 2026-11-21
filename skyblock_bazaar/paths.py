"""运行时路径：源码、PyInstaller 冻结包、以及可覆盖的数据目录。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根目录（源码运行时）或 PyInstaller 解包目录（_MEIPASS）
SOURCE_DIR = Path(__file__).resolve().parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR)) if getattr(sys, "frozen", False) else SOURCE_DIR

# exe 所在目录（冻结包）或源码根目录
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR


def default_data_dir() -> Path:
    """优先把数据放在程序旁边；系统安装目录不可写时退回用户数据目录。"""
    if os.access(BASE_DIR, os.W_OK):
        return BASE_DIR / "bazaar_config"
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "skyblock-bazaar" / "bazaar_config"


DATA_DIR = Path(os.environ.get("SBZ_DATA_DIR") or default_data_dir())

RECIPE_DIRS = {
    "craft": RESOURCE_DIR / "craft_recipe" / "items",
    "forge": RESOURCE_DIR / "forge_recipe",
    "enchant": RESOURCE_DIR / "enchanted_book_recipe",
}


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def data_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)


def parse_geometry(text: str | None) -> dict | None:
    """解析旧版 Tk 的 "1050x700+100+80" 位置字符串。"""
    if not text:
        return None
    try:
        size, _, rest = text.partition("+")
        width, height = (int(v) for v in size.split("x")[:2])
        x_text, _, y_text = rest.partition("+")
        return {"w": width, "h": height, "x": int(x_text), "y": int(y_text)}
    except (ValueError, AttributeError):
        return None
