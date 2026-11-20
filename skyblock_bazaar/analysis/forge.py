"""Forge 页面：锻造时间与小时利润。"""

from __future__ import annotations

from ..data.auctions import lookup_bin
from ..data.market import MarketSnapshot
from ..data.recipes import ForgeRecipe
from .common import craft_capacity, material_cost, material_metric_sum, profit_pairs, quote_price

METRIC_FIELDS = ("buyOrders", "sellOrders", "vol_buy", "vol_sell", "week_buy", "week_sell")
CAPACITY_FIELDS = (
    ("mat_craft_buy", "vol_buy"),
    ("mat_craft_sell", "vol_sell"),
    ("mat_craft_week_buy", "week_buy"),
    ("mat_craft_week_sell", "week_sell"),
)


def format_duration(seconds: float) -> str:
    seconds = round(seconds or 0)
    if seconds < 60:
        return f"{seconds}秒"
    minutes, second = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}分{second}秒" if second else f"{minutes}分"
    hours, minute = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}小时{minute}分" if minute else f"{hours}小时"
    days, hour = divmod(hours, 24)
    return f"{days}天{hour}小时" if hour else f"{days}天"


def format_recipe(materials: dict[str, float]) -> str:
    return " + ".join(f"{item_id} x {amount:g}" for item_id, amount in materials.items())


def build_rows(snapshot: MarketSnapshot, recipes: dict[str, ForgeRecipe], use_ah: bool = True) -> list[dict]:
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
            "duration": recipe.duration,
        }
        row.update(profit_pairs(item_buy, item_sell, mat_buy, mat_sell))
        hours = recipe.duration / 3600 if recipe.duration > 0 else 0.0
        for key in ("buy_mat_buy", "buy_mat_sell", "sell_mat_buy", "sell_mat_sell"):
            value = row.get(key)
            row[f"hour_{key}"] = value / hours if hours and value is not None else None
        for field in METRIC_FIELDS:
            row[f"item_{field}"] = item.get(field) if item.get("_source", "bazaar") == "bazaar" else None
        for field in METRIC_FIELDS:
            row[f"mat_{field}"] = material_metric_sum(materials, market, field)
        for target, source in CAPACITY_FIELDS:
            row[target] = craft_capacity(materials, market, source)
        rows.append(row)
    return rows
