"""Lunara · 黑胶唱片（QPropertyAnimation 匀速旋转）"""
from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from ..assets import cover_pixmap, crop_fill, rounded
from ..services.covers import covers
from ..theme import THEME


class VinylDisc(QWidget):
    """黑胶：外圈主色环 + 细密纹路 + 中央封面 + 中心孔。

    旋转使用 QPropertyAnimation(angle)，20 秒 / 圈，Linear 缓动，
    loopCount=-1 无限循环；暂停时调用 pause()，恢复时 resume()，
    角度连续，不会“跳帧”。
    """

    def __init__(self, diameter: int = 340, compact: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._d = diameter
        self._compact = compact
        self._angle = 0.0
        self._disc: QPixmap | None = None      # 盘体+纹路只画一次，逐帧只旋转封面
        self._seed = 1
        self._hue: int | None = None
        self._url = ""
        self._cover: QPixmap | None = None
        self.setFixedSize(diameter, diameter)
        covers().ready.connect(self._on_cover_ready)

        self._anim = QPropertyAnimation(self, b"angle", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(360.0)
        self._anim.setDuration(20000)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)

    # ---- 旋转属性 ----
    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float) -> None:
        self._angle = float(value)
        self.update()

    angle = pyqtProperty(float, fget=get_angle, fset=set_angle)

    # ---- 数据 ----
    def set_track(self, seed: int, hue: int | None = None, url: str = "") -> None:
        self._seed, self._hue, self._url = seed, hue, url
        self._cover = None
        self.update()

    def _on_cover_ready(self, seed: int) -> None:
        if seed == self._seed and self._url:
            self._cover = None
            self.update()

    def _resolve_cover(self) -> QPixmap:
        dpr = max(1.0, self.devicePixelRatioF())
        size = max(8, int(self._d * (0.60 if not self._compact else 0.82) * dpr))
        if self._url:
            master = covers().pixmap(self._seed, self._url)
            if master is not None and not master.isNull():
                pm = crop_fill(master, size, size)
                pm = rounded(pm, size / 2)
                pm.setDevicePixelRatio(dpr)
                return pm
        # 空态：程序化月牙封面
        pm = cover_pixmap(self._seed, size, self._hue, radius=size / 2)
        pm.setDevicePixelRatio(dpr)
        return pm

    # ---- 播放状态 ----
    def start(self) -> None:
        state = self._anim.state()
        if state == QAbstractAnimation.State.Paused:
            self._anim.resume()
        elif state != QAbstractAnimation.State.Running:
            self._anim.start()

    def hideEvent(self, e) -> None:
        if self._anim.state() == QAbstractAnimation.State.Running:
            self._anim.pause()
        super().hideEvent(e)

    def showEvent(self, e) -> None:
        if self._anim.state() == QAbstractAnimation.State.Paused:
            self._anim.resume()
        super().showEvent(e)

    def stop(self) -> None:
        if self._anim.state() == QAbstractAnimation.State.Running:
            self._anim.pause()

    # ---- 绘制 ----
    def _render_disc(self) -> QPixmap:
        """盘体 + 阴影 + 26 圈纹路：只画一次，逐帧复用。"""
        w, h = self.width(), self.height()
        pm = QPixmap(max(1, w), max(1, h))
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        c = QPointF(w / 2, h / 2)
        R = min(w, h) / 2 - 3

        sh = QRadialGradient(QPointF(c.x(), c.y() + R * 0.10), R * 1.05)
        sh.setColorAt(0.0, QColor(0, 0, 0, 130))
        sh.setColorAt(0.75, QColor(0, 0, 0, 60))
        sh.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sh)
        p.drawEllipse(QPointF(c.x(), c.y() + R * 0.06), R * 1.04, R * 1.04)

        body = QRadialGradient(QPointF(c.x() - R * 0.35, c.y() - R * 0.40), R * 1.55)
        body.setColorAt(0.0, QColor(38, 40, 56))
        body.setColorAt(0.45, QColor(19, 21, 32))
        body.setColorAt(1.0, QColor(7, 8, 14))
        p.setBrush(body)
        p.drawEllipse(c, R, R)

        grooves = 26 if not self._compact else 8
        for i in range(grooves):
            r = R * (0.64 + i * (0.34 / max(1, grooves)))
            pen = QPen(QColor(255, 255, 255, 7 + (i % 3) * 4))
            pen.setWidthF(0.8)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, r, r)
        p.end()
        return pm

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        R = min(w, h) / 2 - 3

        if self._disc is None or self._disc.size() != self.size():
            self._disc = self._render_disc()
        p.drawPixmap(0, 0, self._disc)

        # 旋转部分：封面 + 内圈
        p.save()
        p.translate(c)
        p.rotate(self._angle)
        rc = R * (0.58 if not self._compact else 0.80)
        if self._cover is None:
            self._cover = self._resolve_cover()
        p.drawPixmap(QRectF(-rc, -rc, rc * 2, rc * 2), self._cover,
                     QRectF(self._cover.rect()))
        ring = QPen(QColor(255, 255, 255, 26))
        ring.setWidthF(1.2)
        p.setPen(ring)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), rc, rc)
        # 高光弧
        hl = QPen(QColor(255, 255, 255, 20))
        hl.setWidthF(rc * 0.18)
        p.setPen(hl)
        p.drawArc(QRectF(-rc * 0.92, -rc * 0.92, rc * 1.84, rc * 1.84), 40 * 16, 60 * 16)
        p.restore()

        # 中心孔
        hole = 5 if not self._compact else 3
        p.setPen(QPen(QColor(THEME["primary"]), 1.2))
        p.setBrush(QColor(10, 12, 20))
        p.drawEllipse(c, hole, hole)

        # 外圈主色环
        outer = QPen(QColor(THEME["primary"]))
        outer.setWidthF(2.0 if not self._compact else 1.6)
        p.setPen(outer)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, R - 1, R - 1)

        # 顶部月光渐变（模拟环境光）
        gloss = QLinearGradient(c.x(), c.y() - R, c.x(), c.y() + R)
        gloss.setColorAt(0.0, QColor(226, 232, 240, 26))
        gloss.setColorAt(0.35, QColor(226, 232, 240, 0))
        gloss.setColorAt(1.0, QColor(0, 0, 0, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gloss)
        p.drawEllipse(c, R - 2, R - 2)
