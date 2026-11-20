"""配置：单文件 settings.json，原子写入，并兼容迁移 v3.5 的四个旧配置文件。"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import DATA_DIR, data_path, parse_geometry

CONFIG_VERSION = 2
PAGE_KEYS = ("bazaar", "craft", "forge", "enchant")
LEGACY_FILES = {
    "bazaar": "bazaar_config.json",
    "craft": "craft_config.json",
    "forge": "forge_config.json",
    "enchant": "enchant_config.json",
}
DEFAULT_BUTTON_ORDER = [
    "refresh",
    "refresh_bazaar",
    "refresh_auction",
    "param",
    "save",
    "load",
    "reset",
    "search",
    "record",
    "auto",
    "topmost",
    "shortcut",
    "api",
]


@dataclass
class ColumnSettings:
    visible: bool = True
    width: int = 115
    unit: str = "默认"
    minimum: str = ""
    maximum: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> ColumnSettings:
        if not isinstance(value, dict):
            return cls()
        return cls(
            visible=bool(value.get("visible", True)),
            width=_as_int(value.get("width"), 115),
            unit=_normalize_unit(value.get("unit", "默认")),
            minimum=str(value.get("minimum", "") or ""),
            maximum=str(value.get("maximum", "") or ""),
        )

    def to_dict(self) -> dict:
        return {
            "visible": self.visible,
            "width": self.width,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


@dataclass
class PageSettings:
    columns: dict[str, ColumnSettings] = field(default_factory=dict)
    column_order: list[str] = field(default_factory=list)
    sort_key: str = ""
    sort_reverse: bool = True
    sources: dict[str, bool] = field(default_factory=lambda: {"bazaar": True, "auction": True})

    def column(self, cid: str, width: int = 115) -> ColumnSettings:
        item = self.columns.get(cid)
        if item is None:
            item = ColumnSettings(width=width)
            self.columns[cid] = item
        return item

    @classmethod
    def from_dict(cls, value: Any) -> PageSettings:
        value = value if isinstance(value, dict) else {}
        sources = value.get("sources", {})
        return cls(
            columns={
                str(cid): ColumnSettings.from_dict(item)
                for cid, item in (value.get("columns") or {}).items()
            },
            column_order=[str(cid) for cid in value.get("column_order") or []],
            sort_key=str(value.get("sort_key") or ""),
            sort_reverse=bool(value.get("sort_reverse", True)),
            sources={
                "bazaar": bool(sources.get("bazaar", True)),
                "auction": bool(sources.get("auction", True)),
            },
        )

    def to_dict(self) -> dict:
        return {
            "columns": {cid: item.to_dict() for cid, item in self.columns.items()},
            "column_order": list(self.column_order),
            "sort_key": self.sort_key,
            "sort_reverse": self.sort_reverse,
            "sources": dict(self.sources),
        }


@dataclass
class ShortcutBinding:
    sequence: str = ""
    global_hotkey: bool = False

    @classmethod
    def from_dict(cls, value: Any) -> ShortcutBinding:
        if isinstance(value, str):
            return cls(sequence=value)
        if not isinstance(value, dict):
            return cls()
        return cls(
            sequence=str(value.get("sequence", "") or ""),
            global_hotkey=bool(value.get("global", False)),
        )

    def to_dict(self) -> dict:
        return {"sequence": self.sequence, "global": self.global_hotkey}


DEFAULT_WATCHLIST = ["ENCHANTED_DIAMOND", "ENCHANTED_LAPIS_LAZULI", "BOOSTER_COOKIE"]


@dataclass
class HistorySettings:
    enabled: bool = True
    auto_refresh: bool = True
    interval_sec: int = 60
    retention_days: int = 90
    watchlist: list[str] = field(default_factory=lambda: list(DEFAULT_WATCHLIST))

    @classmethod
    def from_dict(cls, value: Any) -> HistorySettings:
        value = value if isinstance(value, dict) else {}
        raw = value.get("watchlist") if "watchlist" in value else list(DEFAULT_WATCHLIST)
        items = [str(item).strip().upper() for item in raw or [] if str(item).strip()]
        return cls(
            enabled=bool(value.get("enabled", True)),
            auto_refresh=bool(value.get("auto_refresh", True)),
            interval_sec=max(15, _as_int(value.get("interval_sec"), 60)),
            retention_days=max(1, _as_int(value.get("retention_days"), 90)),
            watchlist=list(dict.fromkeys(items)),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "auto_refresh": self.auto_refresh,
            "interval_sec": self.interval_sec,
            "retention_days": self.retention_days,
            "watchlist": list(self.watchlist),
        }


@dataclass
class AppSettings:
    version: int = CONFIG_VERSION
    api_key: str = ""
    theme: str = "dark"
    topmost: bool = False
    active_page: str = "bazaar"
    window: dict = field(default_factory=lambda: {"w": 1500, "h": 860, "x": None, "y": None, "maximized": False})
    button_order: list[str] = field(default_factory=lambda: list(DEFAULT_BUTTON_ORDER))
    shortcuts: dict[str, ShortcutBinding] = field(
        default_factory=lambda: {"search": ShortcutBinding(sequence="CTRL+F")}
    )
    pages: dict[str, PageSettings] = field(default_factory=lambda: {key: PageSettings() for key in PAGE_KEYS})
    history: HistorySettings = field(default_factory=HistorySettings)
    dialogs: dict[str, dict] = field(default_factory=dict)

    def page(self, key: str) -> PageSettings:
        page = self.pages.get(key)
        if page is None:
            page = PageSettings()
            self.pages[key] = page
        return page

    def shortcut(self, action: str) -> ShortcutBinding:
        return self.shortcuts.setdefault(action, ShortcutBinding())

    @classmethod
    def from_dict(cls, value: Any) -> AppSettings:
        value = value if isinstance(value, dict) else {}
        pages = {}
        raw_pages = value.get("pages") or {}
        for key in PAGE_KEYS:
            pages[key] = PageSettings.from_dict(raw_pages.get(key))
        settings = cls(
            version=_as_int(value.get("version"), CONFIG_VERSION),
            api_key=str(value.get("api_key", "") or ""),
            theme=str(value.get("theme", "dark") or "dark"),
            topmost=bool(value.get("topmost", False)),
            active_page=str(value.get("active_page", "bazaar") or "bazaar"),
            window=_merge_window(value.get("window")),
            button_order=[str(b) for b in value.get("button_order") or DEFAULT_BUTTON_ORDER],
            shortcuts={
                str(action): ShortcutBinding.from_dict(item)
                for action, item in (value.get("shortcuts") or {}).items()
            },
            pages=pages,
            history=HistorySettings.from_dict(value.get("history")),
            dialogs={
                str(name): item for name, item in (value.get("dialogs") or {}).items() if isinstance(item, dict)
            },
        )
        settings.shortcuts.setdefault("search", ShortcutBinding(sequence="CTRL+F"))
        return settings

    def to_dict(self) -> dict:
        return {
            "version": CONFIG_VERSION,
            "api_key": self.api_key,
            "theme": self.theme,
            "topmost": self.topmost,
            "active_page": self.active_page,
            "window": dict(self.window),
            "button_order": list(self.button_order),
            "shortcuts": {action: item.to_dict() for action, item in self.shortcuts.items()},
            "pages": {key: page.to_dict() for key, page in self.pages.items()},
            "history": self.history.to_dict(),
            "dialogs": copy.deepcopy(self.dialogs),
        }


class ConfigStore:
    """读写 settings.json；首次运行时从 v3.5 的四个配置文件迁移。"""

    def __init__(self, path: Path | None = None, legacy_dir: Path | None = None):
        self.path = path or data_path("settings.json")
        self.legacy_dir = legacy_dir or DATA_DIR

    def load(self) -> AppSettings:
        if self.path.is_file():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    return AppSettings.from_dict(json.load(fh))
            except (OSError, ValueError):
                # 损坏时保留备份，退回默认值
                try:
                    self.path.replace(self.path.with_suffix(".json.broken"))
                except OSError:
                    pass
        settings = self.migrate()
        try:
            self.save(settings)
        except OSError:
            pass
        return settings

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------ 迁移
    def migrate(self) -> AppSettings:
        settings = AppSettings()
        if not self.legacy_dir.is_dir():
            return settings

        shortcuts: dict[str, ShortcutBinding] = {}
        for page_key in PAGE_KEYS:
            path = self.legacy_dir / LEGACY_FILES[page_key]
            data = _read_json(path)
            if not isinstance(data, dict):
                continue
            page = _migrate_page(data)
            settings.pages[page_key] = page

            if not settings.api_key and isinstance(data.get("api_key"), str):
                settings.api_key = data["api_key"]

            # 快捷键取任意一份非空配置
            if not shortcuts and isinstance(data.get("shortcut_map"), dict):
                globals_map = data.get("shortcut_global") or {}
                for action, sequence in data["shortcut_map"].items():
                    if sequence:
                        shortcuts[str(action)] = ShortcutBinding(
                            sequence=str(sequence),
                            global_hotkey=bool(globals_map.get(action, False)),
                        )
            if page_key == "bazaar":
                if isinstance(data.get("btn_order"), list):
                    settings.button_order = [str(b) for b in data["btn_order"]]
                window = data.get("window")
                if isinstance(window, dict) and window.get("w") and window.get("h"):
                    settings.window = _merge_window(window)
                settings.topmost = bool(data.get("is_topmost", False))
                if data.get("setting_win_geometry"):
                    settings.dialogs["param"] = parse_geometry(str(data["setting_win_geometry"])) or {}
                if data.get("shortcut_win_geometry"):
                    settings.dialogs["shortcut"] = parse_geometry(str(data["shortcut_win_geometry"])) or {}
                if data.get("search_win_geometry"):
                    settings.dialogs["search"] = parse_geometry(str(data["search_win_geometry"])) or {}

        if "search" not in shortcuts:
            shortcuts["search"] = ShortcutBinding(sequence="CTRL+F")
        settings.shortcuts = shortcuts
        return settings


def _migrate_page(data: dict) -> PageSettings:
    page = PageSettings()
    columns = data.get("columns") if isinstance(data.get("columns"), dict) else {}
    widths = data.get("col_widths") if isinstance(data.get("col_widths"), dict) else {}
    mins = data.get("filter_min") if isinstance(data.get("filter_min"), dict) else {}
    maxs = data.get("filter_max") if isinstance(data.get("filter_max"), dict) else {}
    units = data.get("units") if isinstance(data.get("units"), dict) else {}
    for cid, visible in columns.items():
        page.columns[str(cid)] = ColumnSettings(
            visible=bool(visible),
            width=_as_int(widths.get(cid), 115),
            unit=_normalize_unit(units.get(cid, "默认")),
            minimum=str(mins.get(cid, "") or ""),
            maximum=str(maxs.get(cid, "") or ""),
        )
    # 只记录了宽度、没有勾选记录的列也要保留宽度
    for cid, width in widths.items():
        page.column(str(cid)).width = _as_int(width, 115)

    if isinstance(data.get("col_order"), list):
        page.column_order = [str(cid) for cid in data["col_order"]]
    sort = data.get("sort") if isinstance(data.get("sort"), dict) else {}
    if sort.get("key"):
        page.sort_key = str(sort["key"])
        page.sort_reverse = bool(sort.get("reverse", True))
    sources = data.get("filter_sources")
    if isinstance(sources, dict):
        page.sources = {
            "bazaar": bool(sources.get("bazaar", True)),
            "auction": bool(sources.get("auction", True)),
        }
    return page


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _normalize_unit(value: Any) -> str:
    text = str(value or "默认")
    if text in {"M", "m"}:
        return "m"
    if text in {"B", "b"}:
        return "b"
    if text in {"K", "k"}:
        return "k"
    return "默认"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _merge_window(value: Any) -> dict:
    base = {"w": 1500, "h": 860, "x": None, "y": None, "maximized": False}
    if isinstance(value, dict):
        for key in ("w", "h", "x", "y"):
            if value.get(key) is not None:
                base[key] = _as_int(value.get(key), base[key])
        base["maximized"] = bool(value.get("maximized", False))
    return base
