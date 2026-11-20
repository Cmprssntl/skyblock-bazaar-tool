"""快捷键字符串：CTRL+F / V+B。"""

from __future__ import annotations

STANDARD_MODS = {"CTRL", "ALT", "SHIFT", "META"}


def split_sequence(sequence: str) -> tuple[list[str], str] | None:
    if not sequence:
        return None
    parts = [part.strip().upper() for part in sequence.split("+") if part.strip()]
    if len(parts) < 2:
        return None
    key = parts[-1]
    mods = parts[:-1]
    if any(mod not in STANDARD_MODS for mod in mods):
        return None
    return mods, key


def is_standard_sequence(sequence: str) -> bool:
    return split_sequence(sequence) is not None
