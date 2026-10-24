"""Lunara · 首页 Banner（淡入淡出轮播 + 底部渐变遮罩）

渐变遮罩与文字排版全部在 paintEvent 里用 QPainter 完成，
QSS 的 qlineargradient 无法做出“从透明到黑”的柔和过渡。
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget

from ..assets import cover_master, crop_fill
from ..theme import THEME
from .common import font


class BannerCarousel(QWidget):
    clicked = pyqtSignal(int)

    HEIGHT = 196

    def __init__(self, slides: list[dict], parent: QWidget | None = None):
        super().__init__(parent)
        self._slides = slides
        self._index = 0
        self._fade = 1.0
        self._prev_index: int | None = None
        self._cache: dict[tuple, QPixmap] = {}
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self._anim = QPropertyAnimation(self, b"fade", self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._timer = QTimer(self)
        self._timer.setInterval(6500)
        self._timer.timeout.connect(lambda: self.go((self._index + 1) % len(self._slides)))
        self._timer.start()

    # ---- 属性 ----
    def get_fade(self) -> float:
        return self._fade

    def set_fade(self, v: float) -> None:
        self._fade = float(v)
        self.update()

    fade = pyqtProperty(float, fget=get_fade, fset=set_fade)

    # ---- 轮播 ----
    def go(self, index: int) -> None:
        if index == self._index or not self._slides:
            return
        self._prev_index = self._index
        self._index = index % len(self._slides)
        self._anim.stop()
        self._fade = 0.0
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self.update()

    def _pixmap(self, i: int) -> QPixmap:
        s = self._slides[i]
        key = (s["seed"], self.width(), self.height())
        pm = self._cache.get(key)
        if pm is None:
            base = cover_master(s["seed"], s["hue"])
            pm = crop_fill(base, max(1, self.width()), max(1, self.height()))
            self._cache[key] = pm
        return pm

    # ---- 事件 ----
    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        # 右下角圆点区域：切换指定页
        if e.position().y() > self.height() - 34 and e.position().x() > self.width() - 130:
            i = int((e.position().x() - (self.width() - 100)) // 22)
            self.go(max(0, min(i, len(self._slides) - 1)))
            return
        self.clicked.emit(self._index)

    # ---- 绘制 ----
    def paintEvent(self, _e) -> None:
        if not self._slides:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect())

        clip = QPainterPath()
        clip.addRoundedRect(rect, 12, 12)
        p.setClipPath(clip)

        if self._prev_index is not None and self._fade < 1.0:
            p.setOpacity(1.0)
            p.drawPixmap(rect, self._pixmap(self._prev_index),
                         QRectF(self._pixmap(self._prev_index).rect()))
            p.setOpacity(self._fade)
            pm = self._pixmap(self._index)
            p.drawPixmap(rect, pm, QRectF(pm.rect()))
        else:
            pm = self._pixmap(self._index)
            p.drawPixmap(rect, pm, QRectF(pm.rect()))
        p.setOpacity(1.0)

        # 底部 → 透明 的柔和遮罩
        g = QLinearGradient(rect.left(), rect.bottom(), rect.left(), rect.top() * 0.55)
        g.setColorAt(0.0, QColor(8, 12, 24, 225))
        g.setColorAt(0.45, QColor(8, 12, 24, 150))
        g.setColorAt(1.0, QColor(8, 12, 24, 0))
        p.fillRect(rect, g)

        # 左侧补一层，保证标题对比度
        g2 = QLinearGradient(rect.left(), 0, rect.left() + rect.width() * 0.55, 0)
        g2.setColorAt(0.0, QColor(8, 12, 24, 150))
        g2.setColorAt(1.0, QColor(8, 12, 24, 0))
        p.fillRect(rect, g2)

        s = self._slides[self._index]
        # 标签
        p.setFont(font(9, 600))
        tag = s.get("tag", "")
        tw = p.fontMetrics().horizontalAdvance(tag) + 18
        tag_rect = QRectF(32, 32, tw, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(139, 92, 246, 210))
        p.drawRoundedRect(tag_rect, 10, 10)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(tag_rect, int(Qt.AlignmentFlag.AlignCenter), tag)

        # 标题 / 副标题
        p.setFont(font(26, 700))
        # 轮播底图始终是深色画作，文字固定用浅色，不跟随主题
        p.setPen(QColor("#F8FAFC"))
        p.drawText(QRectF(32, self.height() - 96, self.width() - 260, 40),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   s["title"])
        p.setFont(font(12))
        p.setPen(QColor(203, 213, 225, 215))
        p.drawText(QRectF(33, self.height() - 52, self.width() - 300, 24),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   s["subtitle"])

        # 指示点
        base_x = self.width() - 32 - len(self._slides) * 18
        for i in range(len(self._slides)):
            active = i == self._index
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(THEME["primary"]) if active else QColor(255, 255, 255, 90))
            w = 16 if active else 6
            p.drawRoundedRect(QRectF(base_x + i * 18, self.height() - 28, w, 6), 3, 3)
