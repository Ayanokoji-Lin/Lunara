"""Lunara · 主窗口（无边框 + 悬浮阴影 + 四大模块装配）"""
from __future__ import annotations

import asyncio

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .api import aclose_client, get_client
from .api.core import logging as api_log
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
from .data import PLAYLISTS, TRACKS, Playlist, Track
from .pages.base import EmptyPage
from .pages.download import DownloadPage
from .pages.home import HomePage
from .pages.now_playing import NowPlayingPage
from .pages.playlist import PlaylistPage
from .pages.search import SearchPage
from .pages.settings import SettingsPage
from .services.account import AccountStore, apply_cookies, forget_cookies
from .services.async_bridge import run_sync, shutdown as shutdown_bridge
from .services.covers import covers
from .services.catalog import (
    SearchPayload,
    split_user_playlists,
    to_album_card,
    to_artist_card,
    to_playlist,
    to_playlist_card,
    to_playlist_hit,
    to_track_from_newsong,
    to_track_list,
)
from .services.lyrics import parse_lyric_response
from .services.qt_bridge import QtAsyncBridge
from .services.session import SessionService, SessionState
from .widgets.player_bar import PlayerBar
from .widgets.sidebar import Sidebar
from .widgets.topbar import TopBar

SHADOW_MARGIN = 18

# 页面索引
P_HOME, P_PLAYLIST, P_SEARCH, P_SETTINGS, P_NOW, P_EMPTY, P_DOWNLOAD = range(7)

