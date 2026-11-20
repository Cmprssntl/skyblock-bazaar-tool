"""与 v3.5 的 golden 数据对照：价格、成本、利润、产能。

有意保留的差异只有两类，且都由“未知价格”规则产生：
1. 配方里有材料拿不到 Bazaar 价格：新实现把成本/利润/产能标为 None，
   而 v3.5 会把它当作“只计算有价材料”的部分和。
2. 某个方向没有挂单（价格 0）或物品只有 AH 价：新实现同样视为未知，
   避免把 0 当成免费或把 AH 价当成 Bazaar 价。
测试只跳过这些字段，其余数值必须与 v3.5 完全一致。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skyblock_bazaar.analysis import craft as craft_analysis
from skyblock_bazaar.analysis import enchant as enchant_analysis
from skyblock_bazaar.analysis import forge as forge_analysis
from skyblock_bazaar.data.library import RecipeLibrary
from skyblock_bazaar.data.market import MarketSnapshot

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "bazaar_snapshot.json"
GOLDEN = ROOT / "tests" / "golden"

ZERO_FIELDS = ("item_buy", "item_sell", "mat_buy", "mat_sell")
MATERIAL_FIELDS = (
    "mat_buy",
    "mat_sell",
    "buy_mat_buy",
    "buy_mat_sell",
    "sell_mat_buy",
    "sell_mat_sell",
    "rate_buy_mat_buy",
    "rate_buy_mat_sell",
    "rate_sell_mat_buy",
    "rate_sell_mat_sell",
    "hour_buy_mat_buy",
    "hour_buy_mat_sell",
    "hour_sell_mat_buy",
    "hour_sell_mat_sell",
    "mat_buyOrders",
    "mat_sellOrders",
    "mat_vol_buy",
    "mat_vol_sell",
    "mat_week_buy",
    "mat_week_sell",
    "mat_craft_buy",
    "mat_craft_sell",
    "mat_craft_week_buy",
    "mat_craft_week_sell",
)
DEPENDENTS = {
    "item_buy": {
        "buy_mat_buy",
        "buy_mat_sell",
        "rate_buy_mat_buy",
        "rate_buy_mat_sell",
        "hour_buy_mat_buy",
        "hour_buy_mat_sell",
    },
    "item_sell": {
        "sell_mat_buy",
        "sell_mat_sell",
        "rate_sell_mat_buy",
        "rate_sell_mat_sell",
        "hour_sell_mat_buy",
        "hour_sell_mat_sell",
    },
    "mat_buy": {
        "buy_mat_buy",
        "sell_mat_buy",
        "rate_buy_mat_buy",
        "rate_sell_mat_buy",
        "hour_buy_mat_buy",
        "hour_sell_mat_buy",
    },
    "mat_sell": {
        "buy_mat_sell",
        "sell_mat_sell",
        "rate_buy_mat_sell",
        "rate_sell_mat_sell",
        "hour_buy_mat_sell",
        "hour_sell_mat_sell",
    },
}


@pytest.fixture(scope="module")
def snapshot() -> MarketSnapshot:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = MarketSnapshot()
    snap.set_bazaar(payload["rows"], payload["updated"])
    return snap


@pytest.fixture(scope="module")
def library() -> RecipeLibrary:
    return RecipeLibrary.load()


def _golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def _close(a, b, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return a == b


def _unknown_fields(row: dict, old: dict) -> set[str]:
    """找出本次按“未知价格”规则变成 None、因而不能与 v3.5 比较的字段。"""
    skip: set[str] = set()
    for field in ZERO_FIELDS:
        if old.get(field) == 0 and row.get(field) is None:
            skip.add(field)
            skip |= DEPENDENTS[field]
    for field in ("mat_buy", "mat_sell"):
        if row.get(field) is None and old.get(field) not in (None, 0):
            # v3.5 把缺失材料当成 0，只累加有价材料；新实现整体视为未知
            skip.add(field)
            skip |= DEPENDENTS[field]
    missing_rows = (row.get("mat_buy") is None or row.get("mat_sell") is None) and (
        row.get("mat_buyOrders") is None
    )
    if missing_rows:
        # 材料本身不在 Bazaar（仅有 AH 兜底或完全没有）：指标与产能同样未知
        skip |= set(MATERIAL_FIELDS)
    return skip


def _compare_rows(new_rows: list[dict], old_rows: list[dict], key_fields: tuple[str, ...]) -> tuple[int, int]:
    old_by_key = {tuple(row.get(f) for f in key_fields): row for row in old_rows}
    compared = 0
    unknown = 0
    for row in new_rows:
        key = tuple(row.get(f) for f in key_fields)
        old = old_by_key.get(key)
        if old is None:
            continue
        skip = _unknown_fields(row, old)
        if skip:
            unknown += 1
            for field in skip:
                assert row.get(field) is None, f"{key} {field} 应为未知"
        compared += 1
        for field, value in old.items():
            if field == "recipe" or field in skip:
                continue
            assert field in row, f"缺少字段 {field}"
            assert _close(row.get(field), value), f"{key} 字段 {field}: {row.get(field)} != {value}"
    return compared, unknown


def test_craft_parity(snapshot, library):
    golden = _golden("craft_rows.json")
    rows = craft_analysis.build_rows(snapshot, library.craft)
    assert len(rows) == golden["count"], f"craft 行数变化：{len(rows)} != {golden['count']}"
    compared, unknown = _compare_rows(rows, golden["rows"], ("name",))
    assert compared > 0
    assert unknown > 0, "夹具里应当存在缺价 / 无挂单的行，用来覆盖未知规则"


def test_forge_parity(snapshot, library):
    golden = _golden("forge_rows.json")
    rows = forge_analysis.build_rows(snapshot, library.forge)
    assert len(rows) == golden["count"]
    compared, _unknown = _compare_rows(rows, golden["rows"], ("name",))
    assert compared > 0


def test_enchant_parity(snapshot, library):
    golden = _golden("enchant_rows.json")
    rows = enchant_analysis.build_rows(snapshot, library.enchant)
    assert len(rows) == golden["count"]
    compared, unknown = _compare_rows(rows, golden["rows"], ("name", "level", "recipe"))
    assert compared > 0
    assert unknown > 0, "附魔书大量等级没有卖单，应当走未知规则"
