"""OHLC 聚合：用本地快照生成蜡烛，量柱取 7 日成交量的增量（近似）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

PERIODS: list[tuple[str, str, int]] = [
    ("15分", "15m", 900),
    ("1时", "1h", 3600),
    ("1日", "1d", 86400),
]
PERIOD_SECONDS = {key: seconds for _label, key, seconds in PERIODS}
PRICE_FIELDS = {"buy": 1, "sell": 2, "mid": 3}  # rows: (ts, bid, ask, mid, buy_week, sell_week)
MAX_VOLUME_GAP = 1800  # 两次快照间隔超过 30 分钟就不计算成交量增量


@dataclass(slots=True)
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ticks: int

    @property
    def up(self) -> bool:
        return self.close >= self.open


def bucket_start(ts: int, period: int) -> int:
    if period >= 86400:
        moment = datetime.fromtimestamp(ts)
        return int(datetime(moment.year, moment.month, moment.day).timestamp())
    return int(ts) - int(ts) % period


def build_bars(rows: list[tuple], period: int, price: str = "mid") -> list[Bar]:
    """rows: (ts, bid, ask, mid, buy_week, sell_week) 按时间升序。"""
    if price not in PRICE_FIELDS:
        price = "mid"
    index = PRICE_FIELDS[price]

    bars: list[Bar] = []
    current: Bar | None = None
    prev_ts: int | None = None
    prev_buy_week: float | None = None
    prev_sell_week: float | None = None

    for row in rows:
        ts = int(row[0])
        value = float(row[index] or 0)
        if value <= 0:
            prev_ts = ts
            continue
        buy_week = float(row[4] or 0)
        sell_week = float(row[5] or 0)
        volume = 0.0
        if (
            prev_ts is not None
            and 0 < ts - prev_ts <= MAX_VOLUME_GAP
            and prev_buy_week is not None
            and prev_sell_week is not None
        ):
            volume = max(0.0, buy_week - prev_buy_week) + max(0.0, sell_week - prev_sell_week)
        prev_ts, prev_buy_week, prev_sell_week = ts, buy_week, sell_week

        key = bucket_start(ts, period)
        if current is None or key != current.ts:
            if current is not None:
                bars.append(current)
            current = Bar(key, value, value, value, value, volume, 1)
        else:
            current.high = max(current.high, value)
            current.low = min(current.low, value)
            current.close = value
            current.volume += volume
            current.ticks += 1
    if current is not None:
        bars.append(current)
    return bars


def summarize(bars: list[Bar]) -> dict:
    if not bars:
        return {}
    first, last = bars[0], bars[-1]
    highs = max(bar.high for bar in bars)
    lows = min(bar.low for bar in bars)
    change = last.close - first.open
    return {
        "first": first.open,
        "last": last.close,
        "change": change,
        "change_pct": (change / first.open * 100) if first.open else 0.0,
        "high": highs,
        "low": lows,
        "volume": sum(bar.volume for bar in bars),
        "bars": len(bars),
    }


def format_ts(ts: int, period: int) -> str:
    moment = datetime.fromtimestamp(ts)
    if period >= 86400:
        return moment.strftime("%m-%d")
    return moment.strftime("%H:%M")


def format_full_ts(ts: int, period: int) -> str:
    moment = datetime.fromtimestamp(ts)
    if period >= 86400:
        return moment.strftime("%Y-%m-%d")
    return moment.strftime("%m-%d %H:%M")
