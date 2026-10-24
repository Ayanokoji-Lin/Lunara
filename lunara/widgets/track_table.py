"""Lunara · 歌曲列表（QTableView + 自绘 Delegate）

为什么用 QTableView 而不是 QTableWidget：
- Model/View 只渲染可见行，上千首歌也不卡；
- 行悬停、正在播放行的音波动画、文字颜色，都靠 delegate 精确控制，
  QSS 无法表达“某一行是播放行”这种数据驱动样式。
"""
from __future__ import annotations

import math

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QStyledItemDelegate, QTableView

from ..data import Track
from ..theme import THEME
from .common import font
from .icons import pixmap

PLAYING_ROLE = int(Qt.ItemDataRole.UserRole) + 1
TRACK_ROLE = int(Qt.ItemDataRole.UserRole) + 2


class TrackModel(QAbstractTableModel):
    HEADERS = ("#", "标题", "歌手", "专辑", "时长")

    def __init__(self, tracks: list[Track] | None = None, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = list(tracks or [])
        self._playing_id = -1

    # ---- 基本接口 ----
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tracks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tracks)):
            return None
        t = self._tracks[index.row()]
        c = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (str(index.row() + 1), t.title, t.artist, t.album,
                    t.duration_text)[c]
        if role == PLAYING_ROLE:
            return t.id == self._playing_id
        if role == TRACK_ROLE:
            return t
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (orientation == Qt.Orientation.Horizontal
                and role == Qt.ItemDataRole.DisplayRole
                and 0 <= section < len(self.HEADERS)):
            return self.HEADERS[section]
        return None

    # ---- 业务接口 ----
    def set_tracks(self, tracks: list[Track]) -> None:
        self.beginResetModel()
        self._tracks = list(tracks)
        self.endResetModel()

    def track_at(self, row: int) -> Track | None:
        return self._tracks[row] if 0 <= row < len(self._tracks) else None

    def set_playing(self, track_id: int) -> None:
        if track_id == self._playing_id:
            return
        self._playing_id = track_id
        if self._tracks:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self._tracks) - 1, 4))

    def playing_row(self) -> int:
        for i, t in enumerate(self._tracks):
            if t.id == self._playing_id:
                return i
        return -1


class TrackDelegate(QStyledItemDelegate):
    ROW_H = 44

    def __init__(self, view: QTableView):
        super().__init__(view)
        self.view = view
        self.hover_row = -1
        self.phase = 0.0

    def sizeHint(self, option, index) -> QSize:
        return QSize(0, self.ROW_H)

    def paint(self, p: QPainter, option, index: QModelIndex) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(option.rect)
        row, col = index.row(), index.column()
        playing = bool(index.data(PLAYING_ROLE))
        hover = row == self.hover_row

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        fm_pad = 8

        if col == 0:
            self._paint_index(p, r, text, playing, hover)
        elif col == 1:
            p.setFont(font(12, 500))
            p.setPen(QColor(THEME["primary"] if playing else THEME["text_main"]))
            elided = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight,
                                                int(r.width()) - fm_pad * 2)
            p.drawText(r.adjusted(fm_pad, 0, -fm_pad, 0),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       elided)
        elif col in (2, 3):
            p.setFont(font(11))
            p.setPen(QColor(THEME["text_sub"] if col == 2 else THEME["text_dim"]))
            elided = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight,
                                                int(r.width()) - fm_pad * 2)
            p.drawText(r.adjusted(fm_pad, 0, -fm_pad, 0),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       elided)
        else:
            p.setFont(font(11))
            p.setPen(QColor(THEME["text_dim"]))
            p.drawText(r.adjusted(0, 0, -fm_pad, 0),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       text)
        p.restore()

    def _paint_index(self, p: QPainter, r: QRectF, text: str,
                     playing: bool, hover: bool) -> None:
        if playing:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(THEME["primary"]))
            n, bw, gap = 4, 2.4, 3.0
            total = n * bw + (n - 1) * gap
            x0 = r.center().x() - total / 2
            for i in range(n):
                k = abs(math.sin(self.phase + i * 0.9))
                bh = 4.0 + 12.0 * k
                p.drawRoundedRect(
                    QRectF(x0 + i * (bw + gap), r.center().y() - bh / 2, bw, bh),
                    1.2, 1.2)
            return
        if hover:
            ico = pixmap("fa5s.play", THEME["text_main"], 10)
            p.drawPixmap(QRectF(r.center().x() - 5, r.center().y() - 5, 10, 10),
                         ico, QRectF(ico.rect()))
            return
        p.setFont(font(11))
        p.setPen(QColor(THEME["text_dim"]))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), text)


