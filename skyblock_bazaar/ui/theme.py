"""深色 SkyBlock 主题：配色、字体、QSS。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

BG = "#0b0f14"
CARD = "#0f141b"
CARD_ALT = "#131a23"
LINE = "#1c2530"
TEXT = "#e6edf3"
MUTED = "#8b98a8"
ACCENT = "#e0b060"
ACCENT_DARK = "#8a6a2f"
UP = QColor("#ff5c6c")
DOWN = QColor("#2ecc71")
FLAT = QColor("#e6edf3")
GRID = "#18212c"

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QMainWindow {{ background: #080b10; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#bar {{ background: #0c1118; border-bottom: 1px solid {LINE}; }}
QLabel#brand {{ font-size: 15px; font-weight: 600; }}
QLabel#tag {{ color: {MUTED}; border: 1px solid {LINE}; border-radius: 4px; padding: 1px 7px; font-size: 11px; }}
QLabel#tag[state="ok"] {{ color: #9ae6b4; border-color: #24503a; }}
QLabel#tag[state="warn"] {{ color: #ffd479; border-color: #5d4a25; }}
QLabel#tag[state="err"] {{ color: #ffb3bc; border-color: #5d2530; }}
QLabel#title {{ font-size: 12px; font-weight: 600; color: #c6d2de; letter-spacing: .5px; }}
QLabel#hint {{ color: #6f7d8d; font-size: 11px; }}
QLabel#stat {{ font-size: 14px; font-weight: 600; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 10px; }}
QPushButton {{ background: {CARD_ALT}; border: 1px solid {LINE}; border-radius: 5px; padding: 6px 12px; }}
QPushButton:hover {{ background: #17202b; border-color: #2c3a4a; }}
QPushButton:checked {{ background: #2a2417; border-color: {ACCENT_DARK}; color: #f3d79a; }}
QPushButton:disabled {{ color: #4f5b66; border-color: #161e27; }}
QPushButton[accent="true"] {{ background: #4a3a17; border-color: {ACCENT_DARK}; color: #f3d79a; }}
QPushButton[accent="true"]:hover {{ background: #5c4819; }}
QPushButton[accent="true"]:disabled {{ background: #2a2417; color: #7a6a48; border-color: #3a3020; }}
QPushButton[danger="true"] {{ color: #ffb3bc; border-color: #5d2530; }}
QToolBar {{ background: transparent; border: none; spacing: 4px; padding: 4px 6px; }}
QToolButton {{ background: {CARD_ALT}; border: 1px solid {LINE}; border-radius: 5px; padding: 5px 10px; color: {TEXT}; }}
QToolButton:hover {{ background: #17202b; border-color: #2c3a4a; }}
QTableView {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 6px; gridline-color: transparent; selection-background-color: #21303d; selection-color: #ffffff; alternate-background-color: #0d1219; }}
QTableView::item {{ border-bottom: 1px solid #141c25; padding: 2px 6px; }}
QHeaderView::section {{ background: #0c1118; color: {MUTED}; border: none; border-right: 1px solid {LINE}; border-bottom: 1px solid {LINE}; padding: 5px 7px; font-size: 11px; }}
QHeaderView::section:hover {{ color: {TEXT}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ background: #0d1219; color: {MUTED}; border: 1px solid {LINE}; border-bottom: none; padding: 6px 18px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ color: #f3d79a; background: {CARD}; border-color: {ACCENT_DARK}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{ background: #0a0f15; border: 1px solid {LINE}; border-radius: 4px; padding: 4px 8px; selection-background-color: #2a3a48; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT_DARK}; }}
QLineEdit[invalid="true"] {{ border-color: #b34a5a; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {LINE}; selection-background-color: #21303d; }}
QCheckBox {{ color: #c6d2de; }}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #3a4653;
    border-radius: 3px;
    background: #0a0f15;
}}
QCheckBox::indicator:hover {{ border-color: #5a6b7c; }}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:disabled {{ border-color: #232c36; background: #0b1016; }}
QListWidget {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 6px; }}
QListWidget::item {{ padding: 4px 6px; }}
QListWidget::item:selected {{ background: #21303d; }}
QScrollBar:vertical {{ background: transparent; width: 9px; }}
QScrollBar::handle:vertical {{ background: #24303d; border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; }}
QScrollBar::handle:horizontal {{ background: #24303d; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QSplitter::handle {{ background: {BG}; }}
QStatusBar {{ color: #6f7d8d; font-size: 11px; }}
QMenu {{ background: {CARD}; border: 1px solid {LINE}; }}
QMenu::item {{ padding: 5px 22px; }}
QMenu::item:selected {{ background: #21303d; }}
QDialog {{ background: {BG}; }}
QGroupBox {{ border: 1px solid {LINE}; border-radius: 6px; margin-top: 10px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {MUTED}; }}
QToolTip {{ background: {CARD_ALT}; color: {TEXT}; border: 1px solid {LINE}; padding: 4px; }}
"""

FONT_CANDIDATES = (
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "WenQuanYi Micro Hei",
    "Sarasa Gothic SC",
    "DejaVu Sans",
)


def ui_font(size: int = 10) -> QFont:
    families = set(QFontDatabase.families())
    for name in FONT_CANDIDATES:
        if name in families:
            font = QFont(name)
            font.setPointSize(size)
            return font
    font = QFont()
    font.setPointSize(size)
    return font


def mono_font(size: int = 9) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    return font


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    app.setFont(ui_font(10))
