"""Lunara · 封面卡片 / 封面控件

列表滚动性能要点：
1) 封面走 assets.cover_pixmap 的多级缓存，尺寸变化才会重绘；
2) 卡片整体自绘（paintEvent），避免嵌套 QLabel 造成的布局开销；
3) 悬停播放按钮、播放量胶囊都在同一帧里绘制。
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget

from ..assets import cover_pixmap, crop_fill, rounded
from ..services.covers import covers
from ..theme import THEME
from .common import draw_wrapped, font
from .icons import pixmap


class CoverArt(QWidget):
    """圆角封面（可带柔和阴影），HiDPI 友好。"""

    def __init__(self, size: int = 48, radius: float = 6,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self._radius = radius
        self._base_radius = radius
        self._seed = 1
        self._hue: int | None = None
        self._url = ""
        self._pm: QPixmap | None = None
        self.setFixedSize(size, size)
        covers().ready.connect(self._on_cover_ready)

    def set_cover(self, seed: int, hue: int | None = None, url: str = "") -> None:
        self._seed, self._hue, self._url = seed, hue, url
        self._pm = None
        self.update()

    def set_round(self, on: bool = True) -> None:
        """切换成圆形（歌手头像用）；圆角值等于半边长。"""
        radius = self._size / 2 if on else self._base_radius
        if radius == self._radius:
            return
        self._radius = radius
        self._pm = None
        self.update()

    def _on_cover_ready(self, seed: int) -> None:
        if seed == self._seed and self._url:
            self._pm = None
            self.update()

    def _resolve(self) -> QPixmap:
        dpr = max(1.0, self.devicePixelRatioF())
        px = int(self._size * dpr)
        if self._url:
            master = covers().pixmap(self._seed, self._url)
            if master is not None and not master.isNull():
                pm = crop_fill(master, px, px)
                pm = rounded(pm, self._radius * dpr)
                pm.setDevicePixelRatio(dpr)
                return pm
        # 空态：程序化月牙封面
        pm = cover_pixmap(self._seed, px, self._hue, radius=self._radius * dpr)
        pm.setDevicePixelRatio(dpr)
        return pm

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._pm is None:
            self._pm = self._resolve()
        p.drawPixmap(QRectF(0, 0, self._size, self._size), self._pm,
                     QRectF(self._pm.rect()))


class CoverCard(QWidget):
    """歌单 / 专辑 / 歌手卡片：封面 + 播放量胶囊 + 两行标题。"""

    clicked = pyqtSignal()
    playClicked = pyqtSignal()

    TEXT_BLOCK = 62

    def __init__(self, seed: int, hue: int | None = None, title: str = "",
                 subtitle: str = "", plays: str = "", round_cover: bool = False,
                 cover_url: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._seed = seed
        self._hue = hue
        self._title = title
        self._subtitle = subtitle
        self._plays = plays
        self._round = round_cover
        self._cover_url = cover_url
        self._hover = False
        self._pm: QPixmap | None = None
        self._pm_size = 0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(),
                           self.sizePolicy().verticalPolicy())
        covers().ready.connect(self._on_cover_ready)

    # ---- 数据 ----
    def set_data(self, seed: int, hue: int | None, title: str,
                 subtitle: str = "", plays: str = "", cover_url: str = "") -> None:
        self._seed, self._hue = seed, hue
        self._title, self._subtitle, self._plays = title, subtitle, plays
        self._cover_url = cover_url
        self._pm = None
        self.update()

    def _on_cover_ready(self, seed: int) -> None:
        if seed == self._seed and self._cover_url:
            self._pm = None
            self.update()

    # ---- 尺寸 ----
    def resizeEvent(self, e) -> None:
        self.setFixedHeight(self.width() + self.TEXT_BLOCK)
        super().resizeEvent(e)

    def _cover(self) -> QPixmap:
        w = max(1, self.width())
        if self._pm is not None and self._pm_size == w:
            return self._pm

        dpr = max(1.0, self.devicePixelRatioF())
        px = int(w * dpr)
        pm: QPixmap | None = None
        if self._cover_url:
            master = covers().pixmap(self._seed, self._cover_url)
            if master is not None and not master.isNull():
                pm = crop_fill(master, px, px)
                if not self._round:
                    pm = rounded(pm, 6 * dpr)
        if pm is None:  # 空态：程序化月牙封面
            pm = cover_pixmap(self._seed, px, self._hue, radius=6 * dpr)
        pm.setDevicePixelRatio(dpr)
        self._pm = pm
        self._pm_size = w
        return pm

    # ---- 交互 ----
    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            w = self.width()
            if e.position().y() <= w:
                self.clicked.emit()
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.position().y() <= self.width():
            self.playClicked.emit()
        super().mouseDoubleClickEvent(e)

    # ---- 绘制 ----
    def paintEvent(self, _e) -> None:
        w = self.width()
        h = self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        cover = QRectF(0, 0, w, w)
        pm = self._cover()
        if self._round:
            path = QPainterPath()
            path.addEllipse(cover)
            p.setClipPath(path)
        p.drawPixmap(cover, pm, QRectF(pm.rect()))
        p.setClipping(False)

        # 悬停：压暗 + 主色播放按钮
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            if self._round:
                p.drawEllipse(cover)
            else:
                p.drawRoundedRect(cover, 6, 6)
            cx, cy = w / 2, w / 2
            p.setBrush(QColor(THEME["primary"]))
            p.drawEllipse(QPointF(cx, cy), 22, 22)
            ico = pixmap("fa5s.play", "#FFFFFF", 15)
            p.drawPixmap(QRectF(cx - 7.5, cy - 7.5, 15, 15), ico,
                         QRectF(ico.rect()))

        # 播放量胶囊
        if self._plays:
            f = font(10)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(self._plays)
            bw, bh = tw + 30, 19
            rect = QRectF(8, 8, bw, bh)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(10, 15, 28, 150))
            p.drawRoundedRect(rect, bh / 2, bh / 2)
            ico = pixmap("fa5s.headphones", "#E2E8F0", 10)
            p.drawPixmap(QRectF(rect.left() + 8, rect.top() + 5, 10, 10), ico,
                         QRectF(ico.rect()))
            p.setPen(QColor(226, 232, 240))
            p.drawText(QRectF(rect.left() + 21, rect.top(), tw + 4, bh),
                       int(Qt.AlignmentFlag.AlignVCenter),
                       self._plays)

        # 标题（两行截断）+ 副标题
        title_rect = QRectF(2, w + 8, w - 4, 38)
        draw_wrapped(p, title_rect, self._title, font(12, 500),
                     THEME["text_main"], max_lines=2, leading=3)
        if self._subtitle:
            p.setFont(font(10))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(QRectF(2, h - 17, w - 4, 16),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       p.fontMetrics().elidedText(self._subtitle,
                                                  Qt.TextElideMode.ElideRight,
                                                  int(w - 4)))


class ShadowBox(QWidget):
    """给固定尺寸的子控件包一圈柔光投影。

    坑点：QGraphicsDropShadowEffect 作用在子控件上时，如果父级控件已经挂了
    图形效果（本项目的窗口悬浮阴影），子级效果不会被渲染。所以这里改为
    “画一个圆角矩形 → 用 QGraphicsBlurEffect 离线模糊 → 当作阴影贴图” 的方案。
    """

    def __init__(self, child: QWidget, pad: int = 16, radius: float = 8,
                 offset: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._pad = pad
        self._radius = radius
        self._offset = offset
        self._child = child
        child.setParent(self)
        child.move(pad, pad)
        self.setFixedSize(child.width() + pad * 2, child.height() + pad * 2)
        self._shadow = self._make_shadow()

    def _make_shadow(self) -> QPixmap:
        from ..assets import blur_pixmap

        w, h = self._child.width(), self._child.height()
        pad = self._pad
        src = QPixmap(w + pad * 2, h + pad * 2)
        src.fill(Qt.GlobalColor.transparent)
        p = QPainter(src)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 255))
        p.drawRoundedRect(QRectF(pad, pad, w, h), self._radius, self._radius)
        p.end()
        return blur_pixmap(src, radius=pad * 1.15, downscale=0.5)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setOpacity(0.62)
        p.drawPixmap(QRectF(0, self._offset * 0.55, self.width(), self.height()),
                     self._shadow, QRectF(self._shadow.rect()))
