"""Bazaar 页面：直接使用 provider 生成的行。"""

from __future__ import annotations


def build_rows(snapshot, settings=None) -> list[dict]:
    return list(snapshot.bazaar)
