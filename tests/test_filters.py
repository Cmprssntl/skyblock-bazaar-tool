"""单位解析与显示：后缀与下拉单位互斥，非法输入可识别。"""

from __future__ import annotations

from skyblock_bazaar.ui.format import format_value, parse_bound, validate_bound


def test_suffix_and_unit_are_exclusive():
    assert parse_bound("10k", "默认") == (10_000.0, True)
    assert parse_bound("2.5m", "默认") == (2_500_000.0, True)
    assert parse_bound("1b", "默认") == (1_000_000_000.0, True)
    # 关键回归：下拉单位 k 与后缀 k 同时出现时不重复乘
    assert parse_bound("10k", "k") == (10_000.0, True)
    assert parse_bound("10", "k") == (10_000.0, True)


def test_empty_and_invalid():
    assert parse_bound("", "m") == (None, True)
    assert parse_bound("   ", "默认") == (None, True)
    value, ok = parse_bound("abc", "默认")
    assert value is None and ok is False
    assert validate_bound("abc") is not None
    assert validate_bound("10k") is None


def test_commas_and_spaces():
    assert parse_bound(" 1,234 ", "默认") == (1234.0, True)


def test_format_value():
    assert format_value(None, "默认", "price") == "-"
    assert format_value(1234.567, "默认", "price") == "1,234.57"
    assert format_value(1_500_000, "m", "price") == "1.50"
    assert format_value(1234, "k", "count") == "1"
    assert format_value(12.3456, "默认", "percent") == "12.35"
    assert format_value(4, "默认", "level") == "IV"
    assert format_value(3661, "默认", "duration") == "1小时1分"
    assert format_value("abc", "默认", "text") == "abc"
