"""Lunara · 播放控制栏（固定 80px）"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.player import MODE_ICON, MODE_TEXT, Player
from ..data import Track
from ..theme import THEME
from .common import IconButton
from .icons import icon
from .seek_slider import SeekSlider
from .vinyl import VinylDisc


def mmss(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60:02d}:{s % 60:02d}"


class _ClickDisc(VinylDisc):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


#: 音质短标签（播放栏空间小）
QUALITY_LABEL = {
    "standard": "标准",
    "higher": "较高",
    "exhigh": "极高",
    "lossless": "无损",
    "hires": "Hi-Res",
    "jymaster": "母带",
}
QUALITY_ORDER = ("standard", "higher", "exhigh", "lossless", "hires", "jymaster")


class PlayerBar(QFrame):
    openNowPlaying = pyqtSignal()
    qualityChanged = pyqtSignal(str)      # 实时切音质
    queueClearRequested = pyqtSignal()
    queueRemoveRequested = pyqtSignal(int)
    queueCollectRequested = pyqtSignal()

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent)
        self.player = player
        self._queue_panel = None
        self.setObjectName("PlayerBar")
        self.setFixedHeight(80)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 8, 20, 8)
        lay.setSpacing(16)

        # ---------------- 左：唱片 + 曲目信息 ----------------
        left = QWidget()
        left.setFixedWidth(272)
        lh = QHBoxLayout(left)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.setSpacing(12)

        self.disc = _ClickDisc(48, compact=True)
        self.disc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disc.setToolTip("打开播放页")
        self.disc.clicked.connect(self.openNowPlaying)
        lh.addWidget(self.disc)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)
        self.lbl_title = QLabel("—")
        self.lbl_title.setObjectName("PlayerTitle")
        self.lbl_artist = QLabel("Lunara")
        self.lbl_artist.setObjectName("PlayerArtist")
        for w in (self.lbl_title, self.lbl_artist):
            w.setMinimumWidth(120)
        info.addStretch(1)
        info.addWidget(self.lbl_title)
        info.addWidget(self.lbl_artist)
        info.addStretch(1)
        lh.addLayout(info, 1)

        self.btn_like = IconButton("fa5s.star", THEME["text_sub"], 14, 30, "喜欢")
        self.btn_like.clicked.connect(self._toggle_like)
        lh.addWidget(self.btn_like)
        lay.addWidget(left)

        # ---------------- 中：传输 + 进度 ----------------
        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(2)

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(14)
        transport.addStretch(1)
        self.btn_prev = IconButton("fa5s.step-backward", THEME["text_main"], 15, 30,
                                   "上一首")
        self.btn_play = QPushButton()
        self.btn_play.setObjectName("PlayFab")
        self.btn_play.setFixedSize(38, 38)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_next = IconButton("fa5s.step-forward", THEME["text_main"], 15, 30,
                                   "下一首")
        self.btn_prev.clicked.connect(player.prev_track)
        self.btn_next.clicked.connect(player.next_track)
        self.btn_play.clicked.connect(player.toggle)
        transport.addWidget(self.btn_prev)
        transport.addWidget(self.btn_play)
        transport.addWidget(self.btn_next)
        transport.addStretch(1)
        cv.addLayout(transport)

        progress = QHBoxLayout()
        progress.setContentsMargins(0, 0, 0, 0)
        progress.setSpacing(10)
        self.lbl_cur = QLabel("00:00")
        self.lbl_cur.setObjectName("TimeLabel")
        self.lbl_cur.setFixedWidth(36)
        self.lbl_cur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.seek = SeekSlider()
        self.seek.setFixedHeight(16)
        self.lbl_dur = QLabel("00:00")
        self.lbl_dur.setObjectName("TimeLabel")
        self.lbl_dur.setFixedWidth(36)
        progress.addWidget(self.lbl_cur)
        progress.addWidget(self.seek, 1)
        progress.addWidget(self.lbl_dur)
        cv.addLayout(progress)
        lay.addWidget(center, 1)

        # ---------------- 右：模式 / 音量 / 队列 ----------------
        right = QWidget()
        right.setFixedWidth(272)
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(6)
        rh.addStretch(1)

        self.btn_quality = QPushButton(QUALITY_LABEL["exhigh"])
        self.btn_quality.setObjectName("QualityChip")
        self.btn_quality.setFixedHeight(24)
        self.btn_quality.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quality.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_quality.setToolTip("切换音质（立即生效）")
        self.btn_quality.clicked.connect(self._pick_quality)
        rh.addWidget(self.btn_quality)

        self.btn_mode = IconButton(MODE_ICON[player.mode], THEME["text_sub"], 14, 30,
                                   MODE_TEXT[player.mode])
        self.btn_mode.clicked.connect(player.cycle_mode)
        rh.addWidget(self.btn_mode)

        self.btn_volume = IconButton("fa5s.volume-up", THEME["text_sub"], 14, 30,
                                     "静音")
        self.btn_volume.clicked.connect(self._toggle_mute)
        rh.addWidget(self.btn_volume)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setObjectName("VolumeSlider")
        self.volume.setRange(0, 100)
        self.volume.setValue(player.volume)
        self.volume.setFixedWidth(88)
        self.volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume.valueChanged.connect(player.set_volume)
        rh.addWidget(self.volume)

        self.btn_queue = IconButton("fa5s.list-ul", THEME["text_sub"], 14, 30, "播放列表")
        self.btn_queue.clicked.connect(self._show_queue)
        rh.addWidget(self.btn_queue)
        lay.addWidget(right)

        # ---------------- 信号 ----------------
        player.trackChanged.connect(self._on_track)
        player.playingChanged.connect(self._on_playing)
        player.positionChanged.connect(self._on_position)
        player.modeChanged.connect(self._on_mode)
        player.likeChanged.connect(lambda *_: self._sync_like())
        self.seek.seekRequested.connect(self._on_seek)

        self._on_playing(False)
        if player.current is not None:
            self._on_track(player.current)

    # ---------------- 音质 ----------------
    def set_quality(self, value: str) -> None:
        self._quality = value
        self.btn_quality.setText(QUALITY_LABEL.get(value, "标准"))

    def _pick_quality(self) -> None:
        menu = QMenu(self)
        current = getattr(self, "_quality", "exhigh")
        for level in reversed(QUALITY_ORDER):
            label = QUALITY_LABEL[level]
            action = menu.addAction(("● " if level == current else "    ") + label)
            action.triggered.connect(
                lambda _=False, v=level: self.qualityChanged.emit(v))
        menu.exec(self.btn_quality.mapToGlobal(
            self.btn_quality.rect().bottomLeft()))

    # ---------------- 槽 ----------------
    def _on_track(self, track: Track | None) -> None:
        if track is None:
            return
        self.lbl_title.setText(track.title)
        self.lbl_artist.setText(track.artist)
        self.disc.set_track(track.seed, track.hue)
        self.lbl_dur.setText(track.duration_text)
        self.lbl_cur.setText("00:00")
        self.seek.setValue(0)
        self._sync_like()
        if self.player.is_playing:
            self.disc.start()

    def _on_playing(self, playing: bool) -> None:
        self.btn_play.setIcon(icon("fa5s.pause" if playing else "fa5s.play", "#FFFFFF"))
        self.btn_play.setIconSize(QSize(14, 14))
        if playing:
            self.disc.start()
        else:
            self.disc.stop()

    def _on_position(self, pos: int, dur: int) -> None:
        self.seek.set_progress(pos, dur)
        self.lbl_cur.setText(mmss(pos))
        self.lbl_dur.setText(mmss(dur))

    def _on_mode(self, mode: str) -> None:
        self.btn_mode.set_icon_name(MODE_ICON[mode])
        self.btn_mode.setToolTip(MODE_TEXT[mode])

    def _on_seek(self, value: int) -> None:
        track = self.player.current
        if track is None:
            return
        self.player.seek(int(self.player.duration_ms * value / self.seek.maximum()))

    def _sync_like(self) -> None:
        track = self.player.current
        liked = track is not None and self.player.is_liked(track.id)
        self.btn_like.set_color(THEME["primary"] if liked else THEME["text_sub"])
        self.btn_like.set_icon_name("fa5s.star" if liked else "fa5s.star")

    def _toggle_like(self) -> None:
        track = self.player.current
        if track is not None:
            self.player.toggle_like(track.id)

    def _toggle_mute(self) -> None:
        if self.player.volume > 0:
            self._last_volume = self.player.volume
            self.volume.setValue(0)
        else:
            self.volume.setValue(getattr(self, "_last_volume", 70))

    def _show_queue(self) -> None:
        if self._queue_panel is None:
            from .queue_panel import QueuePanel

            self._queue_panel = QueuePanel(self)
            self._queue_panel.rowActivated.connect(self._on_queue_row)
            self._queue_panel.rowRemoved.connect(self._on_queue_remove)
            self._queue_panel.clearRequested.connect(self._on_queue_clear)
            self._queue_panel.collectRequested.connect(self.queueCollectRequested)

        self._queue_panel.set_tracks(list(self.player.queue), self.player.index)
        self._queue_panel.popup_at(self.btn_queue)

    def _on_queue_row(self, index: int) -> None:
        queue = list(self.player.queue)
        if 0 <= index < len(queue):
            self.player.play_track(queue[index], queue)
        self._queue_panel.hide()

    def _on_queue_remove(self, index: int) -> None:
        self.queueRemoveRequested.emit(index)
        self._queue_panel.set_tracks(list(self.player.queue), self.player.index)

    def _on_queue_clear(self) -> None:
        self.queueClearRequested.emit()
        self._queue_panel.set_tracks([], -1)
