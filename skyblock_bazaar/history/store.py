"""本地行情历史：SQLite（WAL）存储，按物品查询。"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from ..paths import data_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticks (
    item        TEXT    NOT NULL,
    ts          INTEGER NOT NULL,
    bid         REAL    NOT NULL,
    ask         REAL    NOT NULL,
    mid         REAL    NOT NULL,
    bid_depth   INTEGER,
    ask_depth   INTEGER,
    bid_orders  INTEGER,
    ask_orders  INTEGER,
    buy_week    REAL,
    sell_week   REAL,
    PRIMARY KEY (item, ts)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_ticks_ts ON ticks(ts);
"""

COLUMNS = (
    "item", "ts", "bid", "ask", "mid",
    "bid_depth", "ask_depth", "bid_orders", "ask_orders", "buy_week", "sell_week",
)


class HistoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_path("history.db")
        self._write_lock = threading.Lock()
        self._write_conn: sqlite3.Connection | None = None
        self._read_conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------ 连接
    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA)
        return conn

    @property
    def writer(self) -> sqlite3.Connection:
        with self._write_lock:
            if self._write_conn is None:
                self._write_conn = self._connect()
            return self._write_conn

    @property
    def reader(self) -> sqlite3.Connection:
        if self._read_conn is None:
            self._read_conn = self._connect()
        return self._read_conn

    def close(self) -> None:
        for conn in (self._write_conn, self._read_conn):
            try:
                if conn is not None:
                    conn.close()
            except sqlite3.Error:
                pass
        self._write_conn = None
        self._read_conn = None

    # ------------------------------------------------------------ 写入
    def write(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        placeholders = ",".join("?" for _ in COLUMNS)
        sql = f"INSERT OR REPLACE INTO ticks ({','.join(COLUMNS)}) VALUES ({placeholders})"
        with self._write_lock:
            if self._write_conn is None:
                self._write_conn = self._connect()
            conn = self._write_conn
            try:
                with conn:
                    conn.executemany(sql, rows)
                return len(rows)
            except sqlite3.Error:
                # 连接异常时重建一次，避免录制线程永久失效
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
                self._write_conn = None
                raise

    # ------------------------------------------------------------ 查询
    def query(self, item: str, since: int | None = None, limit: int = 20000) -> list[tuple]:
        sql = "SELECT ts, bid, ask, mid, buy_week, sell_week FROM ticks WHERE item = ?"
        params: list = [item]
        if since is not None:
            sql += " AND ts >= ?"
            params.append(int(since))
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(int(limit))
        rows = self.reader.execute(sql, params).fetchall()
        rows.reverse()
        return rows

    def latest_ts(self, item: str | None = None) -> int:
        if item:
            row = self.reader.execute("SELECT MAX(ts) FROM ticks WHERE item = ?", (item,)).fetchone()
        else:
            row = self.reader.execute("SELECT MAX(ts) FROM ticks").fetchone()
        return int(row[0] or 0) if row else 0

    def count(self, item: str | None = None) -> int:
        if item:
            row = self.reader.execute("SELECT COUNT(*) FROM ticks WHERE item = ?", (item,)).fetchone()
        else:
            row = self.reader.execute("SELECT COUNT(*) FROM ticks").fetchone()
        return int(row[0] or 0)

    def size_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal", "-shm"):
            try:
                total += Path(f"{self.path}{suffix}").stat().st_size
            except OSError:
                continue
        return total

    def purge(self, older_than_ts: int) -> int:
        with self._write_lock:
            if self._write_conn is None:
                self._write_conn = self._connect()
            with self._write_conn as conn:
                cursor = conn.execute("DELETE FROM ticks WHERE ts < ?", (int(older_than_ts),))
            return cursor.rowcount

    def purge_days(self, days: int) -> int:
        return self.purge(int(time.time()) - max(1, days) * 86400)

    def vacuum(self) -> None:
        try:
            self.reader.execute("VACUUM")
        except sqlite3.Error:
            pass

    def export_csv(self, item: str, path: Path) -> int:
        rows = self.query(item, limit=1_000_000)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            fh.write("ts,bid,ask,mid,buy_week,sell_week\n")
            for row in rows:
                fh.write(",".join(str(value) for value in row) + "\n")
        return len(rows)
