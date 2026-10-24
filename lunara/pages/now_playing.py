"""Lunara · 播放页（沉浸核心）

三种模式：
1) 唱片 + 歌词（默认）
2) 纯歌词（星空字幕）
3) 纯封面（星光粒子）

背景 = 当前封面高斯模糊（离线渲染） + 深空黑遮罩 + 上下渐深，
既保证文字可读，又保留封面的色彩氛围。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..assets import blurred_background
from ..core.player import Player
from ..data import LYRICS, Track
from ..theme import THEME, qcolor
from ..widgets.common import IconButton, font
from ..widgets.cover import CoverArt, ShadowBox
from ..widgets.lyrics import LyricView
from ..widgets.starfield import StarField
from ..widgets.vinyl import VinylDisc

MODE_NAMES = ("唱片 + 歌词", "纯歌词", "纯封面")


class NowPlayingPage(QWidget):
    backRequested = pyqtSignal()

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("NowPlayingRoot")
        self.player = player
        self._bg_key: tuple | None = None
        self._lyrics: list[tuple[int, str]] = list(LYRICS)

        # ---------------- 背景层 ----------------
        self._bg = QLabel(self)
        self._bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._bg.setScaledContents(False)
        self._bg.lower()

        self._bg_timer = QTimer(self)
        self._bg_timer.setSingleShot(True)
        self._bg_timer.setInterval(110)
        self._bg_timer.timeout.connect(self._apply_background)

        # ---------------- 布局 ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 16, 40, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        btn_back = IconButton("fa5s.chevron-down", THEME["text_sub"], 14, 30, "收起播放页")
        btn_back.clicked.connect(self.backRequested)
        top.addWidget(btn_back)

        cap = QLabel("正在播放")
        cap.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;"
                          f" letter-spacing: 2px;")
        top.addWidget(cap)
        top.addStretch(1)

        self._mode_group = QButtonGroup(self)
        self._mode_btns: list[QPushButton] = []
        for i, name in enumerate(MODE_NAMES):
            b = QPushButton(name)
            b.setObjectName("ModeBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setChecked(i == 0)
            self._mode_group.addButton(b, i)
            self._mode_btns.append(b)
            top.addWidget(b)
        self._mode_group.idClicked.connect(self.set_mode)
        root.addLayout(top)

        # ---------------- 模式堆栈 ----------------
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_vinyl_mode())
        self.stack.addWidget(self._build_lyric_mode())
        self.stack.addWidget(self._build_cover_mode())
        root.addWidget(self.stack, 1)

        # ---------------- 底部信息 ----------------
        foot = QHBoxLayout()
        foot.setContentsMargins(2, 0, 2, 0)
        foot.setSpacing(12)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        self.lbl_title = QLabel("—")
        self.lbl_title.setFont(font(22, 700))
        self.lbl_title.setStyleSheet(f"color: {THEME['text_main']};")
        self.lbl_artist = QLabel("")
        self.lbl_artist.setObjectName("BodyText")
        col.addWidget(self.lbl_title)
        col.addWidget(self.lbl_artist)
        foot.addLayout(col, 1)

        self.btn_like = IconButton("fa5s.star", THEME["text_sub"], 16, 34, "喜欢")
        self.btn_like.clicked.connect(self._toggle_like)
        foot.addWidget(self.btn_like)
        root.addLayout(foot)

        # ---------------- 连接 ----------------
        player.trackChanged.connect(self._on_track)
        player.positionChanged.connect(self._on_position)
        player.playingChanged.connect(self._on_playing)
        player.likeChanged.connect(lambda *_: self._sync_like())
        for lv in (self.lyric1, self.lyric2):
            lv.lineClicked.connect(player.seek)

        if player.current is not None:
            self._on_track(player.current)

    # ---------------- 构建 ----------------
    def _build_vinyl_mode(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(48)

        left = QWidget()
        left.setFixedWidth(400)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(10)
        lv.addStretch(1)
        self.vinyl = VinylDisc(320)
        lv.addWidget(self.vinyl, 0, Qt.AlignmentFlag.AlignHCenter)
        self.lbl_vinyl_hint = QLabel("20 秒 / 圈 · 匀速旋转")
        self.lbl_vinyl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vinyl_hint.setStyleSheet(
            f"color: {THEME['text_dim']}; font-size: 10px;")
        lv.addWidget(self.lbl_vinyl_hint)
        lv.addStretch(1)
        h.addWidget(left)

        self.lyric1 = LyricView()
        h.addWidget(self.lyric1, 1)
        return w

    def _build_lyric_mode(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch(1)
        self.lyric2 = LyricView()
        self.lyric2.setMinimumWidth(320)
        self.lyric2.setMaximumWidth(760)
        h.addWidget(self.lyric2, 4)
        h.addStretch(1)
        return w

    def _build_cover_mode(self) -> QWidget:
        w = StarField()
        self.cover_big = CoverArt(300, 10)
        w.attach(ShadowBox(self.cover_big, pad=26, radius=10, offset=16))
        return w

    # ---------------- 模式 ----------------
    def set_mode(self, index: int) -> None:
        index = max(0, min(index, self.stack.count() - 1))
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self._mode_btns):
            b.setChecked(i == index)
        if index == 0 and self.player.is_playing:
            self.vinyl.start()

    # ---------------- 歌词 ----------------
    def set_lyrics(self, lines: list[tuple[int, str]]) -> None:
        """注入真实歌词（LRC 解析结果）。

        空列表视为「没取到」，保留当前歌词（默认是演示歌词），避免切歌时闪成空白。
        """
        if not lines:
            return
        self._lyrics = list(lines)
        position = self.player.position
        for lv in (self.lyric1, self.lyric2):
            lv.set_lyrics(self._lyrics)
            lv.set_position(position)

    # ---------------- 槽 ----------------
    def _on_track(self, track: Track | None) -> None:
        if track is None:
            return
        self.lbl_title.setText(track.title)
        self.lbl_artist.setText(f"{track.artist} · {track.album}")
        self.vinyl.set_track(track.seed, track.hue, track.cover_url)
        self.cover_big.set_cover(track.seed, track.hue, track.cover_url)
        for lv in (self.lyric1, self.lyric2):
            lv.set_lyrics(self._lyrics)
            lv.set_position(0)
        self._sync_like()
        self._bg_key = None
        self._bg_timer.start()

    def _on_position(self, pos: int, _dur: int) -> None:
        self.lyric1.set_position(pos)
        self.lyric2.set_position(pos)

    def _on_playing(self, playing: bool) -> None:
        if playing:
            self.vinyl.start()
        else:
            self.vinyl.stop()

    def _sync_like(self) -> None:
        t = self.player.current
        liked = t is not None and self.player.is_liked(t.id)
        self.btn_like.set_color(THEME["primary"] if liked else THEME["text_sub"])

    def _toggle_like(self) -> None:
        if self.player.current is not None:
            self.player.toggle_like(self.player.current.id)

    # ---------------- 背景 ----------------
    def _apply_background(self) -> None:
        track = self.player.current
        if track is None:
            return
        w, h = max(1, self.width()), max(1, self.height())
        key = (track.id, w, h)
        if key == self._bg_key:
            return
        self._bg_key = key

        pm = blurred_background(track.seed, w, h, track.hue, radius=64)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(pm.rect(), qcolor("bg_main", 138))     # 跟随主题的遮罩 ≈ 0.54
        g = QLinearGradient(0, 0, 0, pm.height())
        g.setColorAt(0.0, qcolor("bg_main", 170))
        g.setColorAt(0.45, qcolor("bg_main", 30))
        g.setColorAt(1.0, qcolor("bg_main", 200))
        p.fillRect(pm.rect(), g)
        p.end()

        self._bg.setPixmap(pm)
        self._bg.setGeometry(-int(w * 0.09), -int(h * 0.09),
                             pm.width(), pm.height())
        self._bg.lower()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self._bg.pixmap() and not self._bg.pixmap().isNull():
            self._bg_key = None
            self._bg_timer.start()
