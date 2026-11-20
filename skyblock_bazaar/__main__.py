"""入口：GUI（默认）或 `record` 子命令无头录制。"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time

from . import __version__
from .config import ConfigStore
from .data.bazaar import fetch_bazaar
from .data.cache import MarketCache
from .data.library import RecipeLibrary
from .history.recorder import HistoryRecorder
from .history.store import HistoryStore
from .log import get_logger
from .paths import DATA_DIR, RESOURCE_DIR, ensure_data_dir


def _base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skyblock-bazaar", description="SkyBlock Bazaar Tool 4.0")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs="?", choices=["gui", "record"], default="gui")
    parser.add_argument("--items", help="record：逗号分隔的物品 ID；默认使用自选列表")
    parser.add_argument("--interval", type=int, help="record：采样间隔（秒）")
    parser.add_argument("--once", action="store_true", help="record：只采样一次")
    return parser


def run_record(args) -> int:
    ensure_data_dir()
    log = get_logger("record", DATA_DIR / "logs")
    settings = ConfigStore().load()
    items = [item.strip().upper() for item in (args.items or "").split(",") if item.strip()]
    items = items or [item.upper() for item in settings.history.watchlist]
    if not items:
        print("没有要记录的物品：用 --items A,B 指定，或先在 GUI 里加入自选。")
        return 2
    interval = max(15, args.interval or settings.history.interval_sec)
    store = HistoryStore()
    store.purge_days(settings.history.retention_days)
    recorder = HistoryRecorder(store, log)
    recorder.start()
    print(f"开始录制 {len(items)} 个物品，每 {interval}s 一拍 -> {store.path}")
    print("物品：" + ", ".join(items))
    samples = 0
    stop = threading.Event()
    try:
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    except (ValueError, OSError):
        pass
    try:
        while not stop.is_set():
            rows, message = fetch_bazaar(settings.api_key)
            if rows:
                quotes = {row["name"]: row for row in rows}
                recorder.record(HistoryRecorder.rows_from_snapshot(quotes, items))
                samples += 1
                print(f"[{time.strftime('%H:%M:%S')}] {message} · 采样 {samples} · 写入 {recorder.stats.rows_written}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] {message}")
            if args.once:
                break
            stop.wait(interval)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在停止…")
    finally:
        recorder.stop()
        print(f"已停止：写入 {recorder.stats.rows_written} 行，错误 {recorder.stats.errors} 次")
    return 0


def run_gui() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    from .ui.theme import apply

    ensure_data_dir()
    log = get_logger("ui", DATA_DIR / "logs")
    config_store = ConfigStore()
    settings = config_store.load()
    cache = MarketCache()
    library = RecipeLibrary.load(log)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("SkyBlock Bazaar Tool")
    app.setApplicationDisplayName("SkyBlock Bazaar")
    app.setApplicationVersion(__version__)
    icon = RESOURCE_DIR / "bazaar.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    apply(app)

    window = MainWindow(settings, config_store, cache, library, log)
    window.show()
    return app.exec()


def main(argv=None) -> int:
    args = _base_parser().parse_args(argv)
    if args.command == "record":
        return run_record(args)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