class TrackTable(QTableView):
    trackActivated = pyqtSignal(object)     # Track
    playNextRequested = pyqtSignal(object)  # 下一首播放
    queueAppendRequested = pyqtSignal(object)  # 加到队列末尾

    def __init__(self, tracks: list[Track] | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("TrackTable")
        self._model = TrackModel(tracks, self)
        self.setModel(self._model)
        self._delegate = TrackDelegate(self)
        self.setItemDelegate(self._delegate)

        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setFrameShape(QTableView.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlternatingRowColors(False)

        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(TrackDelegate.ROW_H)
        vh.setMinimumSectionSize(TrackDelegate.ROW_H)

        hh = self.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setFixedHeight(34)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(0, 52)
        hh.resizeSection(2, 168)
        hh.resizeSection(3, 190)
        hh.resizeSection(4, 64)

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_clicked)

        self._timer = QTimer(self)
        self._timer.setInterval(110)
        self._timer.timeout.connect(self._tick)
        self._sync_height()

    # ---- 数据 ----
    def set_tracks(self, tracks: list[Track]) -> None:
        self._model.set_tracks(tracks)

    def contextMenuEvent(self, event) -> None:
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        track = self._model.track_at(index.row())
        if track is None:
            return

        menu = QMenu(self)
        act_next = menu.addAction("下一首播放")
        act_queue = menu.addAction("加到队列末尾")
        chosen = menu.exec(event.globalPos())
        if chosen is act_next:
            self.playNextRequested.emit(track)
        elif chosen is act_queue:
            self.queueAppendRequested.emit(track)
        self._sync_height()

    def set_playing(self, track: Track | None) -> None:
        self._model.set_playing(track.id if track else -1)
        if self._model.playing_row() >= 0:
            self._timer.start()
        else:
            self._timer.stop()

    def _sync_height(self) -> None:
        rows = self._model.rowCount()
        self.setFixedHeight(rows * TrackDelegate.ROW_H + 40)

    # ---- 整行背景（在 item 绘制之前铺底，避免逐格圆角出现接缝）----
    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_row_backgrounds(painter)
        painter.end()
        super().paintEvent(event)

    def _paint_row_backgrounds(self, p: QPainter) -> None:
        width = self.viewport().width()
        for row in range(self._model.rowCount()):
            rect = self.visualRect(self._model.index(row, 0))
            if not rect.isValid() or rect.isEmpty():
                continue
            playing = bool(self._model.data(self._model.index(row, 0), PLAYING_ROLE))
            hover = row == self._delegate.hover_row
            if not playing and not hover:
                continue
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(139, 92, 246, 30) if playing
                       else QColor(51, 65, 85, 105))
            p.drawRoundedRect(
                QRectF(1, rect.top() + 1.5, width - 2, rect.height() - 3), 6, 6)

    # ---- 交互 ----
    def _on_clicked(self, index: QModelIndex) -> None:
        t = self._model.track_at(index.row())
        if t is not None:
            self.trackActivated.emit(t)

    def mouseMoveEvent(self, e) -> None:
        idx = self.indexAt(e.position().toPoint())
        row = idx.row() if idx.isValid() else -1
        if row != self._delegate.hover_row:
            self._delegate.hover_row = row
            self.viewport().update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if row >= 0
                       else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e) -> None:
        if self._delegate.hover_row != -1:
            self._delegate.hover_row = -1
            self.viewport().update()
        super().leaveEvent(e)

    def _tick(self) -> None:
        row = self._model.playing_row()
        if row < 0:
            self._timer.stop()
            return
        self._delegate.phase = (self._delegate.phase + 0.5) % (math.pi * 2)
        rect = self.visualRect(self._model.index(row, 0))
        self.viewport().update(rect)
