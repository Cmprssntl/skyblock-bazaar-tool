"""API Key 输入窗口。"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class ApiKeyDialog(QDialog):
    def __init__(self, current: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hypixel API Key")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        label = QLabel("输入 Hypixel API Key（可选；Bazaar 公共接口通常不需要）：")
        layout.addWidget(label)
        self.edit = QLineEdit(current)
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("粘贴 API Key")
        layout.addWidget(self.edit)

        show = QCheckBox("显示明文")
        show.toggled.connect(
            lambda checked: self.edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show)

        warning = QLabel("⚠ 请勿泄露自己的 API Key。密钥保存在本地 settings.json（权限 600）。")
        warning.setStyleSheet("color:#ffb3bc;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        clear = QPushButton("清除")
        okay = QPushButton("保存")
        okay.setProperty("accent", True)
        cancel = QPushButton("取消")
        clear.clicked.connect(self._clear)
        okay.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(okay)
        layout.addLayout(buttons)

    def _clear(self) -> None:
        self.edit.clear()

    def value(self) -> str:
        return self.edit.text().strip()
