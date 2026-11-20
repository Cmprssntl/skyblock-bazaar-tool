"""配置：v3.5 迁移、原子写、缺失键容错。"""

from __future__ import annotations

import json

from skyblock_bazaar.config import ConfigStore, ShortcutBinding


def _legacy_payload() -> dict:
    return {
        "window": {"w": 1400, "h": 700, "x": 10, "y": 20},
        "sort": {"key": "pct", "reverse": True},
        "col_order": ["name", "buy", "pct"],
        "btn_order": ["refresh", "api"],
        "shortcut_map": {"search": "CTRL+F", "refresh": "F5"},
        "shortcut_global": {"refresh": True},
        "is_topmost": True,
        "col_widths": {"name": 240, "buy": 95},
        "columns": {"name": True, "buy": False, "pct": True},
        "filter_min": {"buy": "1k", "pct": ""},
        "filter_max": {"buy": "", "pct": "50"},
        "units": {"buy": "K", "pct": "默认"},
        "filter_sources": {"bazaar": True, "auction": False},
        "setting_win_geometry": "1050x700+100+80",
        "search_win_geometry": "430x190+5+6",
        "api_key": "secret-key",
    }


def test_migrate_from_v35(tmp_path):
    (tmp_path / "bazaar_config.json").write_text(json.dumps(_legacy_payload()), encoding="utf-8")
    store = ConfigStore(path=tmp_path / "settings.json", legacy_dir=tmp_path)
    settings = store.load()

    assert settings.api_key == "secret-key"
    assert settings.topmost is True
    assert settings.window["w"] == 1400
    assert settings.button_order == ["refresh", "api"]

    page = settings.page("bazaar")
    assert page.sort_key == "pct" and page.sort_reverse is True
    assert page.column_order == ["name", "buy", "pct"]
    assert page.sources == {"bazaar": True, "auction": False}
    assert page.column("buy").visible is False
    assert page.column("buy").width == 95
    assert page.column("buy").unit == "k"  # 旧配置的 K 归一化为小写
    assert page.column("buy").minimum == "1k"
    assert page.column("pct").maximum == "50"

    assert settings.shortcuts["refresh"] == ShortcutBinding(sequence="F5", global_hotkey=True)
    assert settings.shortcuts["search"].sequence == "CTRL+F"
    assert settings.dialogs["param"]["w"] == 1050
    assert settings.dialogs["search"]["x"] == 5

    # 迁移结果可原子保存并原样读回
    store.save(settings)
    again = store.load()
    assert again.api_key == settings.api_key
    assert again.page("bazaar").column("buy").unit == "k"
    assert again.shortcuts["refresh"].global_hotkey is True


def test_corrupt_config_falls_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    store = ConfigStore(path=path, legacy_dir=tmp_path)
    settings = store.load()
    assert settings.api_key == ""
    assert settings.shortcuts["search"].sequence == "CTRL+F"
    assert path.with_suffix(".json.broken").exists()


def test_missing_keys_get_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"pages": {"craft": {"sort_key": "sell_mat_sell"}}}), encoding="utf-8")
    settings = ConfigStore(path=path, legacy_dir=tmp_path).load()
    assert settings.page("craft").sort_key == "sell_mat_sell"
    assert settings.page("bazaar").sources == {"bazaar": True, "auction": True}
    assert settings.history.interval_sec == 60
    assert settings.history.auto_refresh is True
