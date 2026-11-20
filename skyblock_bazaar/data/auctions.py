"""Auction House：并发分页下载，只保留 BIN，按物品建立最低一口价索引。"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

AUCTIONS_URL = "https://api.hypixel.net/v2/skyblock/auctions"
HEADERS = {"User-Agent": "skyblock-bazaar-tool/4.0"}
PAGE_ATTEMPTS = 4
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_WORKERS = 4

_STRIP_CODES = re.compile(r"§.")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class AuctionError(RuntimeError):
    pass


def normalize_key(value) -> str:
    text = _STRIP_CODES.sub("", str(value or "")).strip().lower()
    return _NON_ALNUM.sub("_", text).strip("_")


def _fetch_page(session: requests.Session, page: int, api_key: str, timeout: int) -> dict:
    params = {"page": page}
    if api_key:
        params["key"] = api_key
    last_error: Exception | None = None
    for attempt in range(1, PAGE_ATTEMPTS + 1):
        delay = 2 ** (attempt - 1)
        # 连接错误默认重试；HTTP 4xx 才停止
        retryable = True
        try:
            with session.get(AUCTIONS_URL, headers=HEADERS, params=params, timeout=timeout) as response:
                retryable = response.status_code in RETRY_STATUS
                if response.status_code == 429:
                    try:
                        delay = max(delay, min(60, float(response.headers.get("Retry-After", delay))))
                    except (TypeError, ValueError):
                        pass
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not payload.get("success"):
                    raise AuctionError(str(payload.get("cause") if isinstance(payload, dict) else "返回失败"))
                if payload.get("page") != page or not isinstance(payload.get("auctions"), list):
                    raise AuctionError("返回的页码或拍卖列表无效")
                if type(payload.get("totalPages")) is not int or payload["totalPages"] <= page:
                    raise AuctionError("返回的总页数无效")
                return payload
        except (requests.RequestException, ValueError, AuctionError) as exc:
            last_error = exc
            if not retryable and not isinstance(exc, (AuctionError, ValueError)):
                break
            if attempt == PAGE_ATTEMPTS:
                break
            time.sleep(delay)
    detail = re.sub(r"(?i)([?&]key=)[^&\s]+", r"\1[REDACTED]", str(last_error))
    raise AuctionError(f"第 {page + 1} 页请求失败（已尝试 {PAGE_ATTEMPTS} 次）：{detail}")


def _bin_entry(index: dict, key: str, price: float, item_name: str) -> None:
    if not key:
        return
    current = index.get(key)
    if current is None:
        index[key] = {"lowest_bin": price, "bin_count": 1, "item_name": item_name}
        return
    if price < current["lowest_bin"]:
        current["lowest_bin"] = price
    current["bin_count"] += 1


def build_index(auctions: list[dict]) -> dict:
    index: dict = {}
    for auction in auctions:
        if not isinstance(auction, dict) or not auction.get("bin"):
            continue
        try:
            price = float(auction.get("starting_bid", 0) or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        name = str(auction.get("item_name") or "")
        extra = str(auction.get("extra") or "")
        keys = {extra.upper(), normalize_key(extra), normalize_key(name)}
        keys.discard("")
        for key in keys:
            _bin_entry(index, key, price, name)
    return index


def fetch_index(
    api_key: str = "",
    timeout: int = 30,
    workers: int = MAX_WORKERS,
    progress=None,
) -> tuple[dict, int, str]:
    """下载全部页面并返回 (index, updated, message)。任何一页失败都抛 AuctionError。"""
    started = time.time()
    with requests.Session() as session:
        first = _fetch_page(session, 0, api_key, timeout)
        total_pages = first["totalPages"]
        pages: dict[int, list] = {0: first["auctions"]}
        if progress:
            progress(1, total_pages)
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(_fetch_page, session, page, api_key, timeout): page
                for page in range(1, total_pages)
            }
            for done, future in enumerate(as_completed(futures), start=1):
                page = futures[future]
                pages[page] = future.result()  # 失败直接抛 AuctionError
                if progress:
                    progress(done + 1, total_pages)

    seen: set[str] = set()
    index: dict = {}
    for page in sorted(pages):
        for auction in pages[page]:
            if not isinstance(auction, dict) or not auction.get("bin"):
                continue
            uuid = auction.get("uuid")
            if uuid:
                if uuid in seen:
                    continue
                seen.add(uuid)
            try:
                price = float(auction.get("starting_bid", 0) or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            name = str(auction.get("item_name") or "")
            extra = str(auction.get("extra") or "")
            keys = {extra.upper(), normalize_key(extra), normalize_key(name)}
            keys.discard("")
            for key in keys:
                _bin_entry(index, key, price, name)

    elapsed = time.time() - started
    return index, int(time.time()), f"Auction House 已更新（{len(seen)} 个 BIN，{total_pages} 页，{elapsed:.1f}s）"


def lookup_bin(index: dict, item_id: str, display_name: str = "") -> dict | None:
    for key in (str(item_id or "").upper(), normalize_key(item_id), normalize_key(display_name)):
        entry = index.get(key)
        if entry:
            return entry
    return None
