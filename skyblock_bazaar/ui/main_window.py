"""主窗口：工具栏、标签页、状态栏、自动刷新、录制、快捷键。"""

from __future__ import annotations

import copy
import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QWidget,
)

from ..config import AppSettings, ConfigStore, HistorySettings, PageSettings
from ..data.cache import MarketCache
from ..data.library import RecipeLibrary
from ..data.market import MarketSnapshot
from ..history.recorder import HistoryRecorder
from ..history.store import HistoryStore
from ..services.hotkeys import HotkeyService
from ..services.refresh import RefreshResult, RefreshService
from ..services.sequences import is_standard_sequence
from .format import format_age, format_int
from .geometry import apply_geometry
from .pages.base import PageWidget
from .pages.chart_page import ChartPage
from .pages.specs import ALL_SPECS
from .theme import MUTED
from .widgets.api_key_dialog import ApiKeyDialog
from .widgets.shortcut_dialog import ShortcutDialog

TOOLBAR_BUTTONS = {
    "refresh": "刷新全部数据",
    "refresh_bazaar": "刷新BZ数据",
    "refresh_auction": "刷新AH数据",
    "param": "参数设置面板",
    "save": "保存当前设置",
    "load": "加载保存设置",
    "reset": "重置全部默认",
    "search": "搜索",
    "record": "录制",
    "auto": "自动刷新",
    "topmost": "窗口置顶",
    "shortcut": "快捷键设置",
    "api": "输入API（可选）",
}

TAB_ACTIONS = {
    "tab_bazaar": 0,
    "tab_craft": 1,
    "tab_forge": 2,
    "tab_enchant": 3,
    "tab_chart": 4,
}

