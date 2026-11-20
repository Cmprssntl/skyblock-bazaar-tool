"""行情快照：Bazaar 行 + BIN 索引，供各页面只读使用。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .auctions import lookup_bin


@dataclass
class MarketSnapshot:
    bazaar: list[dict] = field(default_factory=list)
    bin_index: dict = field(default_factory=dict)
    by_id: dict[str, dict] = field(default_factory=dict)
    bazaar_updated: int = 0
    auction_updated: int = 0
    bazaar_stale: bool = False
    auction_stale: bool = False

    def set_bazaar(self, rows: list[dict], updated: int, stale: bool = False) -> None:
        self.bazaar = rows
        self.by_id = {row["name"]: row for row in rows if row.get("name")}
        self.bazaar_updated = int(updated)
        self.bazaar_stale = stale

    def set_bin_index(self, index: dict, updated: int, stale: bool = False) -> None:
        self.bin_index = index
        self.auction_updated = int(updated)
        self.auction_stale = stale

    def market_map(self, item_ids: set[str], use_ah_fallback: bool = True) -> dict[str, dict]:
        """Bazaar 行 + 缺失物品的 AH 兜底行。

        兜底行带有 `_source="auction"`，分析层据此决定成本/利润是否可用。
        """
        market = {item_id: {**row, "_source": "bazaar"} for item_id, row in self.by_id.items()}
        if not use_ah_fallback:
            return market
        for item_id in item_ids:
            if item_id in market:
                continue
            entry = lookup_bin(self.bin_index, item_id)
            if not entry:
                continue
            price = float(entry["lowest_bin"])
            market[item_id] = {
                "name": item_id,
                "buy": price,
                "sell": price,
                "mid": price,
                "margin": 0.0,
                "pct": 0.0,
                "buyOrders": None,
                "sellOrders": None,
                "vol_buy": None,
                "vol_sell": None,
                "week_buy": None,
                "week_sell": None,
                "_source": "auction",
            }
        return market

    def item_names(self) -> list[str]:
        return list(self.by_id)

    def quote(self, item_id: str) -> dict | None:
        return self.by_id.get(item_id)
