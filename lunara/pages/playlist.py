"""Lunara · 歌单详情页"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.player import Player
from ..data import PLAYLISTS, Playlist, Track
from ..theme import THEME
from ..widgets.common import Chip, SectionHeader, font
from ..widgets.cover import CoverArt, ShadowBox
from ..widgets.icons import icon
from ..widgets.track_table import TrackTable
from .base import BasePage


class PlaylistPage(BasePage):
    downloadRequested = pyqtSignal(object)      # list[Track]

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.player = player
        self._playlist: Playlist = PLAYLISTS[0]

        # ---------------- 顶部信息区 ----------------
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 4, 0, 0)
        hl.setSpacing(28)

        self.cover = CoverArt(180, 8)
        self.cover_box = ShadowBox(self.cover, pad=16, radius=8, offset=10)
        hl.addWidget(self.cover_box, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 2, 0, 2)
        info.setSpacing(9)

        self.chip = Chip("每日推荐")
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.addWidget(self.chip)
        chip_row.addStretch(1)
        info.addLayout(chip_row)

        self.lbl_title = QLabel()
        self.lbl_title.setFont(font(28, 700))
        self.lbl_title.setStyleSheet(f"color: {THEME['text_main']};")
        self.lbl_title.setWordWrap(True)
        info.addWidget(self.lbl_title)

        self.lbl_meta = QLabel()
        self.lbl_meta.setObjectName("BodyText")
        info.addWidget(self.lbl_meta)

        self.lbl_desc = QLabel()
        self.lbl_desc.setObjectName("MetaText")
        self.lbl_desc.setWordWrap(True)
        info.addWidget(self.lbl_desc)

        info.addSpacing(4)
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(10)

        self.btn_play = QPushButton("  播放全部")
        self.btn_play.setObjectName("PrimaryPill")
        self.btn_play.setIcon(icon("fa5s.play", "#FFFFFF"))
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.clicked.connect(self._play_all)

        self.btn_fav = QPushButton("  收藏")
        self.btn_fav.setObjectName("GhostPill")
        self.btn_fav.setCheckable(True)
        self.btn_fav.setIcon(icon("fa5s.star", THEME["text_main"]))
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_dl = QPushButton("  下载")
        self.btn_dl.setObjectName("GhostPill")
        self.btn_dl.setIcon(icon("fa5s.download", THEME["text_main"]))
        self.btn_dl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dl.clicked.connect(
            lambda: self.downloadRequested.emit(list(self._tracks)))

        btns.addWidget(self.btn_play)
        btns.addWidget(self.btn_fav)
        btns.addWidget(self.btn_dl)
        btns.addStretch(1)
        info.addLayout(btns)
        hl.addLayout(info, 1)
        self.body.addWidget(header)

        # ---------------- 歌曲列表 ----------------
        panel = QFrame()
        panel.setObjectName("Panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 14)
        pl.setSpacing(8)
        self.lbl_list = SectionHeader("歌曲列表", "共 0 首")
        pl.addWidget(self.lbl_list)
        self.table = TrackTable()
        pl.addWidget(self.table)
        self.body.addWidget(panel)
        self.body.addStretch(1)

        self.table.trackActivated.connect(self._play_track)
        self.player.trackChanged.connect(self.table.set_playing)

        self.set_playlist(PLAYLISTS[0])

    # ---------------- 数据 ----------------
    def set_playlist(self, playlist: Playlist,
                     tracks: list[Track] | None = None,
                     title: str | None = None) -> None:
        self._playlist = playlist
        self._tracks = list(tracks if tracks is not None else playlist.tracks)
        self.cover.set_cover(playlist.id, playlist.hue, playlist.cover_url)
        self.chip.setText(playlist.tag or "歌单")
        self.lbl_title.setText(title or playlist.title)
        self.lbl_meta.setText(
            f"由 {playlist.author} 创建 · {len(self._tracks)} 首 · "
            f"播放 {playlist.plays_text}")
        self.lbl_desc.setText(playlist.desc)
        self.lbl_list.title.setText("歌曲列表")
        self.lbl_list.hint.setText(f"共 {len(self._tracks)} 首")
        self.table.set_tracks(self._tracks)
        self.table.set_playing(self.player.current)

    def _play_all(self) -> None:
        if self._tracks:
            self.player.set_queue(self._tracks, 0, autoplay=True)

    def _play_track(self, track: Track) -> None:
        self.player.play_track(track, self._tracks)