KEY_NAMES = {
    "PAGE_UP": "PgUp",
    "PAGE_DOWN": "PgDown",
    "RETURN": "Return",
    "ENTER": "Return",
    "ESCAPE": "Esc",
    "SPACE": "Space",
    "BACKSPACE": "Backspace",
    "TAB": "Tab",
    "DELETE": "Del",
    "INSERT": "Ins",
    "HOME": "Home",
    "END": "End",
    "UP": "Up",
    "DOWN": "Down",
    "LEFT": "Left",
    "RIGHT": "Right",
}
MOD_NAMES = {"CTRL": "Ctrl", "ALT": "Alt", "SHIFT": "Shift", "META": "Meta"}
TEXT_INPUTS = (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit, QComboBox)
MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
}
AUTO_INTERVALS = (("30 秒", 30), ("1 分钟", 60), ("2 分钟", 120), ("5 分钟", 300), ("关闭", 0))


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        store: ConfigStore,
        cache: MarketCache,
        library: RecipeLibrary,
        log,
    ):
        super().__init__()
        self.settings = settings
        self.store = store
        self.cache = cache
        self.library = library
        self.log = log

        self.snapshot = MarketSnapshot()
        self.refresh_service = RefreshService(cache, log, self)
        self.hotkeys = HotkeyService(self)

        self.history_store = HistoryStore()
        self.recorder = HistoryRecorder(self.history_store, log)
        self._shortcuts: list = []
        self._combo_bindings: dict[str, tuple[set[str], str, str]] = {}
        self._single_bindings: dict[str, str] = {}
        self._held: set[str] = set()
        self._buttons: dict[str, QToolButton] = {}
        self._filter_installed = False
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setSingleShot(True)
        self._dirty_timer.setInterval(1200)
        self._dirty_timer.timeout.connect(lambda: self._save_settings(quiet=True))

        self.setWindowTitle("SkyBlock Bazaar Tool 4.0")
        self.resize(1520, 880)
        self.setMinimumSize(1180, 700)
        self._build()
        self._load_cache()
        self._start_history()
        self._connect_services()
        self._apply_shortcuts()
        self._restore_settings()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_status)
        self._tick_timer.start(1000)

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self._configure_auto_timer()
        self.ah_timer = QTimer(self)
        self.ah_timer.timeout.connect(lambda: self._refresh("auction", quiet=True))
        self.ah_timer.start(6 * 3600 * 1000)

        self._update_status()
        QTimer.singleShot(400, self._initial_refresh)

    # ------------------------------------------------------------ 构建
    def _build(self) -> None:
        self._build_toolbar()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.pages: dict[str, PageWidget] = {}
        for key, factory in ALL_SPECS.items():
            spec = factory()
            page = PageWidget(spec, self.library, self.settings.page(key), self.settings.dialogs)
            page.chartRequested.connect(self._show_chart)
            page.watchlistToggleRequested.connect(self._toggle_watch)
            page.settingsChanged.connect(self._schedule_save)
            self.pages[key] = page
            self.tabs.addTab(page, spec.title)
        self.chart_page = ChartPage(self.history_store, self.settings.history, self.log)
        self.chart_page.refreshRequested.connect(lambda: self._refresh("bazaar"))
        self.chart_page.watchlistChanged.connect(self._schedule_save)
        self.chart_page.statusMessage.connect(lambda text: self.statusBar().showMessage(text, 6000))
        self.tabs.addTab(self.chart_page, "K 线")
        self.setCentralWidget(self.tabs)

        bar = self.statusBar()
        self.data_label = QLabel("BZ --")
        self.ah_label = QLabel("AH --")
        self.record_label = QLabel("录制 --")
        self.auto_label = QLabel("自动刷新 --")
        for label in (self.data_label, self.ah_label, self.record_label, self.auto_label):
            label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            bar.addPermanentWidget(label)
        bar.showMessage("就绪")

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("main")
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        self._rebuild_toolbar()

    def _rebuild_toolbar(self) -> None:
        self.toolbar.clear()
        self._buttons.clear()
        brand = QLabel("●  SkyBlock Bazaar")
        brand.setObjectName("brand")
        brand.setStyleSheet("padding: 0 10px; color:#e0b060;")
        self.toolbar.addWidget(brand)
        order = [bid for bid in self.settings.button_order if bid in TOOLBAR_BUTTONS]
        order += [bid for bid in TOOLBAR_BUTTONS if bid not in order]
        self.settings.button_order = order
        for bid in order:
            button = QToolButton()
            button.setText(TOOLBAR_BUTTONS[bid])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.clicked.connect(lambda _=False, action=bid: self._dispatch(action))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, action=bid: self._button_menu(action, pos))
            self.toolbar.addWidget(button)
            self._buttons[bid] = button
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self._sync_button_text()

    def _button_menu(self, bid: str, pos) -> None:
        menu = QMenu(self)
        if bid == "auto":
            for label, seconds in AUTO_INTERVALS:
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(
                    (seconds == 0 and not self.settings.history.auto_refresh)
                    or (seconds > 0 and self.settings.history.auto_refresh and self.settings.history.interval_sec == seconds)
                )
                action.triggered.connect(lambda _=False, value=seconds: self._set_auto_interval(value))
        else:
            left = menu.addAction("← 左移此按钮")
            right = menu.addAction("→ 右移此按钮")
            menu.addSeparator()
            label = menu.addAction(TOOLBAR_BUTTONS.get(bid, bid))
            label.setEnabled(False)
            chosen = menu.exec(self._buttons[bid].mapToGlobal(pos))
            if chosen is left:
                self._move_button(bid, -1)
            elif chosen is right:
                self._move_button(bid, 1)
            return
        menu.exec(self._buttons[bid].mapToGlobal(pos))

    def _set_auto_interval(self, seconds: int) -> None:
        self.settings.history.interval_sec = seconds or 60
        self.settings.history.auto_refresh = seconds > 0
        self._configure_auto_timer()
        self._schedule_save()
        self._update_status()
        self.statusBar().showMessage(
            f"自动刷新：{'关闭' if seconds == 0 else f'每 {seconds} 秒'}", 4000
        )

    def _move_button(self, bid: str, delta: int) -> None:
        order = list(self.settings.button_order)
        if bid not in order:
            return
        index = order.index(bid)
        target = index + delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.settings.button_order = order
            self._rebuild_toolbar()
            self._schedule_save()

    def _sync_button_text(self) -> None:
        if "record" in self._buttons:
            self._buttons["record"].setText("录制：开" if self.settings.history.enabled else "录制：关")
        if "auto" in self._buttons:
            self._buttons["auto"].setText(
                "自动刷新：关" if not self.settings.history.auto_refresh else "自动刷新：开"
            )
        if "topmost" in self._buttons:
            self._buttons["topmost"].setText("取消置顶" if self.settings.topmost else "窗口置顶")

    # ------------------------------------------------------------ 设置恢复
    def _restore_settings(self) -> None:
        apply_geometry(self, self.settings.window)
        if self.settings.window.get("maximized"):
            self.showMaximized()
        if self.settings.topmost:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        try:
            tabs = [*self.pages, "chart"]
            index = tabs.index(self.settings.active_page)
        except ValueError:
            index = 0
        if index >= 0:
            self.tabs.setCurrentIndex(index)
        self._sync_button_text()

    def _load_cache(self) -> None:
        rows, updated = self.cache.load_bazaar()
        if rows:
            self.snapshot.set_bazaar(rows, updated, stale=True)
        index, auction_updated = self.cache.load_bin_index()
        if index:
            self.snapshot.set_bin_index(index, auction_updated, stale=True)
        if self.snapshot.bazaar:
            self._apply_snapshot()

    def _start_history(self) -> None:
        try:
            purged = self.history_store.purge_days(self.settings.history.retention_days)
            if purged:
                if self.log:
                    self.log.info("清理过期历史 %d 行", purged)
                self.history_store.vacuum()
        except Exception as exc:
            if self.log:
                self.log.warning("清理历史失败：%s", exc)
        if self.settings.history.enabled:
            self.recorder.start()

    # ------------------------------------------------------------ 数据
    def _connect_services(self) -> None:
        self.refresh_service.result.connect(self._on_refresh_result)
        self.refresh_service.failed.connect(self._on_refresh_failed)
        self.refresh_service.progress.connect(self._on_refresh_progress)
        self.refresh_service.busy_changed.connect(self._on_busy)
        self.hotkeys.triggered.connect(self._dispatch)
        self.hotkeys.statusChanged.connect(self._on_hotkey_status)

    def _initial_refresh(self) -> None:
        now = int(time.time())
        age = now - self.snapshot.bazaar_updated if self.snapshot.bazaar_updated else 10**9
        if not self.snapshot.bazaar or age > 120:
            self._refresh("bazaar", quiet=True)
        auction_age = now - self.snapshot.auction_updated if self.snapshot.auction_updated else 10**9
        if not self.snapshot.bin_index or auction_age > 6 * 3600:
            self._refresh("auction", quiet=True)

    def _refresh(self, source: str, quiet: bool = False) -> None:
        if self.refresh_service.busy(source):
            if not quiet:
                self.statusBar().showMessage(f"{source} 请求进行中…", 3000)
            return
        if not self.refresh_service.refresh(source, self.settings.api_key):
            return
        if not quiet:
            label = {"bazaar": "BZ", "auction": "AH", "all": "BZ + AH"}.get(source, source)
            self.statusBar().showMessage(f"已提交 {label} 刷新请求…", 3000)

    def _auto_refresh(self) -> None:
        if self.settings.history.auto_refresh:
            self._refresh("bazaar", quiet=True)

    def _configure_auto_timer(self) -> None:
        interval = self.settings.history.interval_sec
        if self.settings.history.auto_refresh and interval > 0:
            self.auto_timer.start(interval * 1000)
        else:
            self.auto_timer.stop()
        self._sync_button_text()

    def _on_refresh_result(self, result: RefreshResult) -> None:
        if result.source == "bazaar":
            self.snapshot.set_bazaar(result.payload, result.updated, result.stale)
            self._apply_snapshot()
            if not result.stale:
                self._record_watchlist()
        elif result.source == "auction":
            self.snapshot.set_bin_index(result.payload, result.updated, result.stale)
            self._apply_snapshot()
        self.statusBar().showMessage(result.message, 8000)
        self._update_status()

    def _on_refresh_failed(self, source: str, message: str) -> None:
        self.statusBar().showMessage(f"{source} 刷新失败：{message}", 10000)
        if self.log:
            self.log.warning("%s 刷新失败：%s", source, message)

    def _on_refresh_progress(self, source: str, done: int, total: int) -> None:
        if source == "auction":
            self.statusBar().showMessage(f"Auction House 下载中… {done}/{total} 页", 2000)

    def _on_busy(self, busy: bool) -> None:
        for bid in ("refresh", "refresh_bazaar", "refresh_auction"):
            button = self._buttons.get(bid)
            if button:
                button.setEnabled(not busy)

    def _apply_snapshot(self) -> None:
        for key, page in self.pages.items():
            try:
                page.apply_snapshot(self.snapshot)
            except Exception as exc:
                if self.log:
                    self.log.exception("%s 页面计算失败：%s", key, exc)
                self.statusBar().showMessage(f"{page.spec.title} 页面计算失败：{exc}", 8000)
        self.chart_page.set_snapshot(self.snapshot)

    def _record_watchlist(self) -> None:
        watchlist = self.settings.history.watchlist
        if not watchlist or not self.settings.history.enabled:
            return
        rows = HistoryRecorder.rows_from_snapshot(
            self.snapshot.by_id, watchlist, ts=self.snapshot.bazaar_updated or None
        )
        self.recorder.record(rows)

    # ------------------------------------------------------------ 状态栏
    def _update_status(self) -> None:
        now = time.time()
        if self.snapshot.bazaar_updated:
            text = f"BZ {format_age(now - self.snapshot.bazaar_updated)}"
            if self.snapshot.bazaar_stale:
                text += "（缓存）"
            self.data_label.setText(text)
        else:
            self.data_label.setText("BZ --")
        if self.snapshot.auction_updated:
            text = f"AH {format_age(now - self.snapshot.auction_updated)}"
            if self.snapshot.auction_stale:
                text += "（缓存）"
            self.ah_label.setText(text)
        else:
            self.ah_label.setText("AH --")
        stats = self.recorder.stats
        size = self._human_size(self.history_store.size_bytes())
        state = "录制中" if stats.running else "已停止"
        self.record_label.setText(
            f"{state} · 本次 {format_int(stats.rows_written)} 行 · DB {size} · 自选 {len(self.settings.history.watchlist)}"
        )
        if self.settings.history.auto_refresh and self.auto_timer.isActive():
            remaining = max(0, self.auto_timer.remainingTime() // 1000)
            self.auto_label.setText(f"自动刷新 {remaining}s")
        else:
            self.auto_label.setText("自动刷新 关")

    @staticmethod
    def _human_size(size: int) -> str:
        for unit, scale in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
            if size >= scale:
                return f"{size / scale:.1f} {unit}"
        return f"{size} B"

    # ------------------------------------------------------------ 动作
    def _action_callback(self, action: str):
        return {
            "refresh": lambda: self._refresh("all"),
            "refresh_bazaar": lambda: self._refresh("bazaar"),
            "refresh_auction": lambda: self._refresh("auction"),
            "param": self._open_param_panel,
            "save": lambda: self._save_settings(quiet=False),
            "load": self._load_settings,
            "reset": self._reset_defaults,
            "search": self._search,
            "record": self._toggle_recording,
            "auto": self._toggle_auto_refresh,
            "topmost": self._toggle_topmost,
            "shortcut": self._open_shortcuts,
            "api": self._open_api_key,
        }.get(action)

    def _dispatch(self, action: str) -> None:
        if action in TAB_ACTIONS:
            self.tabs.setCurrentIndex(TAB_ACTIONS[action])
            return
        callback = self._action_callback(action)
        if callback:
            callback()

    def _trigger_shortcut(self, action: str, sequence: str) -> None:
        """单键快捷键在输入框里不触发，避免打字时误触。"""
        parts = [part for part in sequence.split("+") if part.strip()]
        if len(parts) < 2 and isinstance(QApplication.focusWidget(), TEXT_INPUTS):
            return
        self._dispatch(action)

    def _open_param_panel(self) -> None:
        widget = self.tabs.currentWidget()
        if isinstance(widget, PageWidget):
            widget.open_param_panel(self)
        else:
            self.statusBar().showMessage("K 线页没有参数面板；请先切换到行情表格", 4000)

    def _search(self) -> None:
        widget = self.tabs.currentWidget()
        if isinstance(widget, PageWidget):
            widget.show_search()
        elif isinstance(widget, ChartPage):
            widget.item_box.setFocus()
            widget.item_box.lineEdit().selectAll()

    def _toggle_recording(self) -> None:
        self.settings.history.enabled = not self.settings.history.enabled
        if self.settings.history.enabled:
            self.recorder.start()
            message = "已开启本地录制"
        else:
            self.recorder.stop()
            message = "已停止本地录制（已有历史保留）"
        self._sync_button_text()
        self._schedule_save()
        self.statusBar().showMessage(message, 5000)

    def _toggle_auto_refresh(self) -> None:
        self.settings.history.auto_refresh = not self.settings.history.auto_refresh
        self._configure_auto_timer()
        self._schedule_save()
        self._update_status()

    def _toggle_topmost(self) -> None:
        self.settings.topmost = not self.settings.topmost
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.topmost)
        self.show()
        self._sync_button_text()
        self._schedule_save()

    def _on_tab_changed(self, index: int) -> None:
        keys = list(self.pages)
        if 0 <= index < len(keys):
            self.settings.active_page = keys[index]
        elif index == len(keys):
            self.settings.active_page = "chart"
        self._schedule_save()

    # ------------------------------------------------------------ 自选 / K 线
    def _show_chart(self, item_id: str) -> None:
        self.tabs.setCurrentWidget(self.chart_page)
        self.chart_page.select_item(item_id)

    def _toggle_watch(self, item_id: str) -> None:
        self.chart_page.select_item(item_id)
        watchlist = self.settings.history.watchlist
        if item_id in watchlist:
            watchlist.remove(item_id)
            self.statusBar().showMessage(f"{item_id} 已移出自选", 4000)
        else:
            watchlist.append(item_id)
            self.statusBar().showMessage(f"{item_id} 已加入自选（将随刷新记录）", 4000)
        self.chart_page.refresh_watchlist()
        self._schedule_save()
        self._update_status()

    # ------------------------------------------------------------ 设置
    def _schedule_save(self) -> None:
        self._dirty_timer.start()

    def _collect_settings(self) -> None:
        rect = self.geometry()
        self.settings.window = {
            "w": rect.width(),
            "h": rect.height(),
            "x": rect.x(),
            "y": rect.y(),
            "maximized": self.isMaximized(),
        }
        self.settings.topmost = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def _save_settings(self, quiet: bool = True) -> None:
        self._collect_settings()
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self.statusBar().showMessage(f"保存设置失败：{exc}", 8000)
            return
        if not quiet:
            self.statusBar().showMessage("设置已保存", 4000)

    def _load_settings(self) -> None:
        loaded = self.store.load()
        self.settings.api_key = loaded.api_key
        self.settings.theme = loaded.theme
        self.settings.topmost = loaded.topmost
        self.settings.active_page = loaded.active_page
        self.settings.window = dict(loaded.window)
        self.settings.button_order = list(loaded.button_order)
        self.settings.shortcuts = dict(loaded.shortcuts)
        _copy_settings(self.settings.history, loaded.history)
        for key, page in self.pages.items():
            _copy_page(page.settings, loaded.page(key))
            page.rebuild()
            page.refresh_filter()
        self.chart_page.refresh_watchlist()
        self._rebuild_toolbar()
        self._apply_shortcuts()
        self._configure_auto_timer()
        if self.settings.history.enabled and not self.recorder.stats.running:
            self.recorder.start()
        elif not self.settings.history.enabled and self.recorder.stats.running:
            self.recorder.stop()
        self._restore_settings()
        self._update_status()
        self.statusBar().showMessage("已加载保存设置", 5000)

    def _reset_defaults(self) -> None:
        defaults = AppSettings()
        defaults.api_key = self.settings.api_key
        watchlist = list(self.settings.history.watchlist)
        _copy_settings(self.settings.history, HistorySettings(watchlist=watchlist))
        self.settings.button_order = list(defaults.button_order)
        self.settings.shortcuts = dict(defaults.shortcuts)
        self.settings.topmost = False
        self.settings.active_page = "bazaar"
        self.settings.window = {"w": 1520, "h": 880, "x": None, "y": None, "maximized": False}
        self.settings.dialogs = {}
        for key, page in self.pages.items():
            _copy_page(page.settings, defaults.page(key))
            page.rebuild()
            page.refresh_filter()
        self.chart_page.refresh_watchlist()
        self._rebuild_toolbar()
        self._apply_shortcuts()
        self._configure_auto_timer()
        if self.settings.history.enabled and not self.recorder.stats.running:
            self.recorder.start()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.resize(1520, 880)
        self.tabs.setCurrentIndex(0)
        self.show()
        self._update_status()
        self._save_settings()
        self.statusBar().showMessage("已恢复默认设置", 5000)

    def _open_shortcuts(self) -> None:
        dialog = ShortcutDialog(self.settings.shortcuts, self.settings.dialogs, self)
        if dialog.exec():
            self.settings.shortcuts = dialog.result_bindings()
            self._apply_shortcuts()
            self._schedule_save()
            self.statusBar().showMessage("快捷键已更新", 5000)

    def _open_api_key(self) -> None:
        dialog = ApiKeyDialog(self.settings.api_key, self)
        if dialog.exec():
            self.settings.api_key = dialog.value()
            self._save_settings()
            self.statusBar().showMessage("API Key 已保存" if dialog.value() else "API Key 已清空", 5000)

    # ------------------------------------------------------------ 快捷键
    def _apply_shortcuts(self) -> None:
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts.clear()
        self._combo_bindings.clear()
        self._single_bindings.clear()

        global_bindings: dict[str, str] = {}
        for action, binding in self.settings.shortcuts.items():
            sequence = str(binding.sequence or "").strip().upper()
            if not sequence:
                continue
            callback = self._action_callback(action)
            if callback is None and action not in TAB_ACTIONS:
                continue
            if binding.global_hotkey and self.hotkeys.available and is_standard_sequence(sequence):
                global_bindings[action] = sequence
                continue
            if is_standard_sequence(sequence):
                shortcut = _make_shortcut(self, sequence)
                if shortcut is None:
                    continue
                shortcut.activated.connect(lambda a=action, s=sequence: self._trigger_shortcut(a, s))
                self._shortcuts.append(shortcut)
                continue
            parts = [part.strip().upper() for part in sequence.split("+") if part.strip()]
            if len(parts) >= 2:
                self._combo_bindings[action] = (set(parts[:-1]), parts[-1], action)
            elif len(parts) == 1:
                # 单键快捷键由 eventFilter 处理，避免 QShortcut 在输入框里抢走字符
                self._single_bindings[parts[0]] = action
        self.hotkeys.apply(global_bindings)
        app = QApplication.instance()
        if app is not None and not self._filter_installed:
            app.installEventFilter(self)
            self._filter_installed = True

    def _on_hotkey_status(self, status) -> None:
        if status.message and status.message != "没有设置全局热键":
            self.statusBar().showMessage(status.message, 6000)
        if self.log and not status.available:
            self.log.info("全局热键不可用：%s", status.message)

    def eventFilter(self, obj, event):  # noqa: N802
        if not self._combo_bindings and not self._single_bindings:
            return False
        kind = event.type()
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if event.isAutoRepeat():
            return False
        if kind == QEvent.Type.KeyPress:
            if event.key() in MODIFIER_KEYS:
                return False
            if isinstance(QApplication.focusWidget(), TEXT_INPUTS):
                return False
            # 带 Ctrl/Alt/Meta 的按键交给标准快捷键，避免单键绑定抢走组合键
            if event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            ):
                return False
            name = QKeySequence(event.key()).toString().upper()
            if not name:
                return False
            self._held.add(name)
            action = self._single_bindings.get(name)
            if action:
                self._dispatch(action)
                return False
            for prefix, final, action in self._combo_bindings.values():
                if name == final and prefix.issubset(self._held):
                    self._dispatch(action)
                    break
        else:
            name = QKeySequence(event.key()).toString().upper()
            self._held.discard(name)
        return False

    # ------------------------------------------------------------ 关闭
    def closeEvent(self, event) -> None:  # noqa: N802
        self._tick_timer.stop()
        self.auto_timer.stop()
        self.ah_timer.stop()
        self._save_settings()
        try:
            self.recorder.stop()
        except Exception as exc:
            if self.log:
                self.log.warning("停止录制失败：%s", exc)
        self.hotkeys.stop()
        self.refresh_service.shutdown()
        super().closeEvent(event)


# ---------------------------------------------------------------- 辅助
def _make_shortcut(parent: QWidget, sequence: str):
    parts = [part.strip().upper() for part in sequence.split("+") if part.strip()]
    if len(parts) < 2:
        return None
    key = KEY_NAMES.get(parts[-1], parts[-1])
    mods = [MOD_NAMES.get(part, part) for part in parts[:-1]]
    text = "+".join([*mods, key])
    shortcut = QShortcut(QKeySequence(text), parent)
    shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    return shortcut


def _copy_page(target: PageSettings, source: PageSettings) -> None:
    target.columns = copy.deepcopy(source.columns)
    target.column_order = list(source.column_order)
    target.sort_key = source.sort_key
    target.sort_reverse = source.sort_reverse
    target.sources = dict(source.sources)


def _copy_settings(target: HistorySettings, source: HistorySettings) -> None:
    target.enabled = source.enabled
    target.auto_refresh = source.auto_refresh
    target.interval_sec = source.interval_sec
    target.retention_days = source.retention_days
    target.watchlist = list(source.watchlist)
