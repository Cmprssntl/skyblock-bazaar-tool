"""快捷键字符串解析：修饰键组合与普通按键组合。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from skyblock_bazaar.services.sequences import is_standard_sequence, split_sequence
from skyblock_bazaar.ui.widgets.shortcut_dialog import KeyCaptureDialog


def _press(dialog: KeyCaptureDialog, key: Qt.Key, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, modifiers))


def test_capture_plain_combo(qapp):
    dialog = KeyCaptureDialog("test")
    _press(dialog, Qt.Key.Key_V)
    _press(dialog, Qt.Key.Key_B)
    assert dialog.sequence() == "V+B"


def test_capture_modifier_combo(qapp):
    dialog = KeyCaptureDialog("test")
    _press(dialog, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
    _press(dialog, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert dialog.sequence() == "CTRL+F"


def test_capture_single_key(qapp):
    dialog = KeyCaptureDialog("test")
    _press(dialog, Qt.Key.Key_F5)
    assert dialog.sequence() == "F5"


def test_split_standard_sequence():
    assert split_sequence("CTRL+ALT+B") == (["CTRL", "ALT"], "B")
    assert is_standard_sequence("CTRL+ALT+B") is True
    assert is_standard_sequence("CTRL+F") is True


def test_plain_combo_is_local_only():
    assert split_sequence("V+B") is None
    assert is_standard_sequence("V+B") is False


def test_single_key_and_empty():
    assert split_sequence("F5") is None
    assert split_sequence("A") is None
    assert split_sequence("") is None
    assert is_standard_sequence("") is False
