"""Lunara · 主窗口（无边框 + 悬浮阴影 + 四大模块装配）"""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

import httpx

from PyQt6.QtCore import QFile, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QSizeGrip,
    QSystemTrayIcon,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .api import aclose_client, get_client
from .api.core import logging as api_log
from .api.modules.album import get_album
from .api.modules.dj import get_recommend_programs
from .api.modules.song import like_song
from .api.modules.artist import get_artist, get_artist_albums
from .api.modules.lyric import get_lyric
from .api.modules.personalized import get_new_songs, get_recommended_playlists
from .api.modules.playlist import get_playlist_detail
from .api.modules.user import get_user_playlists
from .api.modules.search import (
    SearchKind,
    search_albums,
    search_artists,
    search_playlists,
    search_songs,
)
from .core.player import Player
from .data import (PLAYLISTS, TRACKS, DownloadTask, Playlist, Track,
                   demo_playlist, is_demo_playlist)
from .pages.grid import GridPage
from .widgets.anim import fade_in
from .pages.download import DownloadPage
from .pages.home import HomePage
from .pages.now_playing import NowPlayingPage
from .pages.playlist import PlaylistPage
from .pages.search import SearchPage
from .pages.settings import SettingsPage
from .services.account import AccountStore, apply_cookies, forget_cookies
from .services.async_bridge import run_sync, shutdown as shutdown_bridge
from .services.covers import covers
from .services.download.service import DownloadService
from .services.error_text import error_text
from .services.download.store import DownloadStore
from .services.player_url.service import PlayerUrlService
from .services.player_url.types import ResolveOutcome
from .services.local_library import scan
from .services import queue_store
from .services.recent import RecentStore
from .services.settings_store import SettingsStore
from .services.catalog import (
    hue_for,
    CardItem,
    SearchPayload,
    split_user_playlists,
    to_card_from_track,
    to_playlist_from_album,
    to_playlist_from_artist,
    to_program_track,
    to_card_from_track,
    to_playlist_from_album,
    to_playlist_from_artist,
    to_program_track,
    to_album_card,
    to_artist_card,
    to_playlist,
    to_playlist_card,
    to_playlist_hit,
    to_track_from_newsong,
    to_track_list,
)
from .services.lyrics import parse_lyric_with_translation
from .services.qt_bridge import QtAsyncBridge
from .services.session import SessionService, SessionState
from .widgets.notice import InlineBanner
from .widgets.player_bar import PlayerBar
from .widgets.sidebar import Sidebar
from .widgets.topbar import TopBar

SHADOW_MARGIN = 18

# 页面索引
P_HOME, P_PLAYLIST, P_SEARCH, P_SETTINGS, P_NOW, P_DOWNLOAD, P_GRID = range(7)

#: 单曲搜索每页条数（「加载更多」按这个步进）
SEARCH_PAGE_SIZE = 30

