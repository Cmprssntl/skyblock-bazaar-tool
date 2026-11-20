"""数据刷新服务：QThreadPool 后台请求，信号回主线程。"""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from ..data.auctions import AuctionError, fetch_index
from ..data.bazaar import fetch_bazaar
from ..data.cache import MarketCache


@dataclass
class RefreshResult:
    source: str
    payload: object
    updated: int
    stale: bool
    message: str


class _WorkerSignals(QObject):
    finished = Signal(object)
    progress = Signal(str, int, int)
    failed = Signal(str, str)


class _Worker(QRunnable):
    def __init__(self, source: str, api_key: str, cache: MarketCache, log):
        super().__init__()
        self.source = source
        self.api_key = api_key
        self.cache = cache
        self.log = log
        self.signals = _WorkerSignals()

    def run(self) -> None:  # noqa: D401 - QRunnable 接口
        try:
            if self.source == "bazaar":
                self._bazaar()
            elif self.source == "auction":
                self._auction()
        except Exception as exc:  # 兜底，避免线程静默死亡
            if self.log:
                self.log.exception("刷新失败：%s", exc)
            self.signals.failed.emit(self.source, str(exc))

    def _bazaar(self) -> None:
        rows, message = fetch_bazaar(self.api_key)
        if rows:
            updated = int(time.time())
            try:
                self.cache.save_bazaar(rows, updated)
            except OSError as exc:
                if self.log:
                    self.log.warning("Bazaar 缓存写入失败：%s", exc)
            self.signals.finished.emit(RefreshResult("bazaar", rows, updated, False, message))
            return
        rows, updated = self.cache.load_bazaar()
        if rows:
            self.signals.finished.emit(
                RefreshResult("bazaar", rows, updated, True, f"{message}；使用本地缓存（{len(rows)} 项）")
            )
        else:
            self.signals.failed.emit("bazaar", message)

    def _auction(self) -> None:
        try:
            index, updated, message = fetch_index(
                self.api_key, progress=lambda done, total: self.signals.progress.emit("auction", done, total)
            )
        except AuctionError as exc:
            index, updated = self.cache.load_bin_index()
            if index:
                self.signals.finished.emit(
                    RefreshResult("auction", index, updated, True, f"{exc}；使用本地缓存（{len(index)} 个索引）")
                )
            else:
                self.signals.failed.emit("auction", str(exc))
            return
        try:
            self.cache.save_bin_index(index, updated)
        except OSError as exc:
            if self.log:
                self.log.warning("AH 缓存写入失败：%s", exc)
        self.signals.finished.emit(RefreshResult("auction", index, updated, False, message))


class RefreshService(QObject):
    result = Signal(object)
    failed = Signal(str, str)
    progress = Signal(str, int, int)
    busy_changed = Signal(bool)

    def __init__(self, cache: MarketCache, log, parent=None):
        super().__init__(parent)
        self.cache = cache
        self.log = log
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self._active: set[str] = set()

    def refresh(self, source: str = "all", api_key: str = "") -> bool:
        sources = ("bazaar", "auction") if source == "all" else (source,)
        started = False
        for item in sources:
            if item in self._active:
                continue
            self._active.add(item)
            worker = _Worker(item, api_key, self.cache, self.log)
            worker.signals.finished.connect(self._on_finished)
            worker.signals.failed.connect(self._on_failed)
            worker.signals.progress.connect(self.progress)
            self.pool.start(worker)
            started = True
        if started:
            self.busy_changed.emit(True)
        return started

    def busy(self, source: str | None = None) -> bool:
        if source is None:
            return bool(self._active)
        return source in self._active

    def _on_finished(self, result: RefreshResult) -> None:
        self._active.discard(result.source)
        self.result.emit(result)
        if not self._active:
            self.busy_changed.emit(False)

    def _on_failed(self, source: str, message: str) -> None:
        self._active.discard(source)
        self.failed.emit(source, message)
        if not self._active:
            self.busy_changed.emit(False)

    def shutdown(self) -> None:
        self.pool.clear()
        self.pool.waitForDone(3000)
