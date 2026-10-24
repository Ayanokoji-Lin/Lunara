"""Lunara · 细进度条（自绘，带下载中的流光）

QSS 版 QProgressBar 只能做纯色块，且圆角受“半径必须小于半高”的限制；
这里直接自绘：轨道 + 填充 + 流光扫过，高度 5px 也能保持干净。
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme import THEME

# 注意：QColor 不认 CSS 的 "rgba(...)" 字符串，必须用 (r,g,b,a) 或 #hex
COLORS = {
    "downloading": QColor(THEME["primary"]),
    "paused": QColor(THEME["text_dim"]),
    "done": QColor(139, 92, 246, 110),
    "failed": QColor(THEME["danger"]),
}


class ThinProgress(QWidget):
    def __init__(self, height: int = 5, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = 0.0
        self._state = "downloading"
        self._offset = 0.0
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._timer = QTimer(self)
        self._timer.setInterval(55)
        self._timer.timeout.connect(self._step)

    # ---- 状态 ----
    def set_value(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._value) > 1e-4:
            self._value = value
            self.update()

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "downloading":
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._offset = 0.0
        self.update()

    def _step(self) -> None:
        self._offset = (self._offset + 0.022) % 1.0
        self.update()

    # ---- 绘制 ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        r = h / 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(THEME["border"]))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        fill_w = w * self._value
        if fill_w <= 0.5:
            return

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, fill_w, h), r, r)
        p.fillPath(path, COLORS.get(self._state, QColor(THEME["primary"])))

        if self._state == "downloading" and fill_w > 14:
            p.save()
            p.setClipPath(path)
            x = self._offset * (fill_w + 120) - 60
            g = QLinearGradient(x, 0, x + 60, 0)
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(0.5, QColor(255, 255, 255, 78))
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(x, 0, 60, h), g)
            p.restore()
