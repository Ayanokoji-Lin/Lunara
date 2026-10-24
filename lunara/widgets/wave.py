"""Lunara · 跳动音波图标（正在播放指示）"""
from __future__ import annotations

import math

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

from ..theme import THEME


class WaveBars(QWidget):
    """4 根随相位起伏的竖条；QTimer 驱动，比逐帧动画更省 CPU。"""

    def __init__(self, bars: int = 4, color: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._bars = bars
        self._color = QColor(color or THEME["primary"])
        self._phase = 0.0
        self._running = False
        self.setFixedSize(bars * 5 + 2, 16)
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._step)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._timer.start()
            self.update()

    def stop(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self._phase = 0.0
            self.update()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def _step(self) -> None:
        self._phase = (self._phase + 0.55) % (math.pi * 2)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        h = self.height()
        bw = 2.6
        gap = (self.width() - self._bars * bw) / max(1, self._bars - 1)
        for i in range(self._bars):
            if self._running:
                k = abs(math.sin(self._phase + i * 0.85))
            else:
                k = 0.35
            bh = 3.0 + (h - 5) * (0.18 + 0.82 * k)
            x = i * (bw + gap)
            p.drawRoundedRect(QRectF(x, (h - bh) / 2, bw, bh), bw / 2, bw / 2)
