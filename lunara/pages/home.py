"""Lunara · 首页 / 发现页

数据来源：``services.catalog`` 把接口结果转成 ``Playlist`` / ``Track`` 后，
由 ``MainWindow`` 通过 ``set_playlists()`` / ``set_new_songs()`` 注入。
没注入时用 ``data.py`` 的演示数据兜底，所以断网也不会白屏。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.player import Player
from ..data import BANNERS, PLAYLISTS, TRACKS, Playlist, Track
from ..widgets.banner import BannerCarousel
from ..widgets.common import SectionHeader
from ..widgets.anim import detach, stagger
from ..widgets.cover import CoverCard
from .base import BasePage


def _clear(layout: QVBoxLayout) -> None:
    """清空容器里的旧网格（连子控件一起 deleteLater）。"""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # 卡片可能还在淡入，先停动画摘 effect，再销毁（否则 Qt 段错误）
            for child in widget.findChildren(QWidget):
                detach(child)
            detach(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


class HomePage(BasePage):
    playlistActivated = pyqtSignal(int)     # playlist id

    COLS = 5

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.player = player
        self.body.setSpacing(26)

        self._playlists: list[Playlist] = list(PLAYLISTS)
        self._new_songs: list[Track] = list(TRACKS[: self.COLS])

        # ---------- 问候 ----------
        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(6)
        title = QLabel("月海拾音")
        title.setObjectName("PageTitle")
        sub = QLabel("晚上好，蝶恋。今晚的月亮很薄，适合听点安静的。")
        sub.setObjectName("BodyText")
        col.addWidget(title)
        col.addWidget(sub)
        hl.addLayout(col)
        hl.addStretch(1)
        self.body.addWidget(head)

        # ---------- Banner ----------
        self.banner = BannerCarousel(BANNERS)
        self.banner.clicked.connect(self._on_banner)
        self.body.addWidget(self.banner)

        # ---------- 推荐歌单 ----------
        self.hdr_playlists = SectionHeader("推荐歌单", "根据你的星轨生成", "更多")
        self.body.addWidget(self.hdr_playlists)

        self._pl_host = QWidget()
        self._pl_layout = QVBoxLayout(self._pl_host)
        self._pl_layout.setContentsMargins(0, 0, 0, 0)
        self._pl_layout.setSpacing(0)
        self.body.addWidget(self._pl_host)

        # ---------- 新歌速递 ----------
        self.hdr_news = SectionHeader("新歌速递", "本周新增", "更多")
        self.body.addWidget(self.hdr_news)

        self._song_host = QWidget()
        self._song_layout = QVBoxLayout(self._song_host)
        self._song_layout.setContentsMargins(0, 0, 0, 0)
        self._song_layout.setSpacing(0)
        self.body.addWidget(self._song_host)

        self.body.addStretch(1)

        self._rebuild_playlists()
        self._rebuild_songs()

    # ---------------- 数据注入 ----------------
    def set_playlists(self, playlists: list[Playlist]) -> None:
        """换成真实推荐歌单。空列表视为「没拿到」，保留当前内容。"""
        if not playlists:
            return
        self._playlists = list(playlists)
        self._rebuild_playlists()

    def set_new_songs(self, tracks: list[Track]) -> None:
        """换成真实新歌。空列表同上。"""
        if not tracks:
            return
        self._new_songs = list(tracks)
        self.hdr_news.hint.setText(f"本周新增 {len(self._new_songs)} 首")
        self._rebuild_songs()

    # ---------------- 视图 ----------------
    def _rebuild_playlists(self) -> None:
        _clear(self._pl_layout)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(26)
        for c in range(self.COLS):
            grid.setColumnStretch(c, 1)

        cards: list[CoverCard] = []
        for i, pl in enumerate(self._playlists):
            card = CoverCard(pl.id, pl.hue, pl.title, pl.author, pl.plays_text,
                             cover_url=pl.cover_url)
            card.clicked.connect(lambda pid=pl.id: self.playlistActivated.emit(pid))
            card.playClicked.connect(lambda pid=pl.id: self.playlistActivated.emit(pid))
            grid.addWidget(card, i // self.COLS, i % self.COLS)
            cards.append(card)

        wrap = QWidget()
        wrap.setLayout(grid)
        self._pl_layout.addWidget(wrap)
        stagger(cards, step=16, duration=220, limit=20)

    def _rebuild_songs(self) -> None:
        _clear(self._song_layout)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(26)
        for c in range(self.COLS):
            grid.setColumnStretch(c, 1)

        queue = list(self._new_songs)
        cards: list[CoverCard] = []
        for i, track in enumerate(queue[: self.COLS]):
            card = CoverCard(track.seed, track.hue, track.title, track.artist, "",
                             cover_url=track.cover_url)
            card.clicked.connect(lambda tr=track: self.player.play_track(tr, queue))
            card.playClicked.connect(lambda tr=track: self.player.play_track(tr, queue))
            grid.addWidget(card, 0, i)
            cards.append(card)

        wrap = QWidget()
        wrap.setLayout(grid)
        self._song_layout.addWidget(wrap)
        stagger(cards, step=16, duration=220, limit=20)

    def _on_banner(self, index: int) -> None:
        if 0 <= index < len(self._playlists):
            self.playlistActivated.emit(self._playlists[index].id)
