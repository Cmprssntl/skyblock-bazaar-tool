"""K 线页：物品选择、周期、价格口径、自选记录列表。"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...config import HistorySettings
from ...data.market import MarketSnapshot
from ...history.bars import PERIOD_SECONDS, PERIODS, build_bars, summarize
from ...history.store import HistoryStore
from ..chart import KlineChart
from ..format import format_age, format_int
from ..theme import MUTED

PRICE_MODES = (("中间价", "mid"), ("收购价", "buy"), ("出售价", "sell"))


class ChartPage(QWidget):
    refreshRequested = Signal()
    watchlistChanged = Signal()
    statusMessage = Signal(str)

    def __init__(self, store: HistoryStore, history: HistorySettings, log, parent=None):
        super().__init__(parent)
        self.store = store
        self.history = history
        self.log = log
        self._snapshot: MarketSnapshot | None = None
        self._period = "15m"
        self._price = "mid"
        self._item = ""
        self._names: list[str] = []
        self._build()

    # ------------------------------------------------------------ 界面
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        toolbar.addWidget(QLabel("物品"))
        self.item_box = QComboBox()
        self.item_box.setEditable(True)
        self.item_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_box.setMinimumWidth(300)
        self.item_box.lineEdit().setPlaceholderText("输入物品 ID，如 ENCHANTED_DIAMOND")
        self.item_box.currentTextChanged.connect(self._on_item_changed)
        toolbar.addWidget(self.item_box, 1)

        self.price_box = QComboBox()
        for label, key in PRICE_MODES:
            self.price_box.addItem(label, key)
        self.price_box.currentIndexChanged.connect(self._on_price_changed)
        toolbar.addWidget(self.price_box)

        self.period_buttons: dict[str, QPushButton] = {}
        for label, key, _seconds in PERIODS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setFixedWidth(52)
            button.setChecked(key == self._period)
            button.clicked.connect(lambda _=False, k=key: self._set_period(k))
            toolbar.addWidget(button)
            self.period_buttons[key] = button

        self.record_btn = QPushButton("记录此物品")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._toggle_record)
        toolbar.addWidget(self.record_btn)

        refresh = QPushButton("立即刷新")
        refresh.setProperty("accent", True)
        refresh.clicked.connect(self.refreshRequested)
        toolbar.addWidget(refresh)
        outer.addLayout(toolbar)

        stats = QHBoxLayout()
        stats.setSpacing(18)
        self.stats: dict[str, QLabel] = {}
        for key, caption in (
            ("last", "最新"),
            ("change", "涨跌"),
            ("range", "全区间"),
            ("volume", "全区间成交量"),
            ("rows", "记录 / K线"),
            ("size", "数据库"),
            ("updated", "最后记录"),
        ):
            box = QWidget()
            inner = QVBoxLayout(box)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(0)
            value = QLabel("--")
            value.setObjectName("stat")
            caption_label = QLabel(caption)
            caption_label.setObjectName("statLabel")
            inner.addWidget(value)
            inner.addWidget(caption_label)
            stats.addWidget(box)
            self.stats[key] = value
        stats.addStretch(1)
        self.hint = QLabel("滚轮缩放 · 拖拽平移 · 双击回到最新")
        self.hint.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        stats.addWidget(self.hint)
        outer.addLayout(stats)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.chart = KlineChart()
        split.addWidget(self.chart)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 0, 0, 0)
        side_layout.setSpacing(6)
        title = QLabel("自选 / 记录列表")
        title.setObjectName("title")
        side_layout.addWidget(title)
        self.watch_list = QListWidget()
        self.watch_list.itemDoubleClicked.connect(self._on_watch_activated)
        side_layout.addWidget(self.watch_list, 1)
        row = QHBoxLayout()
        add = QPushButton("加入当前")
        remove = QPushButton("移出选中")
        export = QPushButton("导出 CSV")
        add.clicked.connect(lambda: self._set_watch(self._item, True))
        remove.clicked.connect(self._remove_selected)
        export.clicked.connect(self._export_csv)
        row.addWidget(add)
        row.addWidget(remove)
        side_layout.addLayout(row)
        side_layout.addWidget(export)
        side.setMinimumWidth(220)
        side.setMaximumWidth(320)
        split.addWidget(side)
        split.setStretchFactor(0, 1)
        split.setSizes([900, 240])
        outer.addWidget(split, 1)

        self._reload_watchlist()

    # ------------------------------------------------------------ 外部数据
    def set_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._snapshot = snapshot
        names = snapshot.item_names()
        if names != self._names:
            self._names = names
            completer = QCompleter(names, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setMaxVisibleItems(18)
            self.item_box.setCompleter(completer)
        if not self._item:
            default = self.history.watchlist[0] if self.history.watchlist else ""
            if not default and names:
                default = "ENCHANTED_DIAMOND" if "ENCHANTED_DIAMOND" in names else names[0]
            if default:
                self.select_item(default)
                return
        self._refresh_chart()

    def select_item(self, item_id: str) -> None:
        item_id = str(item_id or "").strip().upper()
        if not item_id:
            return
        self._item = item_id
        self.item_box.blockSignals(True)
        self.item_box.setEditText(item_id)
        self.item_box.blockSignals(False)
        self._sync_record_button()
        self._refresh_chart()

    def current_item(self) -> str:
        return self._item

    # ------------------------------------------------------------ 交互
    def _on_item_changed(self, text: str) -> None:
        item = str(text or "").strip().upper()
        if not item or item == self._item:
            return
        self._item = item
        self._sync_record_button()
        self._refresh_chart()

    def _on_price_changed(self, _index: int) -> None:
        self._price = self.price_box.currentData() or "mid"
        self._refresh_chart()

    def _set_period(self, key: str) -> None:
        self._period = key
        for name, button in self.period_buttons.items():
            button.setChecked(name == key)
        self._refresh_chart()

    def _toggle_record(self) -> None:
        self._set_watch(self._item, self.record_btn.isChecked())

    def _set_watch(self, item: str, wanted: bool) -> None:
        if not item:
            return
        watchlist = self.history.watchlist
        if wanted and item not in watchlist:
            watchlist.append(item)
        elif not wanted and item in watchlist:
            watchlist.remove(item)
        self._reload_watchlist()
        self._sync_record_button()
        self.watchlistChanged.emit()
        self.statusMessage.emit(f"{item} 已{'加入' if wanted else '移出'}记录列表")

    def _remove_selected(self) -> None:
        row = self.watch_list.currentRow()
        if row < 0:
            return
        item = self.watch_list.item(row).text()
        self._set_watch(item, False)

    def _on_watch_activated(self, item: QListWidgetItem) -> None:
        self.select_item(item.text())

    def _reload_watchlist(self) -> None:
        self.watch_list.clear()
        for item in self.history.watchlist:
            self.watch_list.addItem(item)

    def refresh_watchlist(self) -> None:
        self._reload_watchlist()
        self._sync_record_button()

    def _sync_record_button(self) -> None:
        self.record_btn.setChecked(self._item in self.history.watchlist)
        self.record_btn.setText("已加入记录" if self.record_btn.isChecked() else "记录此物品")

    # ------------------------------------------------------------ 图表
    def _refresh_chart(self) -> None:
        if not self._item:
            return
        rows = self.store.query(self._item, limit=20000)
        live = self._live_row()
        if live is not None and (not rows or live[0] > rows[-1][0]):
            rows = [*rows, live]
        period = PERIOD_SECONDS.get(self._period, 60)
        bars = build_bars(rows, period, self._price)
        label = next((text for text, key in PRICE_MODES if key == self._price), "中间价")
        self.chart.set_data(self._item, bars, period, label)
        self._update_stats(bars)
        self._sync_record_button()

    def _live_row(self) -> tuple | None:
        if not self._snapshot:
            return None
        quote = self._snapshot.quote(self._item)
        if not quote:
            return None
        return (
            int(self._snapshot.bazaar_updated or time.time()),
            float(quote.get("sell") or 0),
            float(quote.get("buy") or 0),
            float(quote.get("mid") or 0),
            float(quote.get("week_buy") or 0),
            float(quote.get("week_sell") or 0),
        )

    def _update_stats(self, bars) -> None:
        summary = summarize(bars)
        if not summary:
            for label in self.stats.values():
                label.setText("--")
            self.stats["change"].setStyleSheet("")
        else:
            self.stats["last"].setText(f"{summary['last']:,.1f}")
            change = summary["change"]
            self.stats["change"].setText(f"{change:+,.1f} ({summary['change_pct']:+.2f}%)")
            self.stats["change"].setStyleSheet("color:#ff5c6c;" if change > 0 else "color:#2ecc71;" if change < 0 else "")
            self.stats["range"].setText(f"{summary['low']:,.1f} ~ {summary['high']:,.1f}")
            self.stats["volume"].setText(format_int(summary["volume"]))
            self.stats["rows"].setText(f"{format_int(self.store.count(self._item))} 条 / {summary['bars']} 根")
            self.stats["size"].setText(self._human_size(self.store.size_bytes()))
            updated = self.store.latest_ts(self._item)
            self.stats["updated"].setText(format_age(time.time() - updated) if updated else "从未")
        self.hint.setText(
            f"滚轮缩放 · 拖拽平移 · 双击回到最新 · 周期 {self._period} · 量柱为 7 日成交量增量（近似）"
        )

    @staticmethod
    def _human_size(size: int) -> str:
        for unit, scale in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
            if size >= scale:
                return f"{size / scale:.1f} {unit}"
        return f"{size} B"

    # ------------------------------------------------------------ 导出
    def _export_csv(self) -> None:
        if not self._item:
            return
        default = f"{self._item}.csv"
        path, _filter = QFileDialog.getSaveFileName(self, "导出历史 CSV", default, "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.store.export_csv(self._item, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self.statusMessage.emit(f"已导出 {count:,} 行到 {path}")
