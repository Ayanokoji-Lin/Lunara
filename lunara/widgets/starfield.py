"""Lunara · 播放页背景的星光粒子层"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QWidget

from ..theme import qcolor


class StarField(QWidget):
    """缓慢呼吸的星点 + 中央柔光；用于“纯封面”模式。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        rnd = random.Random(2024)
        self._stars = [
            (rnd.random(), rnd.random(), rnd.uniform(0.7, 2.0),
             rnd.uniform(0, math.tau), rnd.uniform(0.6, 2.2))
            for _ in range(110)
        ]
        self._t = 0.0
        self._child: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def attach(self, child: QWidget) -> None:
        self._child = child
        child.setParent(self)
        self._place_child()

    def _step(self) -> None:
        self._t += 0.075
        self.update()

    def _place_child(self) -> None:
        if self._child is None:
            return
        cw, ch = self._child.width(), self._child.height()
        self._child.move((self.width() - cw) // 2, (self.height() - ch) // 2)

    def resizeEvent(self, e) -> None:
        self._place_child()
        super().resizeEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        glow = QRadialGradient(QPointF(self.width() / 2, self.height() / 2),
                              max(1.0, self.width() * 0.42))
        glow.setColorAt(0.0, QColor(139, 92, 246, 46))
        glow.setColorAt(0.55, QColor(139, 92, 246, 12))
        glow.setColorAt(1.0, QColor(139, 92, 246, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawRect(self.rect())

        w, h = self.width(), self.height()
        for x, y, r, phase, speed in self._stars:
            a = 40 + 150 * (0.5 + 0.5 * math.sin(self._t * speed + phase))
            p.setBrush(qcolor("text_main", int(a)))
            p.drawEllipse(QPointF(x * w, y * h), r, r)
