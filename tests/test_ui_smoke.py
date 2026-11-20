"""界面冒烟：offscreen 下创建页面、套用快照、渲染 K 线。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skyblock_bazaar.config import HistorySettings, PageSettings
from skyblock_bazaar.data.library import RecipeLibrary
from skyblock_bazaar.data.market import MarketSnapshot
from skyblock_bazaar.history.store import HistoryStore
from skyblock_bazaar.ui.pages.base import PageWidget
from skyblock_bazaar.ui.pages.chart_page import ChartPage
from skyblock_bazaar.ui.pages.specs import ALL_SPECS

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def snapshot() -> MarketSnapshot:
    payload = json.loads((ROOT / "tests" / "fixtures" / "bazaar_snapshot.json").read_text(encoding="utf-8"))
    snap = MarketSnapshot()
    snap.set_bazaar(payload["rows"], payload["updated"])
    return snap


@pytest.fixture(scope="module")
def library() -> RecipeLibrary:
    return RecipeLibrary.load()


@pytest.mark.parametrize("page_key", ["bazaar", "craft", "forge", "enchant"])
def test_pages_build_and_filter(qapp, snapshot, library, page_key):
    spec = ALL_SPECS[page_key]()
    page = PageWidget(spec, library, PageSettings())
    page.apply_snapshot(snapshot)
    assert page.model.rowCount() > 0
    assert page.proxy.rowCount() > 0
    assert page.model.columnCount() > 0
    page.show_search()
    first_name = str(page.model.rows()[0]["name"])
    page.search_edit.setText(first_name[:6])
    assert page.proxy.rowCount() >= 1
    page.deleteLater()


def test_chart_page_renders_live(qapp, snapshot, tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    page = ChartPage(store, HistorySettings(watchlist=["ENCHANTED_DIAMOND"]), None)
    page.set_snapshot(snapshot)
    assert page.current_item() == "ENCHANTED_DIAMOND"
    assert len(page.chart._bars) >= 1
    page.resize(900, 500)
    page.show()
    page.grab()  # 触发一次 paintEvent，确认不会抛异常
    page.deleteLater()
    store.close()
