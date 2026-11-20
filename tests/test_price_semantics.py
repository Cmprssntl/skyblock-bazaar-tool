"""价格语义：0 表示没有挂单，必须变成未知，而不是免费。"""

from __future__ import annotations

import json

from skyblock_bazaar.analysis.common import material_cost, quote_price
from skyblock_bazaar.data.bazaar import parse_products
from skyblock_bazaar.data.cache import MarketCache
from skyblock_bazaar.history.bars import build_bars


def _product(sell_price, buy_price):
    return {
        "quick_status": {
            "sellPrice": sell_price,
            "buyPrice": buy_price,
            "buyOrders": 3,
            "sellOrders": 4,
            "buyVolume": 10,
            "sellVolume": 20,
            "buyMovingWeek": 100,
            "sellMovingWeek": 200,
        }
    }


def test_parse_products_treats_zero_as_missing():
    rows = parse_products({"ONE_SIDED": _product(0, 15.5), "NO_SIDE": _product(0, 0)})
    by_name = {row["name"]: row for row in rows}

    one = by_name["ONE_SIDED"]
    assert one["buy"] is None
    assert one["sell"] == 15.5
    assert one["mid"] is None and one["margin"] is None and one["pct"] is None

    none = by_name["NO_SIDE"]
    assert none["buy"] is None and none["sell"] is None and none["mid"] is None


def test_cache_normalizes_v35_zero_prices(tmp_path):
    path = tmp_path / "bazaar.json"
    path.write_text(
        json.dumps(
            {
                "updated": 1,
                "items": [
                    {"name": "OLD", "buy": 0, "sell": 12, "mid": 12, "margin": 0, "pct": 0.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    rows, _updated = MarketCache(path, tmp_path / "auction.json").load_bazaar()
    row = rows[0]
    assert row["buy"] is None and row["sell"] == 12.0
    assert row["mid"] is None and row["margin"] is None and row["pct"] is None


def test_quote_price_requires_bazaar_and_positive():
    assert quote_price({"buy": 10, "_source": "bazaar"}) == 10
    assert quote_price({"buy": 0, "_source": "bazaar"}) is None
    assert quote_price({"buy": 10, "_source": "auction"}) is None
    assert quote_price(None) is None


def test_material_cost_with_zero_priced_material_is_unknown():
    market = {
        "A": {"buy": 0, "sell": 2, "_source": "bazaar"},
        "B": {"buy": 3, "sell": 4, "_source": "bazaar"},
    }
    assert material_cost({"A": 1, "B": 2}, market, "buy") is None
    assert material_cost({"A": 1, "B": 2}, market, "sell") == 10


def test_bars_skip_missing_prices():
    rows = [
        (1700000000, 0, 0, 0, 10, 20),
        (1700000900, 99, 101, 100, 11, 21),
        (1700000950, 98, 102, 100, 12, 22),
    ]
    bars = build_bars(rows, 900, "mid")
    assert len(bars) == 1
    assert bars[0].open == 100 and bars[0].close == 100
    # 中间缺失的一拍不会贡献成交量
    assert bars[0].volume == 2
