"""页面基类：表格、搜索、筛选、列顺序与宽度持久化。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...config import PageSettings
from ...data.library import RecipeLibrary
from ...data.market import MarketSnapshot
from ..format import parse_bound
from ..table import ColumnSpec, MarketProxy, MarketTableModel
from ..theme import MUTED
from .specs import PageSpec

DEFAULT_ROW_HEIGHT = 26


class DataTableView(QTableView):
    copyRequested = Signal(dict)
    chartRequested = Signal(dict)
    watchRequested = Signal(dict)
    moveColumnRequested = Signal(str, int)
    hideColumnRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(DEFAULT_ROW_HEIGHT)
        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._header_menu)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._row_menu)
        self.doubleClicked.connect(self._on_double_click)

    # ------------------------------------------------------------ 行/列定位
    def _source_model(self) -> MarketTableModel | None:
        model = self.model()
        source = model.sourceModel() if isinstance(model, MarketProxy) else model
        return source if isinstance(source, MarketTableModel) else None

    def _row_dict(self, index: QModelIndex) -> dict | None:
        model = self.model()
        if isinstance(model, MarketProxy):
            return model.row_dict(index)
        source = self._source_model()
        if source and index.isValid() and index.row() < len(source.rows()):
            return source.rows()[index.row()]
        return None

    def _cid_at(self, logical: int) -> str:
        source = self._source_model()
        if not source or logical < 0:
            return ""
        columns = source.columns()
        return columns[logical].cid if logical < len(columns) else ""

    # ------------------------------------------------------------ 右键菜单
    def _header_menu(self, pos) -> None:
        logical = self.horizontalHeader().logicalIndexAt(pos)
        cid = self._cid_at(logical)
        if not cid:
            return
        menu = QMenu(self)
        left = menu.addAction("← 左移此列")
        right = menu.addAction("→ 右移此列")
        menu.addSeparator()
        hide = menu.addAction("隐藏此列")
        chosen = menu.exec(self.horizontalHeader().viewport().mapToGlobal(pos))
        if chosen is left:
            self.moveColumnRequested.emit(cid, -1)
        elif chosen is right:
            self.moveColumnRequested.emit(cid, 1)
        elif chosen is hide:
            self.hideColumnRequested.emit(cid)

    def _row_menu(self, pos) -> None:
        index = self.indexAt(pos)
        row = self._row_dict(index)
        if not row:
            return
        self.selectRow(index.row())
        name = str(row.get("name", ""))
        menu = QMenu(self)
        copy = menu.addAction("复制物品 ID")
        chart = menu.addAction("查看 K 线")
        watch = menu.addAction("加入/移出自选")
        menu.addSeparator()
        hint = menu.addAction(name)
        hint.setEnabled(False)
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is copy:
            QGuiApplication.clipboard().setText(name)
            self.copyRequested.emit(row)
        elif chosen is chart:
            self.chartRequested.emit(row)
        elif chosen is watch:
            self.watchRequested.emit(row)

    def _on_double_click(self, index: QModelIndex) -> None:
        row = self._row_dict(index)
        if row:
            self.chartRequested.emit(row)


class PageWidget(QWidget):
    chartRequested = Signal(str)
    watchlistToggleRequested = Signal(str)
    settingsChanged = Signal()

    def __init__(
        self,
        spec: PageSpec,
        library: RecipeLibrary,
        settings: PageSettings,
        dialogs: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.spec = spec
        self.library = library
        self.settings = settings
        self.dialogs = dialogs if dialogs is not None else {}
        self._snapshot: MarketSnapshot | None = None
        self._restoring = True

        self.model = MarketTableModel()
        self.proxy = MarketProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view = DataTableView()
        self.view.setModel(self.proxy)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("查找物品 ID（Enter 下一个，Esc 关闭）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setVisible(False)
        self.search_edit.textChanged.connect(self._on_search_text)
        self.search_edit.returnPressed.connect(lambda: self._search(1))
        self.search_edit.installEventFilter(self)

        self.footer = QLabel("")
        self.footer.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        self.search_hint = QLabel("")
        self.search_hint.setStyleSheet(f"color:{MUTED}; font-size:11px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.view, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.footer, 1)
        bottom.addWidget(self.search_hint)
        layout.addLayout(bottom)

        self.view.chartRequested.connect(lambda row: self.chartRequested.emit(str(row.get("name", ""))))
        self.view.watchRequested.connect(lambda row: self.watchlistToggleRequested.emit(str(row.get("name", ""))))
        self.view.moveColumnRequested.connect(self.move_column)
        self.view.hideColumnRequested.connect(self.hide_column)
        self.view.horizontalHeader().sectionResized.connect(self._on_section_resized)
        self.view.horizontalHeader().sectionMoved.connect(self._on_section_moved)
        self.view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.view.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_changed)

        self._width_timer = QTimer(self)
        self._width_timer.setSingleShot(True)
        self._width_timer.setInterval(400)
        self._width_timer.timeout.connect(self.settingsChanged.emit)

        self._rebuild_columns()
        self._restoring = False
        self._update_footer()

    # ------------------------------------------------------------ 列
    def _ordered_specs(self, include_hidden: bool = False) -> list[ColumnSpec]:
        by_cid = {spec.cid: spec for spec in self.spec.columns}
        order = list(dict.fromkeys(cid for cid in self.settings.column_order if cid in by_cid))
        order += [spec.cid for spec in self.spec.columns if spec.cid not in order]
        result = []
        for cid in order:
            spec = by_cid[cid]
            column = self.settings.column(cid, spec.width)
            if include_hidden or column.visible:
                result.append(spec)
        return result

    def _rebuild_columns(self) -> None:
        if not self.settings.column_order:
            self.settings.column_order = [spec.cid for spec in self.spec.columns]
        specs = self._ordered_specs()
        if not specs:
            # 至少保留第一列，避免界面空白
            specs = self.spec.columns[:1]
        self.model.set_columns(specs)
        self.model.set_units({spec.cid: self.settings.column(spec.cid).unit for spec in specs})
        self._apply_widths()
        self._apply_sort()
        self.refresh_filter()

    def _apply_widths(self) -> None:
        header = self.view.horizontalHeader()
        for index, spec in enumerate(self.model.columns()):
            width = self.settings.column(spec.cid, spec.width).width
            header.resizeSection(index, max(50, int(width)))
        header.setMinimumSectionSize(50)

    def move_column(self, cid: str, delta: int) -> None:
        order = list(self.settings.column_order) or [spec.cid for spec in self.spec.columns]
        if cid not in order:
            order = [spec.cid for spec in self.spec.columns]
        index = order.index(cid)
        target = index + delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.settings.column_order = order
            self._rebuild_columns()
            self.settingsChanged.emit()

    def hide_column(self, cid: str) -> None:
        self.settings.column(cid).visible = False
        self._rebuild_columns()
        self.settingsChanged.emit()

    def _on_section_resized(self, logical: int, _old: int, new: int) -> None:
        if self._restoring:
            return
        specs = self.model.columns()
        if 0 <= logical < len(specs):
            self.settings.column(specs[logical].cid, specs[logical].width).width = int(new)
            self._width_timer.start()

    def _on_section_moved(self, _logical: int, _old_visual: int, _new_visual: int) -> None:
        if self._restoring:
            return
        header = self.view.horizontalHeader()
        visible = [self.model.columns()[header.logicalIndex(i)].cid for i in range(header.count())]
        hidden = [cid for cid in self.settings.column_order if cid not in visible]
        hidden += [spec.cid for spec in self.spec.columns if spec.cid not in visible and spec.cid not in hidden]
        self.settings.column_order = visible + hidden
        self.settingsChanged.emit()

    def _on_header_clicked(self, logical: int) -> None:
        header = self.view.horizontalHeader()
        if logical == header.sortIndicatorSection():
            order = (
                Qt.SortOrder.DescendingOrder
                if header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.DescendingOrder
        header.setSortIndicator(logical, order)

    def _on_sort_changed(self, logical: int, order: Qt.SortOrder) -> None:
        specs = self.model.columns()
        if not (0 <= logical < len(specs)):
            return
        self.proxy.sort(logical, order)
        if self._restoring:
            return
        self.settings.sort_key = specs[logical].cid
        self.settings.sort_reverse = order == Qt.SortOrder.DescendingOrder
        self.settingsChanged.emit()
        self._update_footer()

    def _apply_sort(self) -> None:
        if not self.model.columns():
            return
        header = self.view.horizontalHeader()
        if not self.settings.sort_key:
            self.settings.sort_key, self.settings.sort_reverse = self.spec.default_sort
        cid = self.settings.sort_key
        index = self.model.column_index(cid)
        if index < 0:
            index = 0
            cid = self.model.columns()[0].cid
        order = Qt.SortOrder.DescendingOrder if self.settings.sort_reverse else Qt.SortOrder.AscendingOrder
        header.blockSignals(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(index, order)
        header.blockSignals(False)
        self.proxy.sort(index, order)

    # ------------------------------------------------------------ 数据
    def apply_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._snapshot = snapshot
        try:
            rows = self.spec.build(snapshot, self.library)
        except Exception:
            rows = []
            raise
        scroll = self.view.verticalScrollBar().value()
        self.model.set_rows(rows)
        self.proxy.set_predicate(self._predicate)
        self._update_footer()
        QTimer.singleShot(0, lambda: self.view.verticalScrollBar().setValue(scroll))

    def rows(self) -> list[dict]:
        return self.model.rows()

    def rebuild(self) -> None:
        """列显隐 / 顺序 / 单位变化后重建表格列。"""
        self._rebuild_columns()

    def _predicate(self, row: dict) -> bool:
        if not self._source_allowed(row):
            return False
        for spec in self.model.columns():
            if not spec.numeric:
                continue
            source = "auction" if spec.cid == "item_ah" else "bazaar"
            if not self.settings.sources.get(source, True):
                continue
            column = self.settings.column(spec.cid, spec.width)
            low, low_ok = parse_bound(column.minimum, column.unit)
            high, high_ok = parse_bound(column.maximum, column.unit)
            if not low_ok or not high_ok:
                continue
            if low is None and high is None:
                continue
            value = row.get(spec.cid)
            if value is None:
                return False
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if low is not None and number < low:
                return False
            if high is not None and number > high:
                return False
        return True

    def _source_allowed(self, row: dict) -> bool:
        use_bazaar = self.settings.sources.get("bazaar", True)
        if not self.spec.sources_enabled:
            return use_bazaar
        use_auction = self.settings.sources.get("auction", True)
        has_ah = row.get("item_ah") is not None
        if use_bazaar and use_auction:
            return True
        if use_bazaar:
            return not has_ah
        if use_auction:
            return has_ah
        return False

    def refresh_filter(self) -> None:
        self.proxy.set_predicate(self._predicate)
        self._update_footer()

    def _update_footer(self) -> None:
        total = len(self.model.rows())
        shown = self.proxy.rowCount()
        if not self._snapshot:
            self.footer.setText("等待行情数据…")
            return
        self.footer.setText(f"共 {total:,} 行 · 显示 {shown:,} 行 · 双击行查看 K 线")

    # ------------------------------------------------------------ 搜索
    def show_search(self) -> None:
        self.search_edit.setVisible(True)
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def hide_search(self) -> None:
        self.search_edit.setVisible(False)
        self.proxy.set_search("")
        self.search_hint.setText("")

    def eventFilter(self, obj, event):  # noqa: N802
        if (
            obj is self.search_edit
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            self.hide_search()
            return True
        return super().eventFilter(obj, event)

    def _on_search_text(self, text: str) -> None:
        self.proxy.set_search(text)
        self._update_footer()
        if text.strip():
            self._search(1, from_start=True)

    def _search(self, direction: int, from_start: bool = False) -> None:
        term = self.search_edit.text().strip().upper().replace(" ", "_")
        if not term:
            return
        total = self.proxy.rowCount()
        if total == 0:
            self.search_hint.setText("没有可匹配的行")
            return
        current = -1
        rows = self.view.selectionModel().selectedRows()
        if rows:
            current = rows[0].row()
        if from_start or current < 0:
            start = 0 if direction > 0 else total - 1
        else:
            start = current + direction
        for step in range(total):
            row = (start + step * direction) % total
            source = self.proxy.mapToSource(self.proxy.index(row, 0))
            data = self.model.rows()
            if 0 <= source.row() < len(data):
                name = str(data[source.row()].get("name", "")).upper()
                if term in name:
                    self.view.selectRow(row)
                    self.view.scrollTo(self.proxy.index(row, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
                    self.search_hint.setText(f"已找到：{data[source.row()].get('name')}")
                    return
        self.search_hint.setText("找不到匹配项")

    # ------------------------------------------------------------ 参数面板
    def open_param_panel(self, parent=None) -> None:
        from ..widgets.param_panel import ParamPanelDialog

        dialog = ParamPanelDialog(self, parent or self.window())
        dialog.exec()