EMPTY_PAGES = {
    "podcast": ("星轨播客", "订阅你喜欢的播客，让夜晚有声音陪着。", "fa5s.podcast"),
    "video": ("潮汐视频", "月海实录、现场演出与 4K 沉浸影像。", "fa5s.film"),
    "roam": ("私人漫游", "沿着你的星轨一直播放，不重复、不打断。", "fa5s.compass"),
    "cloud": ("我的星云", "云盘里空空如也，上传音乐即可随处播放。", "fa5s.cloud"),
}


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
        self.stack = QStackedWidget()
        cl.addWidget(self.stack)

        rv.addWidget(self.topbar)
        rv.addWidget(content, 1)
        body.addWidget(self.sidebar)
        body.addWidget(right, 1)
        rl.addLayout(body, 1)

        self.player_bar = PlayerBar(self.player)
        rl.addWidget(self.player_bar)

        # ---------------- 页面注册 ----------------
        self.home = HomePage(self.player)
        self.playlist_page = PlaylistPage(self.player)
        self.search_page = SearchPage(self.player)
        self.settings_page = SettingsPage()
        self.now_playing = NowPlayingPage(self.player)
        self.empty_page = EmptyPage("星轨播客", "", "fa5s.podcast")
        self.download_page = DownloadPage(self.player)
        for page in (self.home, self.playlist_page, self.search_page,
                     self.settings_page, self.now_playing, self.empty_page,
                     self.download_page):
            self.stack.addWidget(page)

        self._history: list[int] = [P_HOME]
        self._hpos = 0

        # ---------------- 交互连接 ----------------
        self.sidebar.navigate.connect(self.navigate)
        self.home.playlistActivated.connect(self.open_playlist)
        self.topbar.searchSubmitted.connect(self._on_search)
        self.topbar.searchChanged.connect(self._on_search_live)
        self.topbar.btn_cog.clicked.connect(lambda: self.navigate("settings"))
        self.topbar.minimizeRequested.connect(self.showMinimized)
        self.topbar.maximizeRequested.connect(self.toggle_maximize)
        self.topbar.closeRequested.connect(self.close)
        self.topbar.backClicked.connect(self.go_back)
        self.topbar.forwardClicked.connect(self.go_forward)
        self.player_bar.openNowPlaying.connect(self.open_now_playing)
        self.playlist_page.downloadRequested.connect(lambda: self.navigate("local"))
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
        self.player.trackChanged.connect(self._load_lyric)
        self.settings_page.loginRequested.connect(self._on_login_requested)
        self.settings_page.logoutRequested.connect(self._on_logout_requested)

        self._account = AccountStore()
        self._session: SessionService | None = None
        self._liked_id: int | None = None
        self._restore_login()

        QTimer.singleShot(0, self._load_home)
        QTimer.singleShot(0, self._refresh_account)

    # ================= 导航 =================
    def _show(self, index: int, record: bool = True) -> None:
        self.stack.setCurrentIndex(index)
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
            pl = Playlist(0, "最近播放", "蝶恋", 96_000, 214, "最近")
            self.playlist_page.set_playlist(pl, TRACKS[2:12], title="最近播放")
            self._show(P_PLAYLIST)
        elif key == "local":
            self._show(P_DOWNLOAD)
        elif key in EMPTY_PAGES:
            self.empty_page.configure(*EMPTY_PAGES[key])
            self._show(P_EMPTY)

    def open_playlist(self, pid: int) -> None:
        """打开歌单：先切页（保留上一屏内容），再异步换成真实数据。"""
        self._show(P_PLAYLIST)
        self._bridge.submit(
            self._fetch_playlist(pid),
            on_success=self._apply_playlist,
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
        self.home.set_playlists(playlists)
        self.home.set_new_songs(tracks)

    def _on_home_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("首页数据未加载，沿用演示数据：%s", error)

    async def _fetch_playlist(self, pid: int) -> Playlist:
        return to_playlist(await get_playlist_detail(get_client(), pid))

    def _apply_playlist(self, playlist: Playlist) -> None:
        self.playlist_page.set_playlist(playlist)

    def _on_playlist_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("歌单未加载，沿用当前内容：%s", error)

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
        return song_id, parse_lyric_response(response)

    def _apply_lyric(self, data: tuple[int, list[tuple[int, str]]]) -> None:
        song_id, lines = data
        current = self.player.current
        if current is None or current.id != song_id:
            return  # 迟到的歌词，用户已经切歌了
        self.now_playing.set_lyrics(lines)

    def _on_lyric_error(self, error: BaseException) -> None:
        api_log.get_logger().warning("歌词未加载，沿用演示歌词：%s", error)

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
        self.settings_page.set_account(
            logged_in=state.logged_in, nickname=state.nickname, vip=state.vip
        )
        if state.logged_in and state.user_id:
            self._load_my_music(state.user_id)
        else:
            self._liked_id = None
            self.sidebar.set_my_playlists([], [])

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
        self.sidebar.set_my_playlists([], [])
        self.settings_page.set_account(logged_in=False)

    # ================= 退出清理 =================
    async def _shutdown_services(self) -> None:
        await aclose_client()
        await covers().aclose()

    def closeEvent(self, event) -> None:
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
    def _on_search(self, text: str) -> None:
        self.search_page.search(text)
        self._show(P_SEARCH)
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

    def _fetch_search(self, keyword: str, tab: int) -> None:
        self._bridge.submit(
            self._search(keyword, tab),
            on_success=self._apply_search,
            on_error=self._on_search_error,
        )

    async def _search(self, keyword: str, tab: int) -> tuple[str, SearchPayload]:
        """只打当前 Tab 对应的那一个 type，切 Tab 时再补。"""
        client = get_client()
        if tab == 0:
            result = await search_songs(client, keyword, limit=30)
            payload = SearchPayload(SearchKind.SONG, tracks=tuple(to_track_list(result.songs)))
        elif tab == 1:
            result = await search_artists(client, keyword, limit=20)
            payload = SearchPayload(
                SearchKind.ARTIST, cards=tuple(to_artist_card(hit) for hit in result.artists)
            )
        elif tab == 2:
            result = await search_albums(client, keyword, limit=20)
            payload = SearchPayload(
                SearchKind.ALBUM, cards=tuple(to_album_card(hit) for hit in result.albums)
            )
        else:
            result = await search_playlists(client, keyword, limit=20)
            payload = SearchPayload(
                SearchKind.PLAYLIST, playlists=tuple(to_playlist_hit(hit) for hit in result.playlists)
            )
        return keyword, payload

    def _apply_search(self, data: tuple[str, SearchPayload]) -> None:
        keyword, payload = data
        self.search_page.set_results(payload, keyword)

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
