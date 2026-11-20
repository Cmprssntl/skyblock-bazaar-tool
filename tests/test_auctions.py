"""Auction House 分页：连接错误重试、BIN 索引与去重。"""

from __future__ import annotations

from typing import ClassVar

import requests

from skyblock_bazaar.data import auctions


class _Response:
    status_code = 200
    headers: ClassVar[dict] = {}

    def __init__(self, page: int = 0, total: int = 2):
        self.page = page
        self.total = total

    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "page": self.page, "totalPages": self.total, "auctions": []}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Session:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise requests.ConnectionError("temporary")
        return _Response()


def test_fetch_page_retries_connection_error(monkeypatch):
    monkeypatch.setattr(auctions.time, "sleep", lambda _seconds: None)
    session = _Session()
    payload = auctions._fetch_page(session, 0, "", 5)
    assert payload["success"] is True
    assert session.calls == 2


def test_build_index_keeps_lowest_and_counts():
    index = auctions.build_index(
        [
            {"bin": True, "uuid": "a", "item_name": "Enchanted Diamond", "extra": "ENCHANTED_DIAMOND", "starting_bid": 1200},
            {"bin": True, "uuid": "b", "item_name": "Enchanted Diamond", "extra": "ENCHANTED_DIAMOND", "starting_bid": 900},
            {"bin": False, "uuid": "c", "item_name": "Enchanted Diamond", "starting_bid": 1},
        ]
    )
    entry = auctions.lookup_bin(index, "ENCHANTED_DIAMOND")
    assert entry is not None
    assert entry["lowest_bin"] == 900
    assert entry["bin_count"] == 2
