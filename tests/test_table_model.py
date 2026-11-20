"""表格模型：格式化、数值排序（None 最后）、过滤、搜索。"""

from __future__ import annotations

from PySide6.QtCore import Qt

from skyblock_bazaar.ui.table import ColumnSpec, MarketProxy, MarketTableModel


def _setup():
    model = MarketTableModel(
        [
            ColumnSpec("name", "物品ID", "text", 200),
            ColumnSpec("pct", "利润率%", "percent", 100),
        ]
    )
    model.set_rows(
        [
            {"name": "ALPHA", "pct": 5.0},
            {"name": "BETA", "pct": None},
            {"name": "GAMMA", "pct": -1.0},
        ]
    )
    proxy = MarketProxy()
    proxy.setSourceModel(model)
    return model, proxy


def _names(proxy) -> list[str]:
    return [proxy.index(row, 0).data() for row in range(proxy.rowCount())]


def test_display_and_units(qapp):
    model, _proxy = _setup()
    assert model.index(0, 0).data() == "ALPHA"
    assert model.index(0, 1).data() == "5.00"
    assert model.index(1, 1).data() == "-"
    model.set_units({"pct": "k"})
    assert model.headerData(1, Qt.Orientation.Horizontal) == "利润率%(k)"
    assert model.index(0, 1).data() == "0.01"


def test_sort_puts_none_last(qapp):
    _model, proxy = _setup()
    proxy.sort(1, Qt.SortOrder.AscendingOrder)
    assert _names(proxy) == ["GAMMA", "ALPHA", "BETA"]
    proxy.sort(1, Qt.SortOrder.DescendingOrder)
    assert _names(proxy) == ["ALPHA", "GAMMA", "BETA"]


def test_filter_and_search(qapp):
    _model, proxy = _setup()
    proxy.set_predicate(lambda row: row["pct"] is None or row["pct"] >= 0)
    assert _names(proxy) == ["ALPHA", "BETA"]
    proxy.set_search("alp")
    assert _names(proxy) == ["ALPHA"]
    index = proxy.index(0, 0)
    assert proxy.row_dict(index)["name"] == "ALPHA"
