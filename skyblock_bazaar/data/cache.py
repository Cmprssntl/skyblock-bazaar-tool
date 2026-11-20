"""本地行情缓存：原子写 JSON，兼容 v3.5 的旧格式。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..paths import data_path
from .auctions import build_index


def _read(path: Path):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def write_json_atomic(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, path)


class MarketCache:
    def __init__(self, bazaar_path: Path | None = None, auction_path: Path | None = None):
        self.bazaar_path = bazaar_path or data_path("bazaar_data.json")
        self.auction_path = auction_path or data_path("auction_data.json")

    # ------------------------------------------------------------ Bazaar
    def load_bazaar(self) -> tuple[list[dict], int]:
        payload = _read(self.bazaar_path)
        if isinstance(payload, dict):
            rows = payload.get("items")
            updated = int(payload.get("updated") or 0)
        elif isinstance(payload, list):
            rows, updated = payload, 0
        else:
            return [], 0
        if not isinstance(rows, list):
            return [], 0
        cleaned = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            item = dict(row)
            # 兼容 v3.5 缓存：0 表示该方向无挂单，统一成 None；并重算派生字段
            buy = _positive(item.get("buy"))
            sell = _positive(item.get("sell"))
            item["buy"], item["sell"] = buy, sell
            if buy is not None and sell is not None:
                item["mid"] = (buy + sell) / 2
                item["margin"] = sell - buy
                item["pct"] = round((sell - buy) / buy * 100, 2)
            else:
                item["mid"] = None
                item["margin"] = None
                item["pct"] = None
            cleaned.append(item)
        return cleaned, updated

    def save_bazaar(self, rows: list[dict], updated: int) -> None:
        write_json_atomic(self.bazaar_path, {"version": 2, "updated": int(updated), "items": rows})

    # ------------------------------------------------------------ Auction
    def load_bin_index(self) -> tuple[dict, int]:
        payload = _read(self.auction_path)
        if isinstance(payload, dict):
            updated = int(payload.get("updated") or 0)
            bins = payload.get("bins")
            if isinstance(bins, dict):
                return bins, updated
            auctions = payload.get("auctions")
            if isinstance(auctions, list):
                return build_index(auctions), updated
        elif isinstance(payload, list):
            return build_index(payload), 0
        return {}, 0

    def save_bin_index(self, index: dict, updated: int) -> None:
        write_json_atomic(self.auction_path, {"version": 2, "updated": int(updated), "bins": index})
