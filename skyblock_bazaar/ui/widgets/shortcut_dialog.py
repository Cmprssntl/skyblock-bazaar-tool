"""快捷键设置与按键捕获窗口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config import ShortcutBinding
from ...services.sequences import is_standard_sequence
from ..geometry import apply_geometry, geometry_dict

SHORTCUT_ACTIONS: list[tuple[str, str]] = [
    ("refresh", "刷新全部数据"),
    ("refresh_bazaar", "刷新 BZ 数据"),
    ("refresh_auction", "刷新 AH 数据"),
    ("param", "参数设置面板"),
    ("save", "保存当前设置"),
    ("load", "加载保存设置"),
    ("reset", "重置全部默认"),
    ("search", "搜索"),
    ("record", "切换录制"),
    ("topmost", "窗口置顶"),
    ("shortcut", "快捷键设置"),
    ("api", "输入 API Key"),
    ("tab_bazaar", "切换到 Bazaar"),
    ("tab_craft", "切换到 Craft"),
    ("tab_forge", "切换到 Forge"),
    ("tab_enchant", "切换到 Enchant"),
    ("tab_chart", "切换到 K 线"),
]
ACTION_LABELS = dict(SHORTCUT_ACTIONS)


class KeyCaptureDialog(QDialog):
    def __init__(self, action_label: str, current: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"设置快捷键 - {action_label}")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._held: list[str] = []
        self._captured: str | None = current or None
        self._mods: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        hint = QLabel("直接按下想要的键或组合键；也支持先按住 V 再按 B 这类普通按键组合。")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self.display = QLabel(current or "等待按键…")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(
            "font-size:20px; padding:18px; border:1px dashed #3a4653; border-radius:8px; color:#f3d79a;"
        )
        layout.addWidget(self.display)

        self.mod_label = QLabel("")
        self.mod_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mod_label.setObjectName("hint")
        layout.addWidget(self.mod_label)

        buttons = QHBoxLayout()
        clear = QPushButton("清除")
        okay = QPushButton("确定")
        okay.setProperty("accent", True)
        cancel = QPushButton("取消")
        buttons.addWidget(clear)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(okay)
        layout.addLayout(buttons)
        clear.clicked.connect(self._clear)
        okay.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.setFocus()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        key = event.key()
        if key in (Qt.Key.Key_Escape,):
            self.reject()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._captured:
            self.accept()
            return
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            self._update_mods(event.modifiers())
            return
        name = QKeySequence(key).toString().upper()
        if not name:
            return
        # 修饰键的按下事件在部分平台不带 modifiers，这里以实际按键事件的修饰状态为准
        self._update_mods(event.modifiers())
        if name not in self._held:
            self._held.append(name)
        mods = self._mods
        if mods:
            sequence = "+".join([*mods, name])
        elif len(self._held) >= 2:
            sequence = "+".join(self._held)
        else:
            sequence = name
        self._captured = sequence
        self.display.setText(sequence)
        if not mods and len(self._held) >= 2:
            self.mod_label.setText("普通按键组合：按住前面的键，再按最后一个键")
        else:
            self.mod_label.setText("")

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        name = QKeySequence(event.key()).toString().upper()
        if name in self._held:
            self._held.remove(name)
        self._update_mods(event.modifiers())

    def _update_mods(self, modifiers) -> None:
        mods = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mods.append("CTRL")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mods.append("ALT")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mods.append("SHIFT")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            mods.append("META")
        self._mods = mods

    def _clear(self) -> None:
        self._captured = None
        self._held.clear()
        self.display.setText("等待按键…")
        self.mod_label.setText("")

    def sequence(self) -> str:
        return self._captured or ""


class ShortcutDialog(QDialog):
    def __init__(self, bindings: dict[str, ShortcutBinding], geometry_store: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("快捷键设置")
        self.setMinimumSize(620, 560)
        self.bindings = {action: ShortcutBinding(**vars(item)) for action, item in bindings.items()}
        self.geometry_store = geometry_store
        self._rows: dict[str, tuple[QTableWidgetItem, QCheckBox]] = {}
        self._build()
        if not apply_geometry(self, geometry_store.get("shortcut")):
            self.resize(660, 620)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        hint = QLabel('点击"设置"捕获快捷键。勾选"全局"后，窗口失去焦点仍然生效（Wayland 不支持全局热键）。')
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(len(SHORTCUT_ACTIONS), 4)
        self.table.setHorizontalHeaderLabels(["按钮", "快捷键", "全局", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 70)

        for row, (action, label) in enumerate(SHORTCUT_ACTIONS):
            binding = self.bindings.setdefault(action, ShortcutBinding())
            name_item = QTableWidgetItem(label)
            seq_item = QTableWidgetItem(binding.sequence or "—")
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setChecked(binding.global_hotkey)
            if not is_standard_sequence(binding.sequence):
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
                checkbox.setToolTip("普通按键组合只支持应用内")
            button = QPushButton("设置")
            button.setFixedWidth(70)
            button.clicked.connect(lambda _=False, a=action, s=seq_item, c=checkbox: self._capture(a, s, c))
            self._rows[action] = (seq_item, checkbox)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, seq_item)
            self.table.setCellWidget(row, 2, self._center(checkbox))
            self.table.setCellWidget(row, 3, self._center(button))

        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        reset = QPushButton("重置全部")
        okay = QPushButton("确定")
        okay.setProperty("accent", True)
        cancel = QPushButton("取消")
        reset.clicked.connect(self._reset)
        okay.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(okay)
        layout.addLayout(buttons)

    @staticmethod
    def _center(widget: QWidget) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(widget)
        return box

    def _capture(self, action: str, seq_item: QTableWidgetItem, checkbox: QCheckBox) -> None:
        binding = self.bindings[action]
        dialog = KeyCaptureDialog(ACTION_LABELS.get(action, action), binding.sequence, self)
        if not dialog.exec():
            return
        binding.sequence = dialog.sequence()
        seq_item.setText(binding.sequence or "—")
        standard = is_standard_sequence(binding.sequence) and binding.sequence
        checkbox.setEnabled(bool(standard))
        if not standard:
            checkbox.setChecked(False)

    def _reset(self) -> None:
        for action, (seq_item, checkbox) in self._rows.items():
            binding = self.bindings[action]
            binding.sequence = ""
            binding.global_hotkey = False
            seq_item.setText("—")
            checkbox.setChecked(False)
            checkbox.setEnabled(True)
        # 搜索保留 Ctrl+F 默认值
        binding = self.bindings.setdefault("search", ShortcutBinding())
        binding.sequence = "CTRL+F"
        seq_item, checkbox = self._rows["search"]
        seq_item.setText("CTRL+F")

    def result_bindings(self) -> dict[str, ShortcutBinding]:
        for action, (_seq, checkbox) in self._rows.items():
            binding = self.bindings.setdefault(action, ShortcutBinding())
            binding.global_hotkey = checkbox.isChecked() and is_standard_sequence(binding.sequence)
        return self.bindings

    def accept(self) -> None:
        self.geometry_store["shortcut"] = geometry_dict(self)
        super().accept()

    def reject(self) -> None:
        self.geometry_store["shortcut"] = geometry_dict(self)
        super().reject()
