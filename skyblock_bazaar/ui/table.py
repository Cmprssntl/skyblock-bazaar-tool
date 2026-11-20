"""表格：列定义、数据模型、数值排序 / 过滤代理。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from .format import format_value
from .theme import DOWN, FLAT, MUTED, UP, mono_font

NUMERIC_KINDS = {"price", "count", "percent"}


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    cid: str
    title: str
    kind: str = "count"
    width: int = 115
    tooltip: str = ""
    profit: bool = False

    @property
    def numeric(self) -> bool:
        return self.kind in NUMERIC_KINDS

    @property
    def unit_enabled(self) -> bool:
        return self.kind in NUMERIC_KINDS


class MarketTableModel(QAbstractTableModel):
    def __init__(self, columns: list[ColumnSpec] | None = None, parent=None):
        super().__init__(parent)
        self._columns: list[ColumnSpec] = columns or []
        self._rows: list[dict] = []
        self.units: dict[str, str] = {}
        self._mono = mono_font(9)
        self._muted = QColor(MUTED)

    # ------------------------------------------------------------ Qt 接口
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        spec = self._columns[index.column()]
        value = row.get(spec.cid)
        if role == Qt.ItemDataRole.DisplayRole:
            return format_value(value, self.units.get(spec.cid, "默认"), spec.kind)
        if role == Qt.ItemDataRole.UserRole:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if spec.numeric:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole:
            if value is None:
                return self._muted
            if spec.profit:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    return FLAT
                if number > 0:
                    return UP
                if number < 0:
                    return DOWN
            return None
        if role == Qt.ItemDataRole.FontRole and spec.numeric:
            return self._mono
        if role == Qt.ItemDataRole.ToolTipRole:
            if spec.tooltip:
                return spec.tooltip
            if spec.kind == "text" and value not in (None, ""):
                return str(value)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        if section >= len(self._columns):
            return None
        spec = self._columns[section]
        unit = self.units.get(spec.cid, "默认")
        if spec.unit_enabled and unit != "默认":
            return f"{spec.title}({unit})"
        return spec.title

    # ------------------------------------------------------------ 数据
    def rows(self) -> list[dict]:
        return self._rows

    def columns(self) -> list[ColumnSpec]:
        return self._columns

    def column_index(self, cid: str) -> int:
        for index, spec in enumerate(self._columns):
            if spec.cid == cid:
                return index
        return -1

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def set_columns(self, columns: list[ColumnSpec]) -> None:
        self.beginResetModel()
        self._columns = columns
        self.endResetModel()

    def set_units(self, units: dict[str, str]) -> None:
        self.units = units
        if self._columns:
            top = self.index(0, 0)
            bottom = self.index(max(0, len(self._rows) - 1), len(self._columns) - 1)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole])
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(self._columns) - 1)


class MarketProxy(QSortFilterProxyModel):
    """过滤 + 排序：None 永远排最后，数值列按原始值比较。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDynamicSortFilter(True)
        self.setSortRole(Qt.ItemDataRole.UserRole)
        self._predicate: Callable[[dict], bool] | None = None
        self._search = ""
        self._descending = True

    # ------------------------------------------------------------ 过滤
    def _invalidate_filter(self) -> None:
        self.invalidate()

    def set_predicate(self, predicate: Callable[[dict], bool] | None) -> None:
        self._predicate = predicate
        self._invalidate_filter()

    def set_search(self, text: str) -> None:
        self._search = str(text or "").strip().upper().replace(" ", "_")
        self._invalidate_filter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if not isinstance(model, MarketTableModel):
            return True
        if source_row >= len(model.rows()):
            return False
        row = model.rows()[source_row]
        if self._predicate is not None and not self._predicate(row):
            return False
        if self._search:
            name = str(row.get("name", "")).upper()
            if self._search not in name:
                return False
        return True

    # ------------------------------------------------------------ 排序
    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:  # noqa: N802
        self._descending = order == Qt.SortOrder.DescendingOrder
        # 始终按升序交给 Qt，由 lessThan 自行处理方向，保证 None 永远在最后；
        # invalidate() 强制在方向变化时重新排序（Qt 对相同的 sort 参数会直接返回）。
        super().sort(column, Qt.SortOrder.AscendingOrder)
        self.invalidate()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        a = left.data(Qt.ItemDataRole.UserRole)
        b = right.data(Qt.ItemDataRole.UserRole)
        if a is None and b is None:
            return False
        if a is None:
            return False
        if b is None:
            return True
        if isinstance(a, str) or isinstance(b, str):
            a, b = str(a).lower(), str(b).lower()
        try:
            return a > b if self._descending else a < b
        except TypeError:
            return str(a) > str(b) if self._descending else str(a) < str(b)

    # ------------------------------------------------------------ 工具
    def row_dict(self, proxy_index: QModelIndex) -> dict | None:
        model = self.sourceModel()
        if not isinstance(model, MarketTableModel) or not proxy_index.isValid():
            return None
        source = self.mapToSource(proxy_index)
        if 0 <= source.row() < len(model.rows()):
            return model.rows()[source.row()]
        return None
