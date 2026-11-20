"""各页面共用的成本 / 产能计算。

v4 规则：只要配方中有一种材料拿不到 Bazaar 价格，相关成本与产能一律视为未知（None），
避免把部分材料的成本当成总成本而虚高利润。
"""

from __future__ import annotations

import math


def is_bazaar(row: dict | None) -> bool:
    return bool(row) and row.get("_source", "bazaar") == "bazaar"


def quote_price(row: dict | None, field: str = "buy") -> float | None:
    """Bazaar 报价；缺失、AH 兜底行、价格为 0（该方向无挂单）都返回 None。"""
    if not is_bazaar(row):
        return None
    value = row.get(field)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def material_cost(materials: dict[str, float], market: dict[str, dict], field: str) -> float | None:
    total = 0.0
    for item_id, amount in materials.items():
        value = quote_price(market.get(item_id), field)
        if value is None:
            return None
        total += amount * value
    return total


def material_metric_sum(
    materials: dict[str, float], market: dict[str, dict], field: str, weighted: bool = False
) -> float | None:
    """各材料市场指标的合计。

    v3.5 口径：Craft/Forge 合计的是材料市场原始指标（不乘配方数量），
    Enchant 则按材料数量加权，因此保留 weighted 开关。
    """
    total: float | None = None
    for item_id, amount in materials.items():
        row = market.get(item_id)
        if not is_bazaar(row):
            return None
        value = row.get(field)
        if value is None:
            return None
        item_value = float(value) * (amount if weighted else 1)
        total = item_value if total is None else total + item_value
    return total


def craft_capacity(materials: dict[str, float], market: dict[str, dict], field: str) -> int | None:
    capacities: list[float] = []
    for item_id, amount in materials.items():
        row = market.get(item_id)
        if not is_bazaar(row) or amount <= 0:
            return None
        value = row.get(field)
        if value is None:
            return None
        capacities.append(float(value) / amount)
    return math.floor(min(capacities)) if capacities else None


def profit_pairs(item_buy, item_sell, mat_buy, mat_sell) -> dict[str, float | None]:
    pairs = {
        "buy_mat_buy": (item_buy, mat_buy),
        "buy_mat_sell": (item_buy, mat_sell),
        "sell_mat_buy": (item_sell, mat_buy),
        "sell_mat_sell": (item_sell, mat_sell),
    }
    values: dict[str, float | None] = {}
    for name, (output, cost) in pairs.items():
        values[name] = (output - cost) if output is not None and cost is not None else None
        values[f"rate_{name}"] = (
            values[name] / cost * 100 if values[name] is not None and cost not in (None, 0) else None
        )
    return values
