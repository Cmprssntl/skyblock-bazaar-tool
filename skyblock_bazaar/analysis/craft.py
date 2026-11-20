"""Craft 页面：成品价 - 材料成本，四种组合与利润率、产能。"""

from __future__ import annotations

from ..data.auctions import lookup_bin
from ..data.market import MarketSnapshot
from ..data.recipes import Recipe
from .common import craft_capacity, material_cost, material_metric_sum, profit_pairs, quote_price

METRIC_FIELDS = ("buyOrders", "sellOrders", "vol_buy", "vol_sell", "week_buy", "week_sell")
CAPACITY_FIELDS = (
    ("mat_craft_buy", "vol_buy"),
    ("mat_craft_sell", "vol_sell"),
    ("mat_craft_week_buy", "week_buy"),
    ("mat_craft_week_sell", "week_sell"),
)


def format_recipe(materials: dict[str, float]) -> str:
    parts = []
    for item_id in sorted(materials):
        parts.append(f"{item_id} x {_quantity(materials[item_id])}")
    return " + ".join(parts)


def _quantity(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def build_rows(snapshot: MarketSnapshot, recipes: dict[str, Recipe], use_ah: bool = True) -> list[dict]:
    if not recipes:
        return []
    needed = set(recipes)
    for recipe in recipes.values():
        needed.update(recipe.materials)
    market = snapshot.market_map(needed, use_ah_fallback=use_ah)

    rows: list[dict] = []
    for item_id, recipe in recipes.items():
        item = market.get(item_id)
        if not item:
            continue
        materials = recipe.materials
        item_buy = quote_price(item, "buy")
        item_sell = quote_price(item, "sell")
        ah = lookup_bin(snapshot.bin_index, item_id)

        mat_buy = material_cost(materials, market, "buy")
        mat_sell = material_cost(materials, market, "sell")
        row: dict = {
            "name": item_id,
            "item_buy": item_buy,
            "item_sell": item_sell,
            "item_ah": ah.get("lowest_bin") if ah else None,
            "recipe": format_recipe(materials),
            "mat_buy": mat_buy,
            "mat_sell": mat_sell,
        }
        for field in METRIC_FIELDS:
            row[f"item_{field}"] = item.get(field) if item.get("_source", "bazaar") == "bazaar" else None
        for field in METRIC_FIELDS:
            row[f"mat_{field}"] = material_metric_sum(materials, market, field)
        for target, source in CAPACITY_FIELDS:
            row[target] = craft_capacity(materials, market, source)
        row.update(profit_pairs(item_buy, item_sell, mat_buy, mat_sell))
        rows.append(row)
    return rows
