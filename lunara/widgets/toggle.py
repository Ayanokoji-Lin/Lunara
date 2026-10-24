"""Lunara · 胶囊开关（自绘 + 滑块动画）

QSS 只能画出“会变色的胶囊”，滑块没有过渡动画；
这里用 QAbstractButton + QPropertyAnimation 实现，观感更好。
QSS 里同时保留了 QCheckBox#PillCheck 的纯样式方案作为降级。
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QAbstractButton

from ..theme import THEME


class Switch(QAbstractButton):
    W, H = 40, 22

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, v: float) -> None:
        self._offset = float(v)
        self.update()

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            # 未实现的开关要看得出来是灰的，否则和可用的一模一样
            p.setOpacity(0.35)
        r = self.H / 2
        track = QRectF(0, 0, self.W, self.H)

        if self._offset <= 0.01:
            p.setBrush(QColor(THEME["bg_elev"]))
            p.setPen(QColor(THEME["border"]))
        else:
            c = QColor(THEME["primary"])
            c.setAlpha(int(60 + 195 * self._offset))
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

        # 滑块
        pad = 3.0
        kd = self.H - pad * 2
        x = pad + self._offset * (self.W - kd - pad * 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QPointF(x + kd / 2, pad + kd / 2 + 0.8), kd / 2, kd / 2)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(x + kd / 2, pad + kd / 2), kd / 2, kd / 2)
