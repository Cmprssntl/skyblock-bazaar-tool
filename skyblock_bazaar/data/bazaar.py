"""Bazaar 行情。

价格口径（与 v3.5 一致）：
    buy  = quick_status.sellPrice → 立即买入价（卖一价 / ask）
    sell = quick_status.buyPrice  → 立即卖出价（买一价 / bid）

数量口径（v4 更正）：
    quick_status.sellVolume = 出售挂单件数（ask 深度，买入会消耗它）
    quick_status.buyVolume  = 收购挂单件数（bid 深度，卖出会消耗它）
    quick_status.sellMovingWeek = 近 7 天立即买入成交量（≈ 消耗 ask 的成交）
    quick_status.buyMovingWeek  = 近 7 天立即卖出成交量（≈ 消耗 bid 的成交）
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
HEADERS = {"User-Agent": "skyblock-bazaar-tool/4.0 (+https://github.com/Cmprssntl/skyblock-bazaar-tool)"}
TIMEOUT = 30


@dataclass(frozen=True, slots=True)
class BazaarQuote:
    name: str
    buy: float | None
    sell: float | None
    mid: float | None
    margin: float | None
    pct: float | None
    buy_orders: int
    sell_orders: int
    bid_depth: int
    ask_depth: int
    buy_week: int
    sell_week: int

    def as_row(self) -> dict:
        """表格 / 缓存使用的扁平字典（字段名与 v3.5 配置兼容）。"""
        return {
            "name": self.name,
            "buy": self.buy,
            "sell": self.sell,
            "mid": self.mid,
            "margin": self.margin,
            "pct": self.pct,
            "buyOrders": self.buy_orders,
            "sellOrders": self.sell_orders,
            "vol_buy": self.ask_depth,
            "vol_sell": self.bid_depth,
            "week_buy": self.buy_week,
            "week_sell": self.sell_week,
        }


def parse_products(products: dict) -> list[dict]:
    rows: list[dict] = []
    for item_id, info in (products or {}).items():
        quick = info.get("quick_status") or {}
        # 价格为 0 表示该方向没有挂单（无卖一价 / 无买一价），用 None 表示未知
        buy = _as_price(quick.get("sellPrice"))
        sell = _as_price(quick.get("buyPrice"))
        if buy is not None and sell is not None:
            mid = (buy + sell) / 2
            margin = sell - buy
            pct = round(margin / buy * 100, 2) if buy > 0 else None
        else:
            mid = margin = pct = None
        quote = BazaarQuote(
            name=str(item_id),
            buy=buy,
            sell=sell,
            mid=mid,
            margin=margin,
            pct=pct,
            buy_orders=_as_int(quick.get("buyOrders")),
            sell_orders=_as_int(quick.get("sellOrders")),
            bid_depth=_as_int(quick.get("buyVolume")),
            ask_depth=_as_int(quick.get("sellVolume")),
            buy_week=_as_int(quick.get("sellMovingWeek")),
            sell_week=_as_int(quick.get("buyMovingWeek")),
        )
        rows.append(quote.as_row())
    rows.sort(key=lambda row: row["name"])
    return rows


def fetch_bazaar(api_key: str = "", timeout: int = TIMEOUT, session: requests.Session | None = None) -> tuple[list[dict], str]:
    """返回 (rows, message)；失败时 rows 为空，由调用方决定是否使用缓存。"""
    params = {"key": api_key} if api_key else None
    own = session is None
    session = session or requests.Session()
    try:
        response = session.get(BAZAAR_URL, headers=HEADERS, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("success"):
            cause = payload.get("cause") if isinstance(payload, dict) else None
            return [], f"Bazaar API 失败：{cause or '未知原因'}"
        rows = parse_products(payload.get("products") or {})
        return rows, f"Bazaar 已更新（{len(rows)} 项）"
    except requests.RequestException as exc:
        return [], f"Bazaar 请求失败：{exc}"
    except ValueError as exc:
        return [], f"Bazaar 返回无效 JSON：{exc}"
    finally:
        if own:
            session.close()


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_price(value) -> float | None:
    """0 / 负数 / 非法值都表示“没有这个方向的价格”。"""
    number = _as_float(value)
    return number if number > 0 else None


def _as_int(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
