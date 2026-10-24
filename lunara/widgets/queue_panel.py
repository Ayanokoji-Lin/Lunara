"""播放列表面板（参照网易云 PC 端布局）。

结构：标题行（播放列表 + 曲目数 + 收藏全部 / 清空）+ 可滚动列表。
每行：封面缩略图、标题（过长省略）、歌手、时长；正在播的那行高亮并带播放标记。
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..data import Track
from ..services.covers import covers
from ..theme import THEME
from .common import font
from .icons import pixmap

ROW_H = 56
COVER = 40


class _Cover(QWidget):
    """行内小封面：有图用图，没有就用月牙占位。"""

    def __init__(self, track: Track, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track = track
        self.setFixedSize(COVER, COVER)
        covers().ready.connect(self._on_ready)

    def _on_ready(self, seed: int) -> None:
        if seed == self._track.seed:
            self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(0, 0, COVER, COVER)

        image = covers().pixmap(self._track.seed, self._track.cover_url) \
            if self._track.cover_url else None
        if image is not None and not image.isNull():
            scaled = image.scaled(COVER, COVER, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
            painter.setClipRect(rect)
            painter.drawPixmap(rect, scaled, QRectF(scaled.rect()))
            painter.setClipping(False)
        else:
            covers().request(self._track.seed, self._track.cover_url)
            from ..assets import cover_pixmap

            painter.drawPixmap(rect, cover_pixmap(self._track.seed, COVER,
                                                  self._track.hue, radius=6),
                               QRectF(0, 0, COVER, COVER))


class QueueRow(QWidget):
    activated = pyqtSignal(int)
    removeRequested = pyqtSignal(int)

    def __init__(self, index: int, track: Track, playing: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._playing = playing
        self._hover = False
        self.setFixedHeight(ROW_H)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(12)

        self.cover = _Cover(track)
        lay.addWidget(self.cover)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)

        self.lbl_title = QLabel()
        self.lbl_title.setFont(font(13, 600 if playing else 400))
        self.lbl_title.setStyleSheet(
            f"color: {THEME['primary'] if playing else THEME['text_main']};")
        text.addWidget(self.lbl_title)

        self.lbl_artist = QLabel(track.artist)
        self.lbl_artist.setFont(font(11))
        self.lbl_artist.setStyleSheet(f"color: {THEME['text_dim']};")
        text.addWidget(self.lbl_artist)
        lay.addLayout(text, 1)

        self.lbl_time = QLabel(track.duration_text)
        self.lbl_time.setFont(font(11))
        self.lbl_time.setStyleSheet(f"color: {THEME['text_dim']};")
        lay.addWidget(self.lbl_time)

        self.btn_remove = QPushButton()
        self.btn_remove.setObjectName("QueueRemove")
        self.btn_remove.setFixedSize(22, 22)
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setIcon(QIcon(pixmap("fa5s.times", THEME["text_dim"], 11)))
        self.btn_remove.setToolTip("从播放列表移除")
        self.btn_remove.clicked.connect(lambda: self.removeRequested.emit(self._index))
        self.btn_remove.hide()
        lay.addWidget(self.btn_remove)

        self._elide(track.title)

    def _elide(self, text: str) -> None:
        width = max(80, self.width() - COVER - 130)
        metrics = QFontMetrics(self.lbl_title.font())
        self.lbl_title.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, width))
        self.lbl_title.setToolTip(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide(self.lbl_title.toolTip())

    def enterEvent(self, event) -> None:
        self._hover = True
        self.btn_remove.show()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.btn_remove.hide()
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self._index)
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 16))
            painter.drawRoundedRect(self.rect().adjusted(6, 2, -6, -2), 8, 8)


class QueuePanel(QFrame):
    """从播放栏「播放列表」按钮弹出的面板。"""

    clearRequested = pyqtSignal()
    collectRequested = pyqtSignal()
    rowActivated = pyqtSignal(int)
    rowRemoved = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("QueuePanel")
        self.setFixedWidth(400)
        self.setMaximumHeight(560)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(0)

        head = QWidget()
        head.setObjectName("QueueHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 14, 12, 10)
        hl.setSpacing(8)

        title = QLabel("播放列表")
        title.setFont(font(14, 600))
        title.setStyleSheet(f"color: {THEME['text_main']};")
        hl.addWidget(title)
        self.lbl_count = QLabel("0")
        self.lbl_count.setFont(font(11))
        self.lbl_count.setStyleSheet(f"color: {THEME['text_dim']};")
        hl.addWidget(self.lbl_count)
        hl.addStretch(1)

        self.btn_collect = QPushButton("  收藏全部")
        self.btn_collect.setObjectName("QueueAction")
        self.btn_collect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collect.setIcon(QIcon(pixmap("fa5s.plus", THEME["text_sub"], 11)))
        self.btn_collect.clicked.connect(self.collectRequested)
        hl.addWidget(self.btn_collect)

        self.btn_clear = QPushButton("  清空")
        self.btn_clear.setObjectName("QueueAction")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setIcon(QIcon(pixmap("fa5s.trash-alt", THEME["text_sub"], 11)))
        self.btn_clear.clicked.connect(self.clearRequested)
        hl.addWidget(self.btn_clear)
        root.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("PageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        self.scroll.setWidget(self._body)
        root.addWidget(self.scroll, 1)

        self._rows: list[QueueRow] = []

    # ------------------------------------------------------------------ #
    def set_tracks(self, tracks: list[Track], current: int) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        self.lbl_count.setText(str(len(tracks)))
        self.btn_collect.setEnabled(bool(tracks))
        self.btn_clear.setEnabled(bool(tracks))

        if not tracks:
            empty = QLabel("播放列表是空的")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(font(12))
            empty.setStyleSheet(f"color: {THEME['text_dim']};")
            empty.setFixedHeight(120)
            self._layout.insertWidget(0, empty)
            self._rows = []
            return

        for i, track in enumerate(tracks):
            row = QueueRow(i, track, i == current)
            row.activated.connect(self.rowActivated)
            row.removeRequested.connect(self.rowRemoved)
            self._layout.insertWidget(i, row)
            self._rows.append(row)

        if 0 <= current < len(self._rows):
            self.scroll.ensureWidgetVisible(self._rows[current], 0, 120)

    def popup_at(self, anchor: QWidget) -> None:
        """在按钮上方弹出（空间不够时往下）。"""
        self.adjustSize()
        point = anchor.mapToGlobal(anchor.rect().topLeft())
        height = min(self.height(), self.maximumHeight())
        self.setFixedHeight(height)
        self.move(point.x() - self.width() + anchor.width(),
                  point.y() - height - 8)
        self.show()
