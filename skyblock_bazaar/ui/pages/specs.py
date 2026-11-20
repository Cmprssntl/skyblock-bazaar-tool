"""四个页面的声明式定义：列 + 行构建函数。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ...analysis import bazaar as bazaar_analysis
from ...analysis import craft as craft_analysis
from ...analysis import enchant as enchant_analysis
from ...analysis import forge as forge_analysis
from ...data.library import RecipeLibrary
from ...data.market import MarketSnapshot
from ..table import ColumnSpec

VOL_TOOLTIPS = {
    "orders": "玩家挂出的订单笔数",
    "buy_depth": "卖单里可立即买到的物品总数（ask 深度）",
    "sell_depth": "买单里可立即卖出的物品总数（bid 深度）",
    "buy_trades": "近 7 天立即买入的成交量",
    "sell_trades": "近 7 天立即卖出的成交量",
}
PRICE_TOOLTIP = "立即买入价（卖一价）"
SELL_TOOLTIP = "立即卖出价（买一价）"
AH_TOOLTIP = "Auction House 最低一口价（BIN）"
CRAFT_TOOLTIP = "只要有一种材料缺少 Bazaar 价格，成本与利润显示为 -"


@dataclass(frozen=True, slots=True)
class PageSpec:
    key: str
    title: str
    columns: list[ColumnSpec]
    build: Callable[[MarketSnapshot, RecipeLibrary], list[dict]]
    needs_auction: bool
    sources_enabled: bool
    default_sort: tuple[str, bool]


_KIND_MIN_WIDTH = {
    "price": 142,
    "count": 116,
    "percent": 146,
    "duration": 92,
    "level": 70,
    "text": 220,
}


def _c(cid: str, title: str, kind: str, width: int = 0, tooltip: str = "", profit: bool = False) -> ColumnSpec:
    return ColumnSpec(cid, title, kind, max(width, _KIND_MIN_WIDTH.get(kind, 110)), tooltip, profit)


def bazaar_spec() -> PageSpec:
    columns = [
        _c("name", "物品ID", "text", 240),
        _c("buy", "收购价", "price", 110, PRICE_TOOLTIP),
        _c("sell", "出售价", "price", 110, SELL_TOOLTIP),
        _c("mid", "中间价", "price", 110, "收购价与出售价的平均"),
        _c("margin", "单件差价", "price", 100, "出售价 - 收购价", profit=True),
        _c("pct", "单件利润率%", "percent", 95, "单件差价 / 收购价", profit=True),
        _c("buyOrders", "买单笔数", "count", 95, VOL_TOOLTIPS["orders"]),
        _c("sellOrders", "卖单笔数", "count", 95, VOL_TOOLTIPS["orders"]),
        _c("vol_buy", "卖单件数", "count", 110, VOL_TOOLTIPS["buy_depth"]),
        _c("vol_sell", "买单件数", "count", 110, VOL_TOOLTIPS["sell_depth"]),
        _c("week_buy", "7日买入量", "count", 110, VOL_TOOLTIPS["buy_trades"]),
        _c("week_sell", "7日卖出量", "count", 110, VOL_TOOLTIPS["sell_trades"]),
    ]
    return PageSpec("bazaar", "Bazaar", columns, bazaar_analysis.build_rows, False, False, ("pct", True))


def craft_spec() -> PageSpec:
    columns = [
        _c("name", "物品ID", "text", 230),
        _c("item_buy", "物品收购价", "price", 110, PRICE_TOOLTIP),
        _c("item_sell", "物品出售价", "price", 110, SELL_TOOLTIP),
        _c("item_ah", "AH最低一口价", "price", 110, AH_TOOLTIP),
        _c("recipe", "合成配方的材料", "text", 300),
        _c("mat_buy", "材料收购价", "price", 110, CRAFT_TOOLTIP),
        _c("mat_sell", "材料出售价", "price", 110, CRAFT_TOOLTIP),
        _c("buy_mat_buy", "收购价-材料收购", "price", 130, profit=True),
        _c("buy_mat_sell", "收购价-材料出售", "price", 130, profit=True),
        _c("sell_mat_buy", "出售价-材料收购", "price", 130, profit=True),
        _c("sell_mat_sell", "出售价-材料出售", "price", 130, profit=True),
        _c("rate_buy_mat_buy", "收购价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_buy_mat_sell", "收购价/材料出售利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_buy", "出售价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_sell", "出售价/材料出售利润率%", "percent", 150, profit=True),
        _c("item_buyOrders", "物品买单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_sellOrders", "物品卖单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_vol_buy", "物品卖单件数", "count", 110, VOL_TOOLTIPS["buy_depth"]),
        _c("item_vol_sell", "物品买单件数", "count", 110, VOL_TOOLTIPS["sell_depth"]),
        _c("item_week_buy", "物品7日买入量", "count", 120, VOL_TOOLTIPS["buy_trades"]),
        _c("item_week_sell", "物品7日卖出量", "count", 120, VOL_TOOLTIPS["sell_trades"]),
        _c("mat_buyOrders", "材料买单笔数（合计）", "count", 140),
        _c("mat_sellOrders", "材料卖单笔数（合计）", "count", 140),
        _c("mat_vol_buy", "材料卖单件数（合计）", "count", 140),
        _c("mat_vol_sell", "材料买单件数（合计）", "count", 140),
        _c("mat_week_buy", "材料7日买入量（合计）", "count", 150),
        _c("mat_week_sell", "材料7日卖出量（合计）", "count", 150),
        _c("mat_craft_buy", "材料可制作数量（收购量）", "count", 160),
        _c("mat_craft_sell", "材料可制作数量（出售量）", "count", 160),
        _c("mat_craft_week_buy", "材料可制作数量（7日买入）", "count", 170),
        _c("mat_craft_week_sell", "材料可制作数量（7日卖出）", "count", 170),
    ]
    return PageSpec("craft", "Craft", columns, _build_craft, True, True, ("sell_mat_sell", True))


def forge_spec() -> PageSpec:
    columns = [
        _c("name", "物品ID", "text", 230),
        _c("item_buy", "物品收购价", "price", 110, PRICE_TOOLTIP),
        _c("item_sell", "物品出售价", "price", 110, SELL_TOOLTIP),
        _c("item_ah", "AH最低一口价", "price", 110, AH_TOOLTIP),
        _c("recipe", "Forge配方材料", "text", 300),
        _c("mat_buy", "材料收购价", "price", 110, CRAFT_TOOLTIP),
        _c("mat_sell", "材料出售价", "price", 110, CRAFT_TOOLTIP),
        _c("buy_mat_buy", "收购价-材料收购", "price", 130, profit=True),
        _c("buy_mat_sell", "收购价-材料出售", "price", 130, profit=True),
        _c("sell_mat_buy", "出售价-材料收购", "price", 130, profit=True),
        _c("sell_mat_sell", "出售价-材料出售", "price", 130, profit=True),
        _c("hour_buy_mat_buy", "收购价-材料收购小时利润", "price", 180, profit=True),
        _c("hour_buy_mat_sell", "收购价-材料出售小时利润", "price", 180, profit=True),
        _c("hour_sell_mat_buy", "出售价-材料收购小时利润", "price", 180, profit=True),
        _c("hour_sell_mat_sell", "出售价-材料出售小时利润", "price", 180, profit=True),
        _c("rate_buy_mat_buy", "收购价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_buy_mat_sell", "收购价/材料出售利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_buy", "出售价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_sell", "出售价/材料出售利润率%", "percent", 150, profit=True),
        _c("duration", "锻造时间", "duration", 110),
        _c("item_buyOrders", "物品买单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_sellOrders", "物品卖单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_vol_buy", "物品卖单件数", "count", 110, VOL_TOOLTIPS["buy_depth"]),
        _c("item_vol_sell", "物品买单件数", "count", 110, VOL_TOOLTIPS["sell_depth"]),
        _c("item_week_buy", "物品7日买入量", "count", 120, VOL_TOOLTIPS["buy_trades"]),
        _c("item_week_sell", "物品7日卖出量", "count", 120, VOL_TOOLTIPS["sell_trades"]),
        _c("mat_buyOrders", "材料买单笔数（合计）", "count", 140),
        _c("mat_sellOrders", "材料卖单笔数（合计）", "count", 140),
        _c("mat_vol_buy", "材料卖单件数（合计）", "count", 140),
        _c("mat_vol_sell", "材料买单件数（合计）", "count", 140),
        _c("mat_week_buy", "材料7日买入量（合计）", "count", 150),
        _c("mat_week_sell", "材料7日卖出量（合计）", "count", 150),
        _c("mat_craft_buy", "材料可制作数量（收购量）", "count", 160),
        _c("mat_craft_sell", "材料可制作数量（出售量）", "count", 160),
        _c("mat_craft_week_buy", "材料可制作数量（7日买入）", "count", 170),
        _c("mat_craft_week_sell", "材料可制作数量（7日卖出）", "count", 170),
    ]
    return PageSpec("forge", "Forge", columns, _build_forge, True, True, ("hour_sell_mat_sell", True))


def enchant_spec() -> PageSpec:
    columns = [
        _c("name", "附魔", "text", 260),
        _c("level", "等级", "level", 70),
        _c("recipe", "合成配方的材料", "text", 240),
        _c("item_buy", "物品收购价", "price", 110, PRICE_TOOLTIP),
        _c("item_sell", "物品出售价", "price", 110, SELL_TOOLTIP),
        _c("mat_buy", "材料收购价", "price", 110, CRAFT_TOOLTIP),
        _c("mat_sell", "材料出售价", "price", 110, CRAFT_TOOLTIP),
        _c("buy_mat_buy", "收购价-材料收购", "price", 130, profit=True),
        _c("buy_mat_sell", "收购价-材料出售", "price", 130, profit=True),
        _c("sell_mat_buy", "出售价-材料收购", "price", 130, profit=True),
        _c("sell_mat_sell", "出售价-材料出售", "price", 130, profit=True),
        _c("rate_buy_mat_buy", "收购价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_buy_mat_sell", "收购价/材料出售利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_buy", "出售价/材料收购利润率%", "percent", 150, profit=True),
        _c("rate_sell_mat_sell", "出售价/材料出售利润率%", "percent", 150, profit=True),
        _c("item_buyOrders", "物品买单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_sellOrders", "物品卖单笔数", "count", 110, VOL_TOOLTIPS["orders"]),
        _c("item_vol_buy", "物品卖单件数", "count", 110, VOL_TOOLTIPS["buy_depth"]),
        _c("item_vol_sell", "物品买单件数", "count", 110, VOL_TOOLTIPS["sell_depth"]),
        _c("item_week_buy", "物品7日买入量", "count", 120, VOL_TOOLTIPS["buy_trades"]),
        _c("item_week_sell", "物品7日卖出量", "count", 120, VOL_TOOLTIPS["sell_trades"]),
        _c("mat_buyOrders", "材料买单笔数（合计）", "count", 140),
        _c("mat_sellOrders", "材料卖单笔数（合计）", "count", 140),
        _c("mat_vol_buy", "材料卖单件数（合计）", "count", 140),
        _c("mat_vol_sell", "材料买单件数（合计）", "count", 140),
        _c("mat_week_buy", "材料7日买入量（合计）", "count", 150),
        _c("mat_week_sell", "材料7日卖出量（合计）", "count", 150),
        _c("mat_craft_buy", "材料可制作数量（收购量）", "count", 160),
        _c("mat_craft_sell", "材料可制作数量（出售量）", "count", 160),
        _c("mat_craft_week_buy", "材料可制作数量（7日买入）", "count", 170),
        _c("mat_craft_week_sell", "材料可制作数量（7日卖出）", "count", 170),
    ]
    return PageSpec("enchant", "Enchant", columns, _build_enchant, False, False, ("rate_sell_mat_sell", True))


def _build_craft(snapshot: MarketSnapshot, library: RecipeLibrary) -> list[dict]:
    return craft_analysis.build_rows(snapshot, library.craft, use_ah=True)


def _build_forge(snapshot: MarketSnapshot, library: RecipeLibrary) -> list[dict]:
    return forge_analysis.build_rows(snapshot, library.forge, use_ah=True)


def _build_enchant(snapshot: MarketSnapshot, library: RecipeLibrary) -> list[dict]:
    return enchant_analysis.build_rows(snapshot, library.enchant)


ALL_SPECS = {
    "bazaar": bazaar_spec,
    "craft": craft_spec,
    "forge": forge_spec,
    "enchant": enchant_spec,
}
