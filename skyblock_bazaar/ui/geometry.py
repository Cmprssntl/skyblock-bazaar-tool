"""窗口几何：保存/恢复（不依赖 QByteArray，便于写进 JSON 配置）。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def apply_geometry(widget: QWidget, data) -> bool:
    if not isinstance(data, dict):
        return False
    try:
        width = int(data.get("w") or 0)
        height = int(data.get("h") or 0)
        x = int(data["x"]) if data.get("x") is not None else None
        y = int(data["y"]) if data.get("y") is not None else None
    except (TypeError, ValueError):
        return False
    if width < 200 or height < 150:
        return False
    if x is None or y is None:
        widget.resize(width, height)
    else:
        widget.setGeometry(x, y, width, height)
    return True


def geometry_dict(widget: QWidget) -> dict:
    rect = widget.geometry()
    return {"w": rect.width(), "h": rect.height(), "x": rect.x(), "y": rect.y()}
