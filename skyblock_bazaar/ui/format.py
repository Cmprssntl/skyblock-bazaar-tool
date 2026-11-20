"""数值解析与显示：单位后缀与下拉单位互斥（修复 v3.5 的双重换算）。"""

from __future__ import annotations

UNIT_SCALE = {"默认": 1.0, "k": 1e3, "m": 1e6, "b": 1e9}
UNIT_CHOICES = ("默认", "k", "m", "b")
SUFFIXES = {"k": 1e3, "m": 1e6, "b": 1e9}


def parse_bound(text: str, unit: str = "默认") -> tuple[float | None, bool]:
    """返回 (值, 是否合法)。空字符串返回 (None, True)；非法输入返回 (None, False)。

    输入 `10k` 时后缀优先，忽略下拉单位；输入 `10` 时使用下拉单位。
    """
    raw = str(text or "").strip().replace(",", "").replace("_", "")
    if not raw:
        return None, True
    suffix = raw[-1].lower()
    explicit = suffix in SUFFIXES and len(raw) > 1
    if explicit:
        raw = raw[:-1]
    try:
        value = float(raw)
    except ValueError:
        return None, False
    value *= SUFFIXES[suffix] if explicit else UNIT_SCALE.get(unit, 1.0)
    return value, True


def validate_bound(text: str, unit: str = "默认") -> str | None:
    _value, ok = parse_bound(text, unit)
    return None if ok else "格式无效，可输入数字或 10k / 2.5m / 1b"


def format_value(value, unit: str = "默认", kind: str = "count") -> str:
    if value is None or value == "":
        return "-"
    if kind == "text":
        return str(value)
    if kind == "level":
        from ..data.recipes import to_roman

        try:
            return to_roman(int(value))
        except (TypeError, ValueError):
            return "-"
    if kind == "duration":
        from ..analysis.forge import format_duration

        return format_duration(float(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    scale = UNIT_SCALE.get(unit, 1.0)
    number /= scale
    if kind == "count":
        return f"{number:,.0f}"
    if kind == "percent":
        return f"{number:,.2f}"
    return f"{number:,.2f}"


def format_int(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{float(value):,.0f}"


def format_age(seconds: float | None) -> str:
    if not seconds or seconds < 0:
        return "从未"
    if seconds < 60:
        return f"{int(seconds)} 秒前"
    if seconds < 3600:
        return f"{int(seconds / 60)} 分钟前"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} 小时前"
    return f"{seconds / 86400:.1f} 天前"