class MainWindow(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Lunara")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(1056, 752)
        self.resize(1280, 820)

        self.player = Player(self)
        self.player.set_queue(TRACKS, 0, autoplay=False)

        # ---------------- 外层：留出阴影空间 ----------------
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN,
                                       SHADOW_MARGIN, SHADOW_MARGIN)
        self._outer.setSpacing(0)

        self.root = QWidget()
        self.root.setObjectName("WindowRoot")
        self.root.setProperty("windowState", "normal")
        self._shadow = QGraphicsDropShadowEffect(self.root)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 8)
        self._shadow.setColor(QColor(0, 0, 0, 100))
        self.root.setGraphicsEffect(self._shadow)
        self._outer.addWidget(self.root)

        # ---------------- 四大模块 ----------------
        rl = QVBoxLayout(self.root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar()
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.topbar = TopBar()
        content = QWidget()
        content.setObjectName("ContentArea")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.banner = InlineBanner()
        cl.addWidget(self.banner)
        self.stack = QStackedWidget()
        cl.addWidget(self.stack)

        rv.addWidget(self.topbar)
        rv.addWidget(content, 1)
        body.addWidget(self.sidebar)
        body.addWidget(right, 1)
        rl.addLayout(body, 1)

        self.player_bar = PlayerBar(self.player)
        rl.addWidget(self.player_bar)

        # ---------------- 服务（页面要用，先于页面创建） ----------------
        self._settings = SettingsStore()
        self._session = SessionService(get_client())
        self._url_service = PlayerUrlService(get_client(), self._session)
        self._download_store = DownloadStore()
        self._downloads = DownloadService(
            self._url_service,
            self._download_store,
            download_dir=lambda: self._settings.download_dir,
            concurrency=self._settings.max_concurrent_downloads,
        )

        # ---------------- 页面注册 ----------------
        self.home = HomePage(self.player)
        self.playlist_page = PlaylistPage(self.player)
        self.search_page = SearchPage(self.player)
        self.settings_page = SettingsPage(self._settings)
        self.now_playing = NowPlayingPage(self.player)
        self.grid_page = GridPage()
        self.download_page = DownloadPage(self.player, self._downloads, self._settings)
        for page in (self.home, self.playlist_page, self.search_page,
                     self.settings_page, self.now_playing,
                     self.download_page, self.grid_page):
            self.stack.addWidget(page)

        self._history: list[int] = [P_HOME]
        self._hpos = 0

        # ---------------- 交互连接 ----------------
        self.sidebar.navigate.connect(self.navigate)
        self.home.playlistActivated.connect(self.open_playlist)
        # 网格页（播客 / 新歌速递 / 更多歌单 / 歌手专辑）的点击统一走这里
        self.grid_page.cardActivated.connect(self._on_grid_card)
        self.home.hdr_playlists.moreClicked.connect(self._open_more_playlists)
        self.home.hdr_news.moreClicked.connect(self._open_more_songs)

        # 歌单页：头部「全部专辑 / 歌手」按钮、下载按钮、表格右键三项
        self.playlist_page.actionRequested.connect(self._on_page_action)
        self.playlist_page.downloadRequested.connect(self._enqueue_downloads)
        self.playlist_page.deleteLocalRequested.connect(self._delete_local_files)
        self.download_page.taskDeleted.connect(self._on_task_deleted)
        for table in (self.playlist_page.table, self.search_page.table):
            table.playNextRequested.connect(self._on_play_next)
            table.queueAppendRequested.connect(self._on_queue_append)
            table.likeManyRequested.connect(self._on_like_many)
        self.topbar.searchSubmitted.connect(self._on_search)
        self.topbar.searchChanged.connect(self._on_search_live)
        self.topbar.btn_cog.clicked.connect(lambda: self.navigate("settings"))
        self.topbar.accountClicked.connect(lambda: self.navigate("settings"))
        self.topbar.notifyClicked.connect(
            lambda: self.banner.show_message("暂时没有新通知", level="info", timeout_ms=3000))
        self.topbar.accountClicked.connect(lambda: self.navigate("settings"))
        self.topbar.notifyClicked.connect(
            lambda: self.banner.show_message("暂时没有新通知", level="info", timeout_ms=3000))
        self.topbar.minimizeRequested.connect(self.showMinimized)
        self.topbar.maximizeRequested.connect(self.toggle_maximize)
        self.topbar.closeRequested.connect(self.close)
        self.topbar.backClicked.connect(self.go_back)
        self.topbar.forwardClicked.connect(self.go_forward)
        self.player_bar.openNowPlaying.connect(self.open_now_playing)
        self.player.urlRequested.connect(self._on_url_requested)
        self.player.errorOccurred.connect(self._on_player_error)
        self.player.trialModeChanged.connect(self._on_trial_changed)
        self.player.likeChanged.connect(self._on_like_changed)
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.positionChanged.connect(self._remember_position)
        self.player.set_fade(bool(self._settings.get("fade", True)))

        # 音量 / 倍速 / 队列的恢复放到事件循环第一帧：
        # 直接在这里 set_queue 会立刻发 trackChanged，而那时 _recent 还没建好，
        # 槽里抛 AttributeError 会被 PyQt6 当成致命错误直接结束进程。
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._on_sleep_timeout)
        self.player.volumeChanged.connect(self._remember_volume)
        QTimer.singleShot(0, self._restore_session)
        self.search_page.set_history(list(self._settings.get("search_history") or []))
        QTimer.singleShot(1500, self._import_existing_files)

        self._close_to_tray = bool(self._settings.get("close_to_tray", True))
        self._tray_hinted = False
        self._tray = QSystemTrayIcon(
            QIcon(str(Path(__file__).resolve().parent.parent / "assets" / "icon.ico")), self)
        self._tray.setToolTip("Lunara")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.setContextMenu(self._build_tray_menu())
        self._tray.show()
        self._restore_geometry()

        self._apply_download_limits()

        self._settings.changed.connect(self._on_setting_changed)
        self.now_playing.set_mode(int(self._settings.get("player_view", 0)))
        self.now_playing.backRequested.connect(self.go_back)

        # 窗口缩放（无边框窗口需要自己挂 QSizeGrip）
        self.grip = QSizeGrip(self.root)
        self.grip.setFixedSize(18, 18)
        self.grip.setStyleSheet("background: transparent;")

        self._install_shortcuts()

        # ---------------- 异步桥 + 首屏数据 ----------------
        self._bridge = QtAsyncBridge(self)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(320)
        self._search_timer.timeout.connect(self._request_search)
        self.search_page.resultsRequested.connect(self._request_search_for_tab)
        self.search_page.playlistActivated.connect(self.open_playlist)
        self.search_page.artistActivated.connect(self.open_artist)
        self.search_page.albumActivated.connect(self.open_album)
        self.search_page.moreRequested.connect(self._load_more)
        self.search_page.suggestRequested.connect(self._on_search)
        self.search_page.artistActivated.connect(self.open_artist)
        self.search_page.albumActivated.connect(self.open_album)
        self.search_page.moreRequested.connect(self._load_more)
        self.player.trackChanged.connect(self._load_lyric)
        self.settings_page.loginRequested.connect(self._on_login_requested)
        self.settings_page.logoutRequested.connect(self._on_logout_requested)
        self.settings_page.themeChanged.connect(self._on_theme_changed)

        self._account = AccountStore()
        self._session: SessionService | None = None
        self._liked_id: int | None = None
        self._home_retried = False
        self._recommended: list[Playlist] = []
        self._grid_mode = ""
        self._podcast_tracks: list[Track] = []
        self._more_tracks: list[Track] = []
        self._recent = RecentStore()
        self._current_artist_id = 0
        self._liked_ids: set[int] = set()
        self._logged_in = False
        self._album_artist_id = 0
        self._resume: dict[str, int] = dict(self._settings.get("resume_positions") or {})
        self._resume_dirty = False
        self._resume: dict[str, int] = dict(self._settings.get("resume_positions") or {})
        self._resume_dirty = False
        self._rolling_back_like = False
        self._search_offsets: dict[tuple[str, int], int] = {}
        self._restore_login()

        QTimer.singleShot(0, self._downloads.start)
        QTimer.singleShot(0, self._load_home)
        QTimer.singleShot(0, self._refresh_account)

    # ================= 导航 =================
    def _show(self, index: int, record: bool = True) -> None:
        changed = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index)
        if changed:
            page = self.stack.currentWidget()
            if page is not None:
                # 从 45% 淡入：整页从黑里浮出来，比硬切干净；160ms 结束即摘 effect
                fade_in(page, duration=160, start=0.45)
        if not record:
            return
        if self._hpos < len(self._history) - 1:
            self._history = self._history[: self._hpos + 1]
        if not self._history or self._history[-1] != index:
            self._history.append(index)
        self._hpos = len(self._history) - 1

    def navigate(self, key: str) -> None:
        if key == "home":
            self._show(P_HOME)
        elif key == "settings":
            self._show(P_SETTINGS)
        elif key.startswith("playlist:"):
            try:
                idx = int(key.split(":")[1])
            except (IndexError, ValueError):
                idx = 0
            self.open_playlist(PLAYLISTS[idx % len(PLAYLISTS)].id)
        elif key.startswith("myplaylist:"):
            try:
                pid = int(key.split(":", 1)[1])
            except (IndexError, ValueError):
                return
            self.open_playlist(pid)
        elif key == "liked":
            if self._liked_id:
                self.open_playlist(self._liked_id)   # 真实「我喜欢的音乐」就是个歌单
                return
            pl = Playlist(0, "我喜欢的音乐", "蝶恋", 128_000, 268, "我喜欢的")
            self.playlist_page.set_playlist(pl, TRACKS[:8], title="我喜欢的音乐")
            self._show(P_PLAYLIST)
        elif key == "recent":
            self._open_recent()
        elif key == "local":
            self._show(P_DOWNLOAD)
        elif key == "library":
            self._open_library()
        elif key == "podcast":
            self._open_podcast()
        elif key == "roam":
            self._start_roam()

    def open_playlist(self, pid: int) -> None:
        """打开歌单：先切页（保留上一屏内容），再异步换成真实数据。

        演示歌单（101 起）只存在于本地，直接渲染、不发请求——否则会拿一个
        不存在的 id 去查详情，得到一个解析失败和一条没必要的错误提示。
        """
        if is_demo_playlist(pid):
            demo = demo_playlist(pid)
            if demo is not None:
                self.playlist_page.set_playlist(demo, list(demo.tracks), title=demo.title)
            self._show(P_PLAYLIST)
            return

        self._show(P_PLAYLIST)
        self._bridge.submit(
            self._fetch_playlist(pid),
            on_success=self._apply_playlist,
            on_error=self._on_playlist_error,
        )

    def open_artist(self, artist_id: int) -> None:
        self.playlist_page._is_local = False
        self.playlist_page.table.set_allow_file_delete(False)
        """歌手页：复用歌单页的骨架，头像取圆形、标签写「歌手」。"""
        self._show(P_PLAYLIST)
        self._bridge.submit(
            self._fetch_artist(artist_id),
            on_success=self._apply_artist,
            on_error=self._on_playlist_error,
        )

    def open_album(self, album_id: int) -> None:
        self.playlist_page._is_local = False
        self.playlist_page.table.set_allow_file_delete(False)
        """专辑页：同样复用歌单页，标签写「专辑」。"""
        self._show(P_PLAYLIST)
        self._bridge.submit(
            self._fetch_album(album_id),
            on_success=self._apply_album,
            on_error=self._on_playlist_error,
        )

    # ================= 异步数据 =================
    async def _fetch_home(self) -> tuple[list[Playlist], list[Track]]:
        """首页两屏数据并发拉取；任一失败由调用方兜底成演示数据。"""
        client = get_client()
        playlists, new_songs = await asyncio.gather(
            get_recommended_playlists(client, limit=10),
            get_new_songs(client, limit=HomePage.COLS),
        )
        tracks = [track for track in (to_track_from_newsong(e) for e in new_songs) if track is not None]
        return [to_playlist_card(item) for item in playlists], tracks

    def _load_home(self) -> None:
        self._bridge.submit(
            self._fetch_home(),
            on_success=self._apply_home,
            on_error=self._on_home_error,
        )

    def _apply_home(self, data: tuple[list[Playlist], list[Track]]) -> None:
        playlists, tracks = data
        self._recommended = list(playlists)
        self.home.set_playlists(playlists)
        self.home.set_new_songs(tracks)

    def _on_home_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("首页数据未加载，沿用演示数据：%s", error)
        self._show_error("首页数据加载失败，先用演示内容顶一下")
        if not self._home_retried:
            # 只自动重试一次：网络刚起来时最常见的失败，多试无益
            self._home_retried = True
            QTimer.singleShot(3000, self._load_home)

    async def _fetch_playlist(self, pid: int) -> Playlist:
        return to_playlist(await get_playlist_detail(get_client(), pid))

    def _apply_playlist(self, playlist: Playlist) -> None:
        self.playlist_page.set_playlist(playlist)

    def _on_playlist_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("歌单未加载，沿用当前内容：%s", error)
        self._show_error(f"歌单加载失败：{error_text(error)}")

    async def _fetch_artist(self, artist_id: int) -> Playlist:
        detail = await get_artist(get_client(), artist_id)
        return to_playlist_from_artist(detail)

    def _apply_artist(self, playlist: Playlist) -> None:
        subtitle = f"歌手 · {len(playlist.tracks)} 首热门 · 作品 {playlist.plays} 首"
        self._current_artist_id = playlist.id
        self.playlist_page.set_playlist(
            playlist, list(playlist.tracks), title=playlist.title,
            subtitle=subtitle, chip="歌手", round_cover=True,
            action=("全部专辑", "artist_albums"))

    async def _fetch_album(self, album_id: int):
        detail = await get_album(get_client(), album_id)
        playlist = to_playlist_from_album(detail)
        parts = [playlist.author]
        year = detail.album.publish_year
        if year:
            parts.append(f"{year} 年")
        parts.append(f"{len(playlist.tracks)} 首")
        artist = detail.album.artist
        return playlist, " · ".join(parts), (artist.id if artist else 0), playlist.author

    def _apply_album(self, data) -> None:
        playlist, subtitle, artist_id, artist_name = data
        self._album_artist_id = artist_id
        self.playlist_page.set_playlist(
            playlist, list(playlist.tracks), title=playlist.title,
            subtitle=subtitle, chip="专辑", round_cover=False,
            action=(f"歌手：{artist_name}", "album_artist") if artist_id else None)

    # ================= 歌词 =================
    def _load_lyric(self, track: Track | None) -> None:
        if track is None or track.id <= 0:
            return
        self._bridge.submit(
            self._fetch_lyric(track.id),
            on_success=self._apply_lyric,
            on_error=self._on_lyric_error,
        )

    async def _fetch_lyric(self, song_id: int) -> tuple[int, list[tuple[int, str]]]:
        response = await get_lyric(get_client(), song_id)
        return song_id, parse_lyric_with_translation(response)

    def _apply_lyric(self, data: tuple[int, list[tuple[int, str]]]) -> None:
        song_id, lines = data
        current = self.player.current
        if current is None or current.id != song_id:
            return  # 迟到的歌词，用户已经切歌了
        self.now_playing.set_lyrics(lines)

    def _on_lyric_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("歌词未加载，沿用演示歌词：%s", error)

    # ================= 提示 =================
    def _show_error(self, message: str) -> None:
        """所有页面级错误都走这条细条，不弹窗。"""
        self.banner.show_message(message, level="error", timeout_ms=6000)

    # ================= 播放 =================
    def _on_url_requested(self, seq: int, track: Track) -> None:
        self._bridge.submit(
            self._resolve_track(track),
            on_success=lambda outcome: self._apply_resolution(seq, outcome),
            on_error=lambda exc: self.player.resolve_failed(seq, error_text(exc)),
        )

    async def _resolve_track(self, track: Track) -> ResolveOutcome:
        return await self._url_service.resolve(track.id, self._settings.play_quality)

    def _apply_resolution(self, seq: int, outcome: ResolveOutcome) -> None:
        if outcome.available and outcome.result is not None:
            self.player.set_source(seq, outcome.result.url, outcome.result.trial)
            return
        if outcome.fallback is not None:
            self.player.set_source(seq, outcome.fallback.url, True)
            return
        self.player.resolve_failed(seq, error_text(outcome.error, "这首歌暂时无法播放"))

    def _on_player_error(self, message: str) -> None:
        self.banner.show_message(message, level="error", timeout_ms=6000)

    def _on_like_changed(self, track_id: int, liked: bool) -> None:
        """星标点了就同步到账号；未登录只改本地。"""
        if self._rolling_back_like or not self._logged_in:
            return
        self._bridge.submit(
            like_song(get_client(), track_id, liked),
            on_success=lambda _playlist_id: None,
            on_error=lambda exc: self._revert_like(track_id, liked, exc),
        )

    def _revert_like(self, track_id: int, liked: bool, error: BaseException) -> None:
        self._rolling_back_like = True
        try:
            self.player.set_liked(track_id, not liked)
        finally:
            self._rolling_back_like = False
        self._search_offsets: dict[tuple[str, int], int] = {}
        self._show_error(f"喜欢同步失败：{error_text(error)}")

    def _on_trial_changed(self, trial: bool) -> None:
        if trial:
            self.banner.show_message("这首歌只提供 45 秒试听片段", level="warning",
                                     timeout_ms=5000)

    # ================= 播客 / 更多 / 漫游 / 最近 =================
    def _open_podcast(self) -> None:
        self._show(P_GRID)
        self.grid_page.configure("星轨播客", "推荐单集 · 来自网易云电台", [])
        self._bridge.submit(
            self._fetch_programs(),
            on_success=self._apply_programs,
            on_error=self._on_podcast_error,
        )

    async def _fetch_programs(self):
        return await get_recommend_programs(get_client())

    def _apply_programs(self, data) -> None:
        tracks = [track for track in (to_program_track(p) for p in data.result) if track]
        self._podcast_tracks = tracks
        self._grid_mode = "podcast"
        self.grid_page.configure(
            "星轨播客", f"推荐单集 · 共 {len(tracks)} 期",
            [to_card_from_track(t) for t in tracks],
            empty_text="暂时没有推荐单集，稍后再试",
        )

    def _on_podcast_error(self, error: BaseException) -> None:
        self._show_error(f"播客加载失败：{error_text(error)}")
        self.grid_page.configure("星轨播客", "加载失败", [], empty_text="播客加载失败，稍后再试")

    def _open_more_playlists(self) -> None:
        self._show(P_GRID)
        self.grid_page.configure("推荐歌单", "正在加载…", [])
        self._bridge.submit(
            self._fetch_more_playlists(),
            on_success=self._apply_more_playlists,
            on_error=self._on_playlist_error,
        )

    async def _fetch_more_playlists(self):
        items = await get_recommended_playlists(get_client(), limit=30)
        return [
            CardItem(seed=pl.id, hue=pl.hue, title=pl.title,
                     subtitle=pl.author, cover_url=pl.cover_url)
            for pl in (to_playlist_card(item) for item in items)
        ]

    def _apply_more_playlists(self, cards) -> None:
        self._grid_mode = "playlists"
        self.grid_page.configure("推荐歌单", f"共 {len(cards)} 个 · 按你的星轨生成", list(cards))

    def _open_more_songs(self) -> None:
        self._show(P_GRID)
        self.grid_page.configure("新歌速递", "正在加载…", [])
        self._bridge.submit(
            self._fetch_more_songs(),
            on_success=self._apply_more_songs,
            on_error=self._on_search_error,
        )

    async def _fetch_more_songs(self):
        return await get_new_songs(get_client(), limit=30)

    def _apply_more_songs(self, entries) -> None:
        tracks = [t for t in (to_track_from_newsong(e) for e in entries) if t]
        self._more_tracks = tracks
        self._grid_mode = "songs"
        self.grid_page.configure("新歌速递", f"共 {len(tracks)} 首 · 本周新增",
                                 [to_card_from_track(t) for t in tracks])

    def _on_grid_card(self, seed: int) -> None:
        if self._grid_mode == "podcast":
            track = next((t for t in self._podcast_tracks if t.id == seed), None)
            if track is not None:
                self.player.play_track(track, self._podcast_tracks)
        elif self._grid_mode == "songs":
            track = next((t for t in self._more_tracks if t.id == seed), None)
            if track is not None:
                self.player.play_track(track, self._more_tracks)
        elif self._grid_mode == "playlists":
            self.open_playlist(seed)
        elif self._grid_mode == "albums":
            self.open_album(seed)

    def _start_roam(self) -> None:
        if not self._recommended:
            self._show_error("还没有可漫游的内容，等首页加载完再试")
            return
        pid = random.choice(self._recommended).id
        self._show(P_PLAYLIST)
        self._bridge.submit(
            self._fetch_roam(pid),
            on_success=self._apply_roam,
            on_error=self._on_playlist_error,
        )

    async def _fetch_roam(self, pid: int):
        playlist = to_playlist(await get_playlist_detail(get_client(), pid))
        tracks = list(playlist.tracks)
        random.shuffle(tracks)
        picked = tracks[:50]
        roam = Playlist(id=playlist.id, title="私人漫游", author="来自你的星轨",
                        plays=0, hue=playlist.hue, tag="漫游",
                        desc="随机挑了一些你可能喜欢的歌，每次都不一样。",
                        cover_url=playlist.cover_url, tracks=picked)
        return roam

    def _apply_roam(self, playlist: Playlist) -> None:
        self.playlist_page.set_playlist(
            playlist, list(playlist.tracks), title="私人漫游",
            subtitle=f"随机 {len(playlist.tracks)} 首 · 每次都不一样", chip="漫游")
        self._show(P_PLAYLIST)
        if playlist.tracks:
            self.player.set_queue(list(playlist.tracks), 0, autoplay=True)

    def _open_library(self) -> None:
        self._show_local_library()

    def _show_local_library(self) -> None:
        root = self._settings.download_dir
        tracks = scan(root)
        playlist = Playlist(id=0, title="本地曲库", author=root, plays=0, hue=150, tag="本地")
        self.playlist_page.set_playlist(
            playlist, tracks, title="本地曲库",
            subtitle=f"{len(tracks)} 个文件 · {root}", chip="本地")
        self.playlist_page.table.set_allow_file_delete(True)   # 本地曲库才允许删文件
        self.playlist_page._is_local = True
        self._show(P_PLAYLIST)
        if not tracks:
            self.banner.show_message("这个目录里没有音频文件，去设置里换个下载目录",
                                     level="info", timeout_ms=5000)

    def _delete_local_files(self, tracks: list[Track]) -> None:
        """本地曲库：把选中的文件移到回收站，并刷新列表。"""
        if not tracks:
            return
        names = "\n".join(f"· {t.title}" for t in tracks[:8])
        more = "" if len(tracks) <= 8 else f"\n… 还有 {len(tracks) - 8} 首"
        box = QMessageBox(self)
        box.setWindowTitle("从磁盘删除")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"把 {len(tracks)} 个文件移到回收站？\n\n{names}{more}")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Yes).setText("移到回收站")
        box.button(QMessageBox.StandardButton.Cancel).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        removed = 0
        for track in tracks:
            path = Path(track.path)
            if not path.exists():
                continue
            try:
                if QFile.moveToTrash(str(path)):
                    removed += 1
                else:
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue

        current = self.player.current
        if current is not None and current.path in {t.path for t in tracks}:
            self.player.stop_source()
        self._show_local_library()
        self.banner.show_message(f"已删除 {removed} 个文件（在回收站里）", level="info",
                                 timeout_ms=4000)

    def _on_task_deleted(self, payload, deleted_file: bool) -> None:
        """下载页删任务：正在播这首就停掉；本地曲库开着就刷新（防抖）。"""
        tracks = payload if isinstance(payload, list) else [payload]
        current = self.player.current
        if deleted_file and current is not None:
            if current.id in {t.id for t in tracks}:
                self.player.stop_source()
        if self._local_library_open():
            # 删 300 个文件要十几秒，刷新得太早会扫到还没删掉的
            self._schedule_library_refresh(min(8000, 120 * len(tracks)))

    def _schedule_library_refresh(self, delay: int = 600) -> None:
        """批量删除时只刷新一次：每次刷新都要重新扫描整个目录。"""
        if getattr(self, "_library_refresh_timer", None) is None:
            self._library_refresh_timer = QTimer(self)
            self._library_refresh_timer.setSingleShot(True)
            self._library_refresh_timer.timeout.connect(self._refresh_library_if_open)
        self._library_refresh_timer.start(max(200, delay))

    def _refresh_library_if_open(self) -> None:
        if self._local_library_open():
            self._show_local_library()

    def _local_library_open(self) -> bool:
        page = self.playlist_page
        return bool(getattr(page, "_is_local", False))

    def _on_page_action(self, kind: str) -> None:
        if kind == "artist_albums" and self._current_artist_id:
            self._open_artist_albums(self._current_artist_id)
        elif kind == "album_artist" and self._album_artist_id:
            self.open_artist(self._album_artist_id)

    def _open_artist_albums(self, artist_id: int) -> None:
        self._show(P_GRID)
        self.grid_page.configure("专辑", "正在加载…", [])
        self._bridge.submit(
            get_artist_albums(get_client(), artist_id, limit=30),
            on_success=self._apply_artist_albums,
            on_error=self._on_playlist_error,
        )

    def _apply_artist_albums(self, data) -> None:
        cards = []
        for album in data.hot_albums:
            hint = f"{album.publish_year} · {album.size} 首" if album.publish_year else f"{album.size} 首"
            cards.append(CardItem(seed=album.id, hue=hue_for(album.id), title=album.name,
                                  subtitle=hint, cover_url=album.pic_url))
        self._grid_mode = "albums"
        self.grid_page.configure(f"{data.artist.name} 的专辑", f"共 {len(cards)} 张",
                                 cards, empty_text="这位歌手还没有专辑")

    def _open_recent(self) -> None:
        tracks = self._recent.load()
        playlist = Playlist(id=0, title="最近播放", author="本地记录", plays=0,
                            hue=214, tag="最近")
        self.playlist_page.set_playlist(
            playlist, tracks, title="最近播放",
            subtitle=f"最近 {len(tracks)} 首 · 只记在本机", chip="最近")
        self._show(P_PLAYLIST)
        if not tracks:
            self.banner.show_message("还没有播放记录，随便听一首就有了", level="info",
                                     timeout_ms=4000)

    def _on_track_changed(self, track) -> None:
        """切歌：记进「最近播放」，并按设置恢复上次的进度。"""
        if track is None or track.id <= 0:
            return
        self._recent.add(track)
        self._save_queue()
        if not self._settings.get("memory_position", True):
            return
        if self._liked_ids:
            self.player.mark_liked(track.id, track.id in self._liked_ids)
        saved = self._resume.get(str(track.id), 0)
        if saved > 3000:
            self.player.set_resume_position(saved)

    def _remember_position(self, position: int, duration: int) -> None:
        track = self.player.current
        if track is None or track.id <= 0 or not self.player.is_playing:
            return
        if position < 3000 or (duration and position > duration - 5000):
            return
        self._resume[str(track.id)] = position
        self._resume_dirty = True
        if len(self._resume) > 200:
            self._resume = dict(list(self._resume.items())[-200:])

    def _build_tray_menu(self):
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("显示主窗口", self._show_from_tray)
        menu.addSeparator()
        menu.addAction("播放 / 暂停", self.player.toggle)
        menu.addAction("上一首", self.player.prev_track)
        menu.addAction("下一首", self.player.next_track)
        menu.addSeparator()
        menu.addAction("退出 Lunara", self._quit_from_tray)
        return menu

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._close_to_tray = False
        self._tray.hide()
        self.close()

    def _restore_geometry(self) -> None:
        raw = self._settings.get("window_geometry")
        if not raw:
            return
        try:
            from PyQt6.QtCore import QByteArray

            self.restoreGeometry(QByteArray.fromBase64(str(raw).encode("ascii")))
        except (TypeError, ValueError):
            pass

    def _save_geometry(self) -> None:
        try:
            data = bytes(self.saveGeometry().toBase64()).decode("ascii")
        except (AttributeError, ValueError):
            return
        self._settings.set("window_geometry", data)

    def _apply_download_limits(self) -> None:
        self._downloads.set_limits(
            retries=int(self._settings.get("dl_retries", 3)),
            speed_kbps=int(self._settings.get("dl_speed_kbps", 0)),
        )

    def _import_existing_files(self) -> None:
        """把下载目录里已有、但任务表没登记的文件补进来（重启后也能看到）。"""
        try:
            tracks = scan(self._settings.download_dir)
        except Exception:  # noqa: BLE001 - 扫描失败不该影响启动
            return
        if not tracks:
            return
        tasks = [
            DownloadTask(id=0, track=track, file_path=track.path, state="done",
                         bytes_done=Path(track.path).stat().st_size,
                         bytes_total=Path(track.path).stat().st_size)
            for track in tracks
        ]
        added = self._downloads.import_done(tasks)
        if added:
            self.banner.show_message(f"已把 {added} 个本地文件登记进下载列表",
                                     level="info", timeout_ms=4000)

    def _notify(self, title: str, body: str) -> None:
        if not self._settings.notify_on_complete:
            return
        if self._tray.isSystemTrayAvailable():
            self._tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _restore_session(self) -> None:
        """上次退出时的音量、倍速、队列（不开播）。"""
        self.player.set_volume(int(self._settings.get("volume", self.player.volume)))
        self.player.set_rate(float(self._settings.get("playback_rate", 1.0)))
        self.now_playing.set_lyric_offset(int(self._settings.get("lyric_offset", 0)))
        self.now_playing.set_lyric_offset(int(self._settings.get("lyric_offset", 0)))
        self._apply_sleep(int(self._settings.get("sleep_minutes", 0)))

        tracks, index = queue_store.load()
        if tracks:
            self.player.set_queue(tracks, index, autoplay=False)
            self.playlist_page.table.set_tracks(tracks)

    def _apply_sleep(self, minutes: int) -> None:
        self._sleep_timer.stop()
        if minutes > 0:
            self._sleep_timer.start(minutes * 60 * 1000)
            self.banner.show_message(f"{minutes} 分钟后自动暂停", level="info",
                                     timeout_ms=3000)

    def _on_sleep_timeout(self) -> None:
        if self.player.is_playing:
            self.player.pause()
        self.banner.show_message("睡眠定时器到点，已暂停播放", level="info", timeout_ms=5000)

    def _on_play_next(self, track: Track) -> None:
        self.player.insert_next(track)
        self.banner.show_message(f"下一首播放：{track.title}", level="info", timeout_ms=3000)

    def _on_like_many(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        self._bridge.submit(
            self._like_many(tracks),
            on_success=lambda n: self.banner.show_message(
                f"已喜欢 {n} 首", level="info", timeout_ms=3000),
            on_error=lambda exc: self._show_error(f"批量喜欢失败：{error_text(exc)}"),
        )

    async def _like_many(self, tracks: list[Track]) -> int:
        client = get_client()
        done = 0
        for track in tracks:
            try:
                await like_song(client, track.id, True)
            except Exception:  # noqa: BLE001 - 单首失败不影响其余
                continue
            self._liked_ids.add(track.id)
            done += 1
        return done

    def _on_queue_append(self, track: Track) -> None:
        self.player.queue.append(track)
        self.banner.show_message(f"已加到队列末尾：{track.title}", level="info", timeout_ms=3000)

    def _reload_current_quality(self) -> None:
        """换音质后重新解析当前曲目，并回到原来的位置。"""
        track = self.player.current
        if track is None or not track.remote or not self.player.is_playing:
            return
        position = self.player.position
        self.player.play_track(track, self.player.queue)
        QTimer.singleShot(1200, lambda: self.player.seek(position))

    def _remember_volume(self, volume: int) -> None:
        if self._settings.get("volume") != volume:
            self._settings.set("volume", int(volume))

    def _save_queue(self) -> None:
        queue_store.save(list(self.player.queue), self.player.index)

    def _flush_resume(self) -> None:
        if not self._resume_dirty:
            return
        self._resume_dirty = False
        self._settings.set("resume_positions", self._resume)

    # ================= 下载 =================
    def _enqueue_downloads(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        added = self.download_page.enqueue_tracks(list(tracks))
        skipped = getattr(self._downloads, "last_skipped", 0)
        self.navigate("local")
        if added or skipped:
            text = f"已加入 {added} 首下载任务"
            if skipped:
                text += f"，{skipped} 首磁盘上已有，跳过"
            self.banner.show_message(text, level="info", timeout_ms=4000)
        else:
            self.banner.show_message("这些歌曲已经在下载列表里了", level="info",
                                     timeout_ms=4000)

    def _on_download_finished(self, task) -> None:
        if not self._settings.notify_on_complete:
            return
        self.banner.show_message(f"《{task.track.title}》下载完成", level="info",
                                 timeout_ms=4000)

    def _on_theme_changed(self, name: str) -> None:
        label = "月光白" if name == "light" else "深空"
        self.banner.show_message(f"已切换到{label}主题，重启应用后生效",
                                 level="info", timeout_ms=5000)

    def _on_setting_changed(self, key: str, value: object) -> None:
        if key == "max_concurrent_downloads":
            self._downloads.set_concurrency(int(value))
        elif key == "download_dir":
            self.download_page.set_download_dir(str(value))
        elif key == "player_view":
            self.now_playing.set_mode(int(value))
        elif key == "fade":
            self.player.set_fade(bool(value))
        elif key == "playback_rate":
            self.player.set_rate(float(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "sleep_minutes":
            self._apply_sleep(int(value))
        elif key == "close_to_tray":
            self._close_to_tray = bool(value)
        elif key in ("dl_retries", "dl_speed_kbps"):
            self._apply_download_limits()
        elif key == "play_quality":
            self._reload_current_quality()
        elif key == "fade":
            self.player.set_fade(bool(value))
        elif key == "playback_rate":
            self.player.set_rate(float(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "sleep_minutes":
            self._apply_sleep(int(value))
        elif key == "close_to_tray":
            self._close_to_tray = bool(value)
        elif key in ("dl_retries", "dl_speed_kbps"):
            self._apply_download_limits()
        elif key == "play_quality":
            self._reload_current_quality()
        elif key == "player_view":
            self.now_playing.set_mode(int(value))
        elif key == "fade":
            self.player.set_fade(bool(value))
        elif key == "playback_rate":
            self.player.set_rate(float(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "sleep_minutes":
            self._apply_sleep(int(value))
        elif key == "close_to_tray":
            self._close_to_tray = bool(value)
        elif key in ("dl_retries", "dl_speed_kbps"):
            self._apply_download_limits()
        elif key == "play_quality":
            self._reload_current_quality()
        elif key == "fade":
            self.player.set_fade(bool(value))
        elif key == "playback_rate":
            self.player.set_rate(float(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "lyric_offset":
            self.now_playing.set_lyric_offset(int(value))
        elif key == "sleep_minutes":
            self._apply_sleep(int(value))
        elif key == "close_to_tray":
            self._close_to_tray = bool(value)
        elif key in ("dl_retries", "dl_speed_kbps"):
            self._apply_download_limits()
        elif key == "play_quality":
            self._reload_current_quality()

    # ================= 账号 =================
    def _restore_login(self) -> None:
        """启动时从加密文件恢复登录态（文件损坏就当未登录，不打扰用户）。"""
        cookies = self._account.load()
        if not cookies:
            return
        apply_cookies(get_client(), cookies)
        api_log.get_logger().info("已恢复登录态（%s）", self._account.store.backend)

    def _refresh_account(self) -> None:
        self._bridge.submit(
            self._fetch_account(),
            on_success=self._on_account_state,
            on_error=self._on_account_error,
        )

    async def _fetch_account(self) -> SessionState:
        client = get_client()
        if self._session is None:
            self._session = SessionService(client)
        return await self._session.state(force=True)

    def _on_account_state(self, state: SessionState) -> None:
        self._logged_in = state.logged_in
        self.settings_page.set_account(
            logged_in=state.logged_in, nickname=state.nickname, vip=state.vip
        )
        self.topbar.set_account(state.nickname if state.logged_in else "",
                                vip=state.vip)
        if state.logged_in and state.avatar_url:
            self._bridge.submit(
                self._fetch_avatar(state.avatar_url),
                on_success=self.topbar.set_avatar,
                on_error=lambda _exc: None,
            )
        else:
            self.topbar.set_avatar(None)
        self.topbar.set_account(state.nickname if state.logged_in else "",
                                vip=state.vip)
        if state.logged_in and state.avatar_url:
            self._bridge.submit(
                self._fetch_avatar(state.avatar_url),
                on_success=self.topbar.set_avatar,
                on_error=lambda _exc: None,
            )
        else:
            self.topbar.set_avatar(None)
        if state.logged_in and state.user_id:
            self._load_my_music(state.user_id)
        else:
            self._liked_id = None
            self.sidebar.set_my_playlists([], [])

    def _prefetch_liked_ids(self) -> None:
        if not self._liked_id:
            return
        self._bridge.submit(
            self._fetch_liked_ids(self._liked_id),
            on_success=self._apply_liked_ids,
            on_error=lambda _exc: None,
        )

    async def _fetch_liked_ids(self, playlist_id: int) -> set[int]:
        detail = await get_playlist_detail(get_client(), playlist_id)
        return {song.id for song in detail.tracks}

    def _apply_liked_ids(self, ids: set[int]) -> None:
        self._liked_ids = set(ids)
        current = self.player.current
        if current is not None:
            self.player.mark_liked(current.id, current.id in self._liked_ids)

    async def _fetch_avatar(self, url: str):
        from PyQt6.QtGui import QPixmap

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
        pixmap = QPixmap()
        pixmap.loadFromData(response.content)
        return pixmap

    def _load_my_music(self, uid: int) -> None:
        self._bridge.submit(
            self._fetch_my_music(uid),
            on_success=self._apply_my_music,
            on_error=self._on_my_music_error,
        )

    async def _fetch_my_music(self, uid: int) -> tuple[list[Playlist], list[Playlist], int | None]:
        response = await get_user_playlists(get_client(), uid, limit=100)
        return split_user_playlists(response.playlist)

    def _apply_my_music(self, data: tuple[list[Playlist], list[Playlist], int | None]) -> None:
        created, collected, liked_id = data
        self._liked_id = liked_id
        self.sidebar.set_my_playlists(created, collected)
        self._prefetch_liked_ids()

    def _on_my_music_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("我的歌单未加载：%s", error)

    def _on_account_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("登录态查询失败，按未登录处理：%s", error)

    def _on_login_requested(self) -> None:
        """开内嵌浏览器登录 → 抓 Cookie → 加密落盘 → 刷新会员态。"""
        try:
            from .services.login_browser import collect_login_cookies
        except Exception as exc:  # noqa: BLE001 - 缺 WebEngine 时给出可读日志
            api_log.get_logger().warning("登录窗口不可用：%s", exc)
            return

        cookies = collect_login_cookies(self)
        if not cookies:
            return
        if not self._account.save(cookies):
            api_log.get_logger().warning("登录信息不完整（缺少 MUSIC_U），未保存")
            return

        apply_cookies(get_client(), cookies)
        if self._session is not None:
            self._session.invalidate()
        self._refresh_account()

    def _on_logout_requested(self) -> None:
        self._account.clear()
        forget_cookies(get_client())
        if self._session is not None:
            self._session.invalidate()
        self._liked_id = None
        self._logged_in = False
        self._liked_ids.clear()
        queue_store.save([], 0)
        self.player.stop_source()
        self.playlist_page.table.set_tracks([])
        self.sidebar.set_my_playlists([], [])
        self.settings_page.set_account(logged_in=False)

    # ================= 退出清理 =================
    async def _shutdown_services(self) -> None:
        await aclose_client()
        await covers().aclose()

    def closeEvent(self, event) -> None:
        self._flush_resume()
        self._save_queue()
        self._save_geometry()
        if self._close_to_tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_hinted:
                self._tray_hinted = True
                self._tray.showMessage("Lunara 还在后台", "点托盘图标可以叫回来，右键有退出",
                                       QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        try:
            self.player.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._downloads.shutdown()
        except Exception:  # noqa: BLE001 - 退出路径不该再抛错
            pass
        try:
            run_sync(self._shutdown_services(), timeout=2.0)
        except Exception:  # noqa: BLE001 - 退出路径不该再抛错
            pass
        shutdown_bridge()
        super().closeEvent(event)

    def open_now_playing(self) -> None:
        self._show(P_NOW)

    def go_back(self) -> None:
        if self._hpos > 0:
            self._hpos -= 1
            self.stack.setCurrentIndex(self._history[self._hpos])

    def go_forward(self) -> None:
        if self._hpos < len(self._history) - 1:
            self._hpos += 1
            self.stack.setCurrentIndex(self._history[self._hpos])

    # ================= 搜索 =================
    def _remember_search(self, text: str) -> None:
        keyword = text.strip()
        if not keyword:
            return
        history = [w for w in (self._settings.get("search_history") or []) if w != keyword]
        history.insert(0, keyword)
        self._settings.set("search_history", history[:10])
        self.search_page.set_history(history[:10])

    def _on_search(self, text: str) -> None:
        self._remember_search(text)
        self._search_offsets.clear()
        self.search_page.search(text)
        self._show(P_SEARCH)
        self.search_page.refresh()
        self._request_search()

    def _on_search_live(self, text: str) -> None:
        if self.stack.currentIndex() == P_SEARCH:
            self.search_page.search(text)
        self._search_timer.start()  # 320ms 内的连续输入只发一次请求

    def _request_search(self) -> None:
        keyword = self.search_page.query
        if keyword:
            self._fetch_search(keyword, self.search_page.tab)

    def _request_search_for_tab(self, keyword: str, tab: int) -> None:
        self._fetch_search(keyword, tab)

    def _fetch_search(self, keyword: str, tab: int, offset: int = 0) -> None:
        self._bridge.submit(
            self._search(keyword, tab, offset),
            on_success=self._apply_search,
            on_error=self._on_search_error,
        )

    def _load_more(self) -> None:
        keyword = self.search_page.query
        if not keyword:
            return
        tab = self.search_page.tab
        offset = self._search_offsets.get((keyword, tab), 0)
        self._fetch_search(keyword, tab, offset)

    async def _search(self, keyword: str, tab: int,
                      offset: int = 0) -> tuple[str, int, int, SearchPayload]:
        """只打当前 Tab 对应的那一个 type，切 Tab 时再补。"""
        client = get_client()
        if tab == 0:
            page = offset // SEARCH_PAGE_SIZE + 1
            result = await search_songs(client, keyword, page=page, limit=SEARCH_PAGE_SIZE)
            payload = SearchPayload(SearchKind.SONG, tracks=tuple(to_track_list(result.songs)))
        elif tab == 1:
            result = await search_artists(client, keyword, page=offset // 20 + 1, limit=20)
            payload = SearchPayload(
                SearchKind.ARTIST, cards=tuple(to_artist_card(hit) for hit in result.artists)
            )
        elif tab == 2:
            result = await search_albums(client, keyword, page=offset // 20 + 1, limit=20)
            payload = SearchPayload(
                SearchKind.ALBUM, cards=tuple(to_album_card(hit) for hit in result.albums)
            )
        else:
            result = await search_playlists(client, keyword, page=offset // 20 + 1, limit=20)
            payload = SearchPayload(
                SearchKind.PLAYLIST, playlists=tuple(to_playlist_hit(hit) for hit in result.playlists)
            )
        return keyword, tab, offset, payload

    def _apply_search(self, data: tuple[str, int, int, SearchPayload]) -> None:
        keyword, tab, offset, payload = data
        if offset > 0:
            if payload.kind is SearchKind.SONG:
                self.search_page.append_tracks(list(payload.tracks), keyword)
            else:
                self.search_page.append_results(payload, keyword)
        else:
            self.search_page.set_results(payload, keyword)

        size = len(payload.tracks) if payload.kind is SearchKind.SONG else len(payload.cards) or len(payload.playlists)
        page_size = SEARCH_PAGE_SIZE if payload.kind is SearchKind.SONG else 20
        self._search_offsets[(keyword, tab)] = offset + size
        self.search_page.set_has_more(size >= page_size)

    def _on_search_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("搜索未返回真实结果，沿用本地过滤：%s", error)

    # ================= 窗口 =================
    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self._apply_window_state(False)
        else:
            self.showMaximized()
            self._apply_window_state(True)

    def _apply_window_state(self, maximized: bool) -> None:
        m = 0 if maximized else SHADOW_MARGIN
        self._outer.setContentsMargins(m, m, m, m)
        self.root.setProperty("windowState", "maximized" if maximized else "normal")
        self.root.style().unpolish(self.root)
        self.root.style().polish(self.root)
        self._shadow.setEnabled(not maximized)
        self.topbar.set_maximized(maximized)
        self.grip.setVisible(not maximized)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, "grip"):
            self.grip.move(self.root.width() - 18, self.root.height() - 18)
            self.grip.raise_()

    # ================= 快捷键 =================
    def _install_shortcuts(self) -> None:
        sc = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        sc.activated.connect(self._toggle_play)
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(
            self.player.next_track)
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(
            self.player.prev_track)
        QShortcut(QKeySequence("Ctrl+Up"), self).activated.connect(
            lambda: self.player.set_volume(min(100, self.player.volume + 5)))
        QShortcut(QKeySequence("Ctrl+Down"), self).activated.connect(
            lambda: self.player.set_volume(max(0, self.player.volume - 5)))
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.go_back)

    def _toggle_play(self) -> None:
        if isinstance(QApplication.focusWidget(), QLineEdit):
            return
        self.player.toggle()
