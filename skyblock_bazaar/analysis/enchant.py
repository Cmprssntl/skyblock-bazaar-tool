"""Enchant 页面：附魔书铁砧升级配方（只用 Bazaar 数据）。"""

from __future__ import annotations

from ..data.market import MarketSnapshot
from ..data.recipes import EnchantRecipe, parse_enchant_output, to_roman
from .common import craft_capacity, material_cost, material_metric_sum, profit_pairs, quote_price

METRIC_FIELDS = ("buyOrders", "sellOrders", "vol_buy", "vol_sell", "week_buy", "week_sell")
CAPACITY_FIELDS = (
    ("mat_craft_buy", "vol_buy"),
    ("mat_craft_sell", "vol_sell"),
    ("mat_craft_week_buy", "week_buy"),
    ("mat_craft_week_sell", "week_sell"),
)


def _format_recipe(materials: dict[str, float]) -> str:
    parts = []
    for item_id, amount in materials.items():
        parsed = parse_enchant_output(item_id)
        if parsed:
            parts.append(f"{to_roman(parsed[1])} x {_quantity(amount)}")
        else:
            parts.append(f"{item_id} x {_quantity(amount)}")
    return " + ".join(parts)


def _quantity(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def build_rows(snapshot: MarketSnapshot, recipes: dict[str, EnchantRecipe]) -> list[dict]:
    if not recipes:
        return []
    market = snapshot.market_map(set(recipes), use_ah_fallback=False)
    rows: list[dict] = []
    for output_id, recipe in recipes.items():
        item = market.get(output_id)
        if not item:
            continue
        for materials in recipe.alternatives:
            item_buy = quote_price(item, "buy")
            item_sell = quote_price(item, "sell")
            mat_buy = material_cost(materials, market, "buy")
            mat_sell = material_cost(materials, market, "sell")
            row: dict = {
                "name": recipe.base_id,
                "level": recipe.level,
                "recipe": _format_recipe(materials),
                "item_buy": item_buy,
                "item_sell": item_sell,
                "mat_buy": mat_buy,
                "mat_sell": mat_sell,
            }
            row.update(profit_pairs(item_buy, item_sell, mat_buy, mat_sell))
            for field in METRIC_FIELDS:
                row[f"item_{field}"] = item.get(field)
            for field in METRIC_FIELDS:
                row[f"mat_{field}"] = material_metric_sum(materials, market, field, weighted=True)
            for target, source in CAPACITY_FIELDS:
                row[target] = craft_capacity(materials, market, source)
            rows.append(row)
    return rows
