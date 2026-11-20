"""全局快捷键：Windows（RegisterHotKey）/ X11（XGrabKey）/ 不可用时降级。

局部快捷键由 UI 层用 QShortcut 处理；这里只负责窗口失去焦点后仍然生效的热键。
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .sequences import split_sequence

SPECIAL_KEYS = {
    "SPACE": "space",
    "ESCAPE": "Escape",
    "RETURN": "Return",
    "ENTER": "Return",
    "TAB": "Tab",
    "BACKSPACE": "BackSpace",
    "INSERT": "Insert",
    "DELETE": "Delete",
    "HOME": "Home",
    "END": "End",
    "PAGE_UP": "Prior",
    "PAGE_DOWN": "Next",
    "LEFT": "Left",
    "RIGHT": "Right",
    "UP": "Up",
    "DOWN": "Down",
}


def is_standard(sequence: str) -> bool:
    return split_sequence(sequence) is not None


class HotkeyBackend:
    name = "none"
    available = False
    reason = ""

    def start(self, bindings: dict[str, str]) -> bool:  # items: action -> sequence
        return False

    def stop(self) -> None:
        pass


class NoopBackend(HotkeyBackend):
    def __init__(self, reason: str):
        self.reason = reason
        self.name = "noop"


class Win32Backend(HotkeyBackend):
    name = "win32"
    available = True
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY = 0x0312

    def __init__(self, on_trigger):
        self.on_trigger = on_trigger
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self.registered = 0
        self.error = ""

    @staticmethod
    def _vk(key: str) -> int | None:
        if len(key) == 1 and key.isalnum():
            return ord(key)
        if key.startswith("F") and key[1:].isdigit():
            number = int(key[1:])
            if 1 <= number <= 24:
                return 0x70 + number - 1
        mapping = {
            "SPACE": 0x20, "ESCAPE": 0x1B, "RETURN": 0x0D, "ENTER": 0x0D, "TAB": 0x09,
            "BACKSPACE": 0x08, "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
            "PAGE_UP": 0x21, "PAGE_DOWN": 0x22, "LEFT": 0x25, "RIGHT": 0x27, "UP": 0x26, "DOWN": 0x28,
        }
        return mapping.get(key)

    def _parse(self, sequence: str):
        parts = split_sequence(sequence)
        if not parts:
            return None
        mods, key = parts
        vk = self._vk(key)
        if vk is None:
            return None
        flags = self.MOD_NOREPEAT
        for mod in mods:
            flags |= {"CTRL": self.MOD_CONTROL, "ALT": self.MOD_ALT, "SHIFT": self.MOD_SHIFT, "META": self.MOD_WIN}[mod]
        return flags, vk

    def start(self, bindings: dict[str, str]) -> bool:
        parsed = {action: self._parse(seq) for action, seq in bindings.items()}
        parsed = {action: item for action, item in parsed.items() if item}
        if not parsed:
            return False
        self.stop()
        self._stop.clear()
        self._ready.clear()
        self.registered = 0
        self.error = ""
        self._thread = threading.Thread(target=self._run, args=(parsed,), daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)
        return self.registered > 0 and not self.error

    def _run(self, parsed: dict) -> None:
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        messages = ctypes.wintypes.MSG()
        registered: dict[int, str] = {}
        try:
            for action, (flags, vk) in parsed.items():
                hotkey_id = (hash(action) & 0x7FFF) + 1
                if user32.RegisterHotKey(None, hotkey_id, flags, vk):
                    registered[hotkey_id] = action
            self.registered = len(registered)
            if not registered:
                self.error = "RegisterHotKey 失败（可能被其他程序占用）"
                return
            self._ready.set()
            while not self._stop.is_set():
                if user32.PeekMessageW(ctypes.byref(messages), None, 0, 0, 0x0001):
                    if messages.message == self.WM_HOTKEY:
                        action = registered.get(int(messages.wParam))
                        if action:
                            self.on_trigger(action)
                else:
                    self._stop.wait(0.05)
        except Exception as exc:
            self.error = f"Windows 全局热键异常：{exc}"
        finally:
            self._ready.set()
            for hotkey_id in registered:
                try:
                    user32.UnregisterHotKey(None, hotkey_id)
                except Exception:
                    pass

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None


class X11Backend(HotkeyBackend):
    name = "x11"

    def __init__(self, on_trigger):
        self.on_trigger = on_trigger
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self.registered = 0
        self.error = ""
        try:
            from Xlib import XK, X, display  # noqa: F401

            self._X = X
            self._XK = XK
            self._display_module = display
            self.available = True
        except Exception:
            self.available = False
            self.reason = "未安装 python-xlib（Linux 全局快捷键需要）"

    def _keycode(self, display, key: str) -> int | None:
        name = SPECIAL_KEYS.get(key, key if len(key) > 1 else key.lower())
        try:
            keysym = self._XK.string_to_keysym(name)
        except Exception:
            keysym = 0
        if not keysym:
            return None
        return display.keysym_to_keycode(keysym)

    def _mods(self, mods: list[str]) -> int:
        X = self._X
        mask = 0
        for mod in mods:
            mask |= {"CTRL": X.ControlMask, "ALT": X.Mod1Mask, "SHIFT": X.ShiftMask, "META": X.Mod4Mask}[mod]
        return mask

    def start(self, bindings: dict[str, str]) -> bool:
        if not self.available:
            return False
        self.stop()
        self._stop.clear()
        self._ready.clear()
        self.registered = 0
        self.error = ""
        self._thread = threading.Thread(target=self._run, args=(dict(bindings),), daemon=True)
        self._thread.start()
        # 等线程真正 grab 完成，否则 UI 会误报“已注册”
        self._ready.wait(timeout=2)
        return self.registered > 0 and not self.error

    def _run(self, bindings: dict[str, str]) -> None:
        X = self._X
        try:
            display = self._display_module.Display()
        except Exception as exc:
            self.error = f"无法连接 X11：{exc}"
            self._ready.set()
            return
        root = display.screen().root
        grabbed: list[tuple[int, int]] = []
        actions: dict[tuple[int, int], str] = {}
        try:
            for action, sequence in bindings.items():
                parts = split_sequence(sequence)
                if not parts:
                    continue
                mods, key = parts
                keycode = self._keycode(display, key)
                if not keycode:
                    continue
                base = self._mods(mods)
                for extra in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask):
                    mask = base | extra
                    try:
                        root.grab_key(keycode, mask, True, X.GrabModeAsync, X.GrabModeAsync)
                    except Exception:
                        continue
                    grabbed.append((keycode, mask))
                actions[(keycode, base)] = action

            display.flush()
            self.registered = len(actions)
            self._ready.set()
            while not self._stop.is_set():
                if display.pending_events():
                    event = display.next_event()
                    if getattr(event, "type", None) == X.KeyPress:
                        keycode = event.detail
                        state = event.state & ~(X.LockMask | X.Mod2Mask)
                        action = actions.get((keycode, state))
                        if action:
                            self.on_trigger(action)
                    continue
                self._stop.wait(0.08)
        except Exception as exc:
            self.error = f"X11 全局热键异常：{exc}"
        finally:
            self._ready.set()
            for keycode, mask in grabbed:
                try:
                    root.ungrab_key(keycode, mask)
                except Exception:
                    pass
            try:
                display.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None


@dataclass
class HotkeyStatus:
    backend: str
    available: bool
    message: str


class HotkeyService(QObject):
    triggered = Signal(str)
    statusChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: HotkeyBackend = self._make_backend()
        self.status = HotkeyStatus(
            backend=self._backend.name,
            available=self._backend.available,
            message=self._backend.reason,
        )

    @property
    def available(self) -> bool:
        return self._backend.available

    def _make_backend(self) -> HotkeyBackend:
        if os.name == "nt":
            try:
                import ctypes.wintypes  # noqa: F401

                return Win32Backend(self.triggered.emit)
            except Exception as exc:
                return NoopBackend(f"Windows 全局热键不可用：{exc}")
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return NoopBackend("Wayland 不支持全局热键，快捷键仅在窗口内生效")
        if not os.environ.get("DISPLAY"):
            return NoopBackend("没有可用的 X11 DISPLAY，快捷键仅在窗口内生效")
        backend = X11Backend(self.triggered.emit)
        if not backend.available:
            return NoopBackend(backend.reason)
        return backend

    def apply(self, bindings: dict[str, str]) -> HotkeyStatus:
        """bindings: action -> sequence（只传全局快捷键）。"""
        self._backend.stop()
        usable = {}
        skipped = []
        for action, sequence in bindings.items():
            if is_standard(sequence):
                usable[action] = sequence
            else:
                skipped.append(sequence)
        started = self._backend.start(usable) if usable else False
        error = getattr(self._backend, "error", "")
        if not self._backend.available:
            message = self._backend.reason
        elif error:
            message = f"全局热键注册失败：{error}"
        elif started:
            count = getattr(self._backend, "registered", len(usable))
            message = f"已注册 {count} 个全局热键（{self._backend.name}）"
            if skipped:
                message += f"；{', '.join(skipped)} 不支持全局"
        elif usable:
            message = "全局热键没有注册成功（可能被其他程序占用）"
        else:
            message = "没有设置全局热键"
        self.status = HotkeyStatus(self._backend.name, self._backend.available, message)
        self.statusChanged.emit(self.status)
        return self.status

    def stop(self) -> None:
        self._backend.stop()
