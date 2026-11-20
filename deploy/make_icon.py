"""生成 bazaar.png / bazaar.ico（无外部依赖，使用 Qt 绘制）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

ROOT = Path(__file__).resolve().parent.parent
BG_TOP = QColor("#141d27")
BG_BOTTOM = QColor("#0a0e13")
GOLD = QColor("#e0b060")
UP = QColor("#ff5c6c")
DOWN = QColor("#2ecc71")
GRID = QColor("#22303d")


def draw(size: int = 256) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.045
    card = QRectF(margin, margin, size - margin * 2, size - margin * 2)
    gradient = QLinearGradient(card.topLeft(), card.bottomRight())
    gradient.setColorAt(0, BG_TOP)
    gradient.setColorAt(1, BG_BOTTOM)
    path = QPainterPath()
    path.addRoundedRect(card, size * 0.16, size * 0.16)
    p.fillPath(path, gradient)
    p.setPen(QPen(GOLD, max(2.0, size * 0.014)))
    p.drawPath(path)

    # 网格
    p.setPen(QPen(GRID, max(1.0, size * 0.005)))
    left = size * 0.17
    right = size * 0.83
    top = size * 0.24
    bottom = size * 0.76
    for index in range(1, 4):
        y = top + (bottom - top) * index / 4
        p.drawLine(QPointF(left, y), QPointF(right, y))

    # 蜡烛：open/high/low/close（0~1）
    candles = [
        (0.58, 0.72, 0.44, 0.62, True),
        (0.50, 0.58, 0.34, 0.40, True),
        (0.62, 0.68, 0.46, 0.52, False),
        (0.40, 0.47, 0.28, 0.32, True),
        (0.30, 0.38, 0.16, 0.22, True),
        (0.24, 0.30, 0.12, 0.18, False),
    ]
    slot = (right - left) / len(candles)
    body_w = slot * 0.46

    def y_of(value: float) -> float:
        return bottom - value * (bottom - top)

    closes = []
    for index, (open_v, high_v, low_v, close_v, up) in enumerate(candles):
        x = left + slot * (index + 0.5)
        color = UP if up else DOWN
        p.setPen(QPen(color, max(1.5, size * 0.009)))
        p.drawLine(QPointF(x, y_of(high_v)), QPointF(x, y_of(low_v)))
        body = QRectF(
            x - body_w / 2,
            y_of(max(open_v, close_v)),
            body_w,
            max(size * 0.012, abs(y_of(close_v) - y_of(open_v))),
        )
        if up:
            p.fillRect(body, QColor("#141d27"))
            p.drawRect(body)
        else:
            p.fillRect(body, color)
        closes.append((x, y_of((open_v + close_v) / 2)))

    # 金色均线
    line = QPainterPath()
    line.moveTo(QPointF(closes[0][0], closes[0][1]))
    for point in closes[1:]:
        line.lineTo(QPointF(point[0], point[1]))
    p.setPen(QPen(GOLD, max(2.0, size * 0.014), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawPath(line)

    p.end()
    return image


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - 需要 QGuiApplication 才能用字体/绘制
    image = draw(256)
    image.save(str(ROOT / "bazaar.png"), "PNG")
    image.save(str(ROOT / "bazaar.ico"), "ICO")
    print("wrote bazaar.png / bazaar.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
