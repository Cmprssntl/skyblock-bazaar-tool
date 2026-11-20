"""本地历史：SQLite 写入/查询、OHLC 聚合、量柱增量。"""

from __future__ import annotations

import time

from skyblock_bazaar.history.bars import bucket_start, build_bars
from skyblock_bazaar.history.store import HistoryStore

BASE = 1_700_000_400


def _db_row(ts: int, price: float, buy_week: float, sell_week: float) -> tuple:
    return ("TEST_ITEM", ts, price - 1, price + 1, price, 10, 20, 3, 4, buy_week, sell_week)


def _bar_row(ts: int, price: float, buy_week: float, sell_week: float) -> tuple:
    return (ts, price - 1, price + 1, price, buy_week, sell_week)


def test_store_write_query_and_purge(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    rows = [_db_row(BASE + i * 60, 100 + i, 1000 + i * 10, 2000 + i * 20) for i in range(10)]
    assert store.write(rows) == 10
    assert store.count("TEST_ITEM") == 10
    assert store.count() == 10

    data = store.query("TEST_ITEM")
    assert [row[0] for row in data] == [BASE + i * 60 for i in range(10)]
    assert store.latest_ts() == BASE + 540

    # 重复写入同一 (item, ts) 不会增加行数
    assert store.write(rows[:1]) == 1
    assert store.count("TEST_ITEM") == 10

    assert store.purge(BASE + 300) == 5
    assert store.count("TEST_ITEM") == 5
    store.close()


def test_bars_ohlc_and_volume():
    rows = [
        _bar_row(BASE, 100, 1000, 2000),
        _bar_row(BASE + 60, 104, 1010, 2020),
        _bar_row(BASE + 120, 96, 1030, 2025),
        _bar_row(BASE + 180, 110, 1040, 2060),
    ]
    bars = build_bars(rows, period=300, price="mid")
    assert len(bars) == 1
    bar = bars[0]
    assert bar.open == 100
    assert bar.high == 110
    assert bar.low == 96
    assert bar.close == 110
    # 每拍增量 = (buy_week + sell_week) 的变化
    assert bar.volume == (1010 - 1000) + (2020 - 2000) + (1030 - 1010) + (2025 - 2020) + (1040 - 1030) + (2060 - 2025)


def test_bars_gap_does_not_count_volume():
    rows = [_bar_row(BASE, 100, 1000, 2000), _bar_row(BASE + 7200, 101, 9999, 9999)]
    bars = build_bars(rows, period=300)
    assert len(bars) == 2
    assert bars[0].volume == 0
    assert bars[1].volume == 0


def test_price_mode():
    rows = [_bar_row(BASE, 100, 1, 1)]  # bid=99, ask=101
    assert build_bars(rows, 60, "buy")[0].close == 99
    assert build_bars(rows, 60, "sell")[0].close == 101
    assert build_bars(rows, 60, "mid")[0].close == 100


def test_bucket_start_daily():
    moment = time.localtime(BASE)
    start = bucket_start(BASE, 86400)
    assert time.localtime(start).tm_hour == 0
    assert time.localtime(start).tm_min == 0
    assert time.localtime(start).tm_yday == moment.tm_yday
