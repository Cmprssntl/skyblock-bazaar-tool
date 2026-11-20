"""参数设置面板：列显隐、数值范围、单位、列顺序、数据源。"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..format import UNIT_CHOICES, validate_bound
from ..geometry import apply_geometry, geometry_dict
from ..theme import MUTED


class ParamPanelDialog(QDialog):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.settings = page.settings
        self.geometry_store = page.dialogs
        self.setWindowTitle(f"{page.spec.title} 参数设置")
        self.setMinimumSize(900, 600)
        self._snapshot = copy.deepcopy(self.settings)
        self._rows: dict[str, dict] = {}
        self._stretch_row = 0

        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(180)
        self._apply_timer.timeout.connect(self._apply_filters)

        self._build()
        self._load_geometry()

    # ------------------------------------------------------------ 界面
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "勾选显示列；数值列可填最低/最高值，支持 10k / 2.5m / 1b；"
            "右键字段名可上移/下移。修改实时生效。"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.grid = QGridLayout(body)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(1, 0)
        self.grid.setColumnStretch(5, 1)
        self.grid.setColumnMinimumWidth(1, 240)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        headers = ("显示", "字段", "最低值", "最高值", "单位")
        for column, text in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            self.grid.addWidget(label, 0, column)

        order = list(dict.fromkeys(cid for cid in self.settings.column_order if any(s.cid == cid for s in self.page.spec.columns)))
        order += [spec.cid for spec in self.page.spec.columns if spec.cid not in order]
        self.settings.column_order = order

        for cid in order:
            self._add_row(cid)

        self.source_frame = QFrame()
        source_layout = QHBoxLayout(self.source_frame)
        source_layout.setContentsMargins(0, 4, 0, 0)
        source_layout.addWidget(QLabel("筛选数据源："))
        self.source_boxes = {}
        for key, caption in (("bazaar", "Bazaar"), ("auction", "Auction House")):
            box = QCheckBox(caption)
            box.setChecked(bool(self.settings.sources.get(key, True)))
            box.toggled.connect(self._on_source_toggled)
            source_layout.addWidget(box)
            self.source_boxes[key] = box
        source_layout.addStretch(1)
        self.source_frame.setVisible(self.page.spec.sources_enabled)
        layout.addWidget(self.source_frame)

        buttons = QHBoxLayout()
        reset = QPushButton("恢复默认")
        apply_close = QPushButton("应用并关闭")
        apply_close.setProperty("accent", True)
        cancel = QPushButton("仅关闭（放弃修改）")
        reset.clicked.connect(self._reset_defaults)
        apply_close.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(apply_close)
        layout.addLayout(buttons)

    def _add_row(self, cid: str) -> None:
        spec = next(item for item in self.page.spec.columns if item.cid == cid)
        column = self.settings.column(cid, spec.width)

        check = QCheckBox()
        check.setChecked(column.visible)
        check.setToolTip("在表格中显示该列")

        field = QLabel(spec.title)
        field.setToolTip(spec.tooltip or spec.title)
        field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        field.customContextMenuRequested.connect(lambda pos, c=cid: self._field_menu(c, pos, field))

        minimum = QLineEdit(column.minimum)
        minimum.setPlaceholderText("最低")
        minimum.setMaximumWidth(140)
        maximum = QLineEdit(column.maximum)
        maximum.setPlaceholderText("最高")
        maximum.setMaximumWidth(140)
        unit = QComboBox()
        unit.addItems(UNIT_CHOICES)
        unit.setCurrentText(column.unit)
        unit.setMaximumWidth(90)

        if not spec.numeric:
            minimum.setEnabled(False)
            maximum.setEnabled(False)
            unit.setEnabled(False)
            minimum.setPlaceholderText("不支持筛选")
            maximum.setPlaceholderText("不支持筛选")

        check.toggled.connect(lambda checked, c=cid: self._on_visible(c, checked))
        minimum.textChanged.connect(lambda text, c=cid: self._on_bound(c, "minimum", text))
        maximum.textChanged.connect(lambda text, c=cid: self._on_bound(c, "maximum", text))
        unit.currentTextChanged.connect(lambda text, c=cid: self._on_unit(c, text))

        self._rows[cid] = {
            "spec": spec,
            "check": check,
            "field": field,
            "minimum": minimum,
            "maximum": maximum,
            "unit": unit,
            "numeric": spec.numeric,
        }
        self._regrid()

    def _regrid(self) -> None:
        if self._stretch_row:
            self.grid.setRowStretch(self._stretch_row, 0)
        for index, cid in enumerate(self.settings.column_order):
            widgets = self._rows.get(cid)
            if not widgets:
                continue
            row = index + 1
            self.grid.addWidget(widgets["check"], row, 0, alignment=Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(widgets["field"], row, 1)
            self.grid.addWidget(widgets["minimum"], row, 2)
            self.grid.addWidget(widgets["maximum"], row, 3)
            self.grid.addWidget(widgets["unit"], row, 4)
        # 把多余高度留给最后一行，避免所有行被均匀拉高
        self._stretch_row = len(self.settings.column_order) + 1
        self.grid.setRowStretch(self._stretch_row, 1)
        self.grid.setColumnStretch(5, 1)

    # ------------------------------------------------------------ 交互
    def _field_menu(self, cid: str, pos, widget: QWidget) -> None:
        menu = QMenu(self)
        up = menu.addAction("↑ 上移")
        down = menu.addAction("↓ 下移")
        order = self.settings.column_order
        index = order.index(cid) if cid in order else -1
        up.setEnabled(index > 0)
        down.setEnabled(0 <= index < len(order) - 1)
        chosen = menu.exec(widget.mapToGlobal(pos))
        if chosen is up and index > 0:
            order[index - 1], order[index] = order[index], order[index - 1]
            self._regrid()
            self._refresh_columns()
        elif chosen is down and 0 <= index < len(order) - 1:
            order[index + 1], order[index] = order[index], order[index + 1]
            self._regrid()
            self._refresh_columns()

    def _on_visible(self, cid: str, checked: bool) -> None:
        self.settings.column(cid).visible = bool(checked)
        self._refresh_columns()

    def _on_bound(self, cid: str, key: str, text: str) -> None:
        column = self.settings.column(cid)
        setattr(column, key, text)
        widget = self._rows[cid][key]
        error = validate_bound(text, column.unit)
        widget.setToolTip(error or "")
        widget.setProperty("invalid", error is not None)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        self._apply_timer.start()

    def _on_unit(self, cid: str, text: str) -> None:
        self.settings.column(cid).unit = text
        self._on_bound(cid, "minimum", self._rows[cid]["minimum"].text())
        self.page.rebuild()
        self._apply_timer.start()

    def _on_source_toggled(self, _checked: bool) -> None:
        for key, box in self.source_boxes.items():
            self.settings.sources[key] = box.isChecked()
        self._apply_timer.start()

    def _refresh_columns(self) -> None:
        self.page.rebuild()
        self._apply_timer.start()

    def _apply_filters(self) -> None:
        self.page.refresh_filter()

    # ------------------------------------------------------------ 恢复默认
    def _reset_defaults(self) -> None:
        for spec in self.page.spec.columns:
            column = self.settings.column(spec.cid, spec.width)
            column.visible = True
            column.minimum = ""
            column.maximum = ""
            column.unit = "默认"
            column.width = spec.width
            widgets = self._rows.get(spec.cid)
            if widgets:
                widgets["check"].setChecked(True)
                widgets["minimum"].setText("")
                widgets["maximum"].setText("")
                widgets["unit"].setCurrentText("默认")
        self.settings.column_order = [spec.cid for spec in self.page.spec.columns]
        for box in self.source_boxes.values():
            box.setChecked(True)
        for key in self.settings.sources:
            self.settings.sources[key] = True
        self._regrid()
        self.page.rebuild()
        self.page.refresh_filter()

    # ------------------------------------------------------------ 几何
    def _load_geometry(self) -> None:
        if not apply_geometry(self, self.geometry_store.get("param")):
            self.resize(980, 720)

    def _save_geometry(self) -> None:
        self.geometry_store["param"] = geometry_dict(self)

    def accept(self) -> None:
        self._save_geometry()
        self.page.refresh_filter()
        self.page.settingsChanged.emit()
        super().accept()

    def reject(self) -> None:
        self._save_geometry()
        # 放弃本次修改：恢复打开面板前的快照
        self.settings.columns = copy.deepcopy(self._snapshot.columns)
        self.settings.column_order = list(self._snapshot.column_order)
        self.settings.sources = dict(self._snapshot.sources)
        self.page.rebuild()
        self.page.refresh_filter()
        super().reject()
