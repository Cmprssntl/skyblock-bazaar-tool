"""行情录制：后台写线程 + 有界队列，UI 线程零阻塞（参考 SimNow TickRecorder）。"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

from .store import HistoryStore

BATCH_SIZE = 500
FLUSH_INTERVAL = 0.5


@dataclass
class RecorderStats:
    running: bool = False
    queued: int = 0
    rows_written: int = 0
    errors: int = 0
    dropped: int = 0
    started_at: float | None = None
    last_write_at: float | None = None


@dataclass
class HistoryRecorder:
    store: HistoryStore
    log: object | None = None
    queue_max: int = 200_000
    stats: RecorderStats = field(default_factory=RecorderStats)

    def __post_init__(self) -> None:
        self._queue: queue.Queue[list[tuple]] = queue.Queue(maxsize=self.queue_max)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        if self.stats.running:
            return
        self._stop.clear()
        self.stats = RecorderStats(running=True, started_at=time.time())
        self._thread = threading.Thread(target=self._loop, name="history-writer", daemon=True)
        self._thread.start()

    def stop(self, flush: bool = True) -> None:
        if not self.stats.running:
            return
        self.stats.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if flush:
            self._flush_remaining()
        self.store.close()

    # ------------------------------------------------------------ 入队
    def record(self, rows: list[tuple]) -> None:
        if not rows:
            return
        try:
            self._queue.put_nowait(rows)
        except queue.Full:
            self.stats.dropped += len(rows)
            if self.log:
                self.log.warning("录制队列已满，丢弃 %d 行", len(rows))

    # ------------------------------------------------------------ 写盘
    def _loop(self) -> None:
        pending: list[tuple] = []
        while not self._stop.is_set():
            try:
                pending.extend(self._queue.get(timeout=FLUSH_INTERVAL))
            except queue.Empty:
                pass
            # 一次最多写 BATCH_SIZE 行，避免单次事务过大
            while len(pending) >= BATCH_SIZE:
                self._write(pending[:BATCH_SIZE])
                pending = pending[BATCH_SIZE:]
            if pending and (self._queue.empty() or self._stop.is_set()):
                self._write(pending)
                pending = []
        if pending:
            self._write(pending)
        self.stats.queued = 0

    def _write(self, rows: list[tuple]) -> None:
        try:
            written = self.store.write(rows)
            self.stats.rows_written += written
            self.stats.last_write_at = time.time()
        except Exception as exc:  # 数据库异常不应杀死录制线程
            self.stats.errors += 1
            if self.log:
                self.log.error("历史写盘失败：%s", exc)

    def _flush_remaining(self) -> None:
        rows: list[tuple] = []
        while True:
            try:
                rows.extend(self._queue.get_nowait())
            except queue.Empty:
                break
        if rows:
            self._write(rows)

    # ------------------------------------------------------------ 快照转换
    @staticmethod
    def rows_from_snapshot(quotes: dict[str, dict], items: list[str], ts: int | None = None) -> list[tuple]:
        ts = int(ts or time.time())
        rows: list[tuple] = []
        for item in items:
            quote = quotes.get(item)
            if not quote:
                continue
            rows.append(
                (
                    item,
                    ts,
                    float(quote.get("sell") or 0),   # bid
                    float(quote.get("buy") or 0),    # ask
                    float(quote.get("mid") or 0),
                    int(quote.get("vol_sell") or 0),  # bid depth
                    int(quote.get("vol_buy") or 0),   # ask depth
                    int(quote.get("buyOrders") or 0),
                    int(quote.get("sellOrders") or 0),
                    float(quote.get("week_buy") or 0),
                    float(quote.get("week_sell") or 0),
                )
            )
        return rows
