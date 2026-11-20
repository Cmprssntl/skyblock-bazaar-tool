"""K 线图：蜡烛 + 成交量 + MA + 十字光标 + 缩放/平移（参考 SimNow chart.py）。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..history.bars import Bar, format_full_ts, format_ts
from .format import format_int
from .theme import ACCENT, BG, CARD, DOWN, GRID, MUTED, TEXT, UP, mono_font

MA_WINDOWS = (5, 10, 20)
MA_COLORS = ("#e0b060", "#6fa8dc", "#c678dd")
TEXT_C = QColor(TEXT)
MUTED_C = QColor(MUTED)


class KlineChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._bars: list[Bar] = []
        self._ma: list[list[float | None]] = []
        self._period = 60
        self._instrument = ""
        self._price_label = "中间价"
        self._hover: int | None = None
        self._visible = 120
        self._offset = 0
        self._drag_x: float | None = None
        self._drag_offset = 0
        self._axis_right = 68
        self._top = 22
        self._bottom = 20

    # ------------------------------------------------------------ 数据
    def set_data(self, instrument: str, bars: list[Bar], period: int, price_label: str = "中间价") -> None:
        keep_end = len(self._bars) - self._offset
        self._instrument = instrument
        self._bars = bars
        self._period = period
        self._price_label = price_label
        self._compute_ma()
        if keep_end > 0 and self._offset:
            # 刷新时保持当前查看位置（按索引比例回退）
            self._offset = max(0, len(bars) - keep_end)
        self._clamp()
        self.update()

    def _compute_ma(self) -> None:
        closes = [bar.close for bar in self._bars]
        result: list[list[float | None]] = []
        for window in MA_WINDOWS:
            series: list[float | None] = [None] * len(closes)
            running = 0.0
            for index, value in enumerate(closes):
                running += value
                if index >= window:
                    running -= closes[index - window]
                if index >= window - 1:
                    series[index] = running / window
            result.append(series)
        self._ma = result

    # ------------------------------------------------------------ 视窗
    def _clamp(self) -> None:
        self._visible = max(20, min(2000, int(self._visible)))
        self._offset = max(0, min(max(0, len(self._bars) - self._visible), int(self._offset)))

    def _range(self) -> tuple[int, int]:
        end = max(0, len(self._bars) - self._offset)
        start = max(0, end - self._visible)
        return start, end

    def wheelEvent(self, event) -> None:  # noqa: N802
        if not self._bars:
            return
        steps = event.angleDelta().y() / 120
        if steps == 0:
            return
        before = self._visible
        factor = 0.85 if steps > 0 else 1.18
        self._visible = max(20, min(2000, int(self._visible * factor)))
        # 以最右侧为锚点缩放
        if self._visible == before:
            return
        self._clamp()
        self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_x = event.position().x()
            self._drag_offset = self._offset
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_x = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._bars:
            return
        if self._drag_x is not None:
            slot = self._slot()
            if slot:
                delta = round((event.position().x() - self._drag_x) / slot)
                self._offset = max(0, min(len(self._bars) - 1, self._drag_offset + delta))
                self._clamp()
                self._hover = None
                self.update()
                return
        start, end = self._range()
        slot = self._slot()
        if slot <= 0:
            return
        index = int((event.position().x() - self._x_start()) / slot) + start
        index = max(start, min(end - 1, index))
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._offset = 0
        self._visible = 120
        self._clamp()
        self.update()

    # ------------------------------------------------------------ 几何
    def _price_area(self) -> tuple[float, float, float]:
        top = self._top
        bottom = self.height() - self._bottom
        vol_h = (bottom - top) * 0.22
        return top, bottom, vol_h

    def _slot(self) -> float:
        start, end = self._range()
        count = max(1, end - start)
        usable = self.width() - 10 - self._axis_right
        return max(1.0, usable / count)

    def _x_start(self) -> float:
        return 10.0

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(BG))
        p.fillRect(rect.adjusted(6, 6, -6, -6), QColor(CARD))
        if rect.width() < 120 or rect.height() < 120:
            return

        p.setFont(mono_font(9))
        if len(self._bars) < 2:
            p.setPen(MUTED_C)
            hint = "等待本地行情…（保持程序运行并开启自动刷新即可积累 K 线）"
            p.drawText(rect.adjusted(16, 0, -16, 0), Qt.AlignmentFlag.AlignVCenter, hint)
            return

        start, end = self._range()
        bars = self._bars[start:end]
        top, bottom, vol_h = self._price_area()
        price_bottom = bottom - vol_h - 12
        vol_top = price_bottom + 12
        left = 10.0
        right = self.width() - self._axis_right
        slot = self._slot()
        x_start = self._x_start()
        body_w = max(1.0, min(9.0, slot * 0.68))

        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]
        hi, lo = max(highs), min(lows)
        pad = (hi - lo) * 0.06 or max(hi * 0.005, 1.0)
        hi += pad
        lo -= pad
        span = hi - lo or 1.0

        volumes = sorted(bar.volume for bar in bars)
        max_vol = (volumes[int(len(volumes) * 0.95)] if len(volumes) > 4 else max(volumes, default=1)) or 1

        def px(index: int) -> float:
            return x_start + (index - start + 0.5) * slot

        def py(value: float) -> float:
            return top + (1 - (value - lo) / span) * (price_bottom - top)

        def vy(value: float) -> float:
            return vol_top + (1 - min(value, max_vol) / max_vol) * vol_h

        # 网格 + 价格刻度
        p.setPen(QPen(QColor(GRID), 1))
        for i in range(5):
            gy = top + i / 4 * (price_bottom - top)
            p.drawLine(QPointF(left, gy), QPointF(right, gy))
            p.setPen(MUTED_C)
            p.drawText(
                QRectF(right + 6, gy - 8, self._axis_right - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._axis_label(hi - i / 4 * span),
            )
            p.setPen(QPen(QColor(GRID), 1))
        p.drawLine(QPointF(right, vol_top - 6), QPointF(right, bottom))

        # 蜡烛 + 成交量
        for index in range(start, end):
            bar = self._bars[index]
            x = px(index)
            color = UP if bar.up else DOWN
            p.setPen(QPen(color, 1))
            p.drawLine(QPointF(x, py(bar.high)), QPointF(x, py(bar.low)))
            y_open, y_close = py(bar.open), py(bar.close)
            body = QRectF(x - body_w / 2, min(y_open, y_close), body_w, max(1.0, abs(y_close - y_open)))
            if bar.up:
                p.fillRect(body, QColor(CARD))
                p.drawRect(body)
            else:
                p.fillRect(body, color)
            if bar.volume > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(color))
                p.drawRect(
                    QRectF(x - body_w / 2, vy(bar.volume), body_w, max(1.0, vol_top + vol_h - vy(bar.volume)))
                )

        # 均线
        for _window, color, series in zip(MA_WINDOWS, MA_COLORS, self._ma, strict=False):
            path = QPainterPath()
            started = False
            for index in range(start, end):
                value = series[index]
                if value is None:
                    continue
                point = QPointF(px(index), py(value))
                if not started:
                    path.moveTo(point)
                    started = True
                else:
                    path.lineTo(point)
            if started:
                p.setPen(QPen(QColor(color), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)

        # 末价线 + 标签
        last = self._bars[-1].close
        if lo <= last <= hi:
            p.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DotLine))
            y = py(last)
            p.drawLine(QPointF(left, y), QPointF(right, y))
            self._tag(p, QRectF(right + 2, y - 8, self._axis_right - 4, 16), self._axis_label(last), QColor("#2a2417"), QColor(ACCENT))

        # 顶栏信息
        p.setPen(QColor("#c6d2de"))
        if self._hover is not None and start <= self._hover < end:
            bar = self._bars[self._hover]
            p.setPen(QPen(QColor("#4b5a6a"), 1, Qt.PenStyle.DashLine))
            cx = px(self._hover)
            p.drawLine(QPointF(cx, top), QPointF(cx, vol_top + vol_h))
            y = py(bar.close)
            p.drawLine(QPointF(left, y), QPointF(right, y))
            self._tag(p, QRectF(right + 2, y - 8, self._axis_right - 4, 16), self._axis_label(bar.close), QColor("#1f2c38"), TEXT_C)
            moment = format_full_ts(bar.ts, self._period)
            info = (
                f"{self._instrument}  {self._price_label}  {moment}  "
                f"开 {bar.open:,.1f}  高 {bar.high:,.1f}  低 {bar.low:,.1f}  收 {bar.close:,.1f}  量 {format_int(bar.volume)}"
            )
        else:
            change = last - bars[0].open
            pct = change / bars[0].open * 100 if bars[0].open else 0
            info = (
                f"{self._instrument}  {self._price_label}  收 {last:,.1f}  "
                f"可视涨跌 {change:+,.1f} ({pct:+.2f}%)  高 {hi:,.1f}  低 {lo:,.1f}  "
                f"量 {format_int(sum(bar.volume for bar in bars))}"
            )
        p.setPen(QColor("#c6d2de"))
        p.drawText(QRectF(left + 2, 2, self.width() - self._axis_right - 8, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, info)

        # 时间刻度
        p.setPen(MUTED_C)
        p.setFont(mono_font(8))
        label_gap = 78.0
        last_x = -1000.0
        last_day = None
        for index in range(start, end):
            x = px(index)
            if x - last_x < label_gap and index != end - 1:
                continue
            if self._period >= 86400:
                text = format_ts(self._bars[index].ts, self._period)
            else:
                moment = datetime.fromtimestamp(self._bars[index].ts)
                day = moment.date()
                if last_day is None or day != last_day:
                    text = moment.strftime("%m-%d")
                    last_day = day
                else:
                    text = moment.strftime("%H:%M")
            p.drawText(QRectF(min(max(x - 26, 2), self.width() - 60), bottom + 2, 56, 14), Qt.AlignmentFlag.AlignCenter, text)
            last_x = x

        # MA 图例（画在价格区右上角，避免与时间刻度重叠）
        p.setFont(mono_font(8))
        legend_w = 3 * 50 + 6
        legend_x = right - legend_w
        legend_y = top + 2
        p.fillRect(QRectF(legend_x - 4, legend_y - 2, legend_w + 4, 15), QColor(CARD))
        for window, color in zip(MA_WINDOWS, MA_COLORS, strict=False):
            p.setPen(QColor(color))
            p.drawText(QRectF(legend_x, legend_y, 48, 12), Qt.AlignmentFlag.AlignLeft, f"MA{window}")
            legend_x += 50

    @staticmethod
    def _axis_label(value: float) -> str:
        magnitude = abs(value)
        if magnitude >= 1e9:
            return f"{value / 1e9:,.2f}b"
        if magnitude >= 1e6:
            return f"{value / 1e6:,.2f}m"
        if magnitude >= 1e5:
            return f"{value / 1e3:,.0f}k"
        return f"{value:,.1f}"

    @staticmethod
    def _tag(p: QPainter, rect: QRectF, text: str, bg: QColor, fg: QColor) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRect(rect)
        p.setPen(fg)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
