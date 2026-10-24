"""Lunara · 播放页背景的星光粒子层"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap, QRadialGradient
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
        self._glow: QPixmap | None = None      # 柔光只画一次，之后当背景贴
        self._child: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)      # 30fps：柔光已缓存，只剩星点
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

    def _render_glow(self) -> QPixmap:
        pm = QPixmap(max(1, self.width()), max(1, self.height()))
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        glow = QRadialGradient(QPointF(pm.width() / 2, pm.height() / 2),
                              max(1.0, pm.width() * 0.42))
        glow.setColorAt(0.0, QColor(139, 92, 246, 46))
        glow.setColorAt(0.55, QColor(139, 92, 246, 12))
        glow.setColorAt(1.0, QColor(139, 92, 246, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawRect(pm.rect())
        p.end()
        return pm

    def resizeEvent(self, e) -> None:
        self._glow = None
        self._place_child()
        super().resizeEvent(e)

    def showEvent(self, e) -> None:
        if not self._timer.isActive():
            self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e) -> None:
        # 看不见就别画：播放页在别的 Tab 时不该占 CPU
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._glow is None:
            self._glow = self._render_glow()
        p.drawPixmap(0, 0, self._glow)

        w, h = self.width(), self.height()
        for x, y, r, phase, speed in self._stars:
            a = 40 + 150 * (0.5 + 0.5 * math.sin(self._t * speed + phase))
            p.setBrush(qcolor("text_main", int(a)))
            p.drawEllipse(QPointF(x * w, y * h), r, r)
