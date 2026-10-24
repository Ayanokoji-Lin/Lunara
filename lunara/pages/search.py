"""Lunara · 搜索页（单曲列表 + 歌手/专辑/歌单网格）

数据流：
1. 输入时先跑一次本地过滤（``data.py`` 的演示曲库），保证输入框一敲就有反应；
2. 主窗口做 320ms 防抖，再去打真实接口，结果通过 ``set_results()`` 覆盖；
3. 切 Tab 时如果这一类的真实结果还没拉过，发 ``resultsRequested`` 让主窗口补一次。

这样离线/断网时页面照旧可用，联网后自动变真。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..api.modules.search import SearchKind
from ..core.player import Player
from ..data import PLAYLISTS, TRACKS, Playlist, Track
from ..services.catalog import CardItem, SearchPayload
from ..widgets.anim import detach, stagger
from ..widgets.cover import CoverCard
from ..widgets.track_table import TrackTable
from .base import BasePage

TABS = ("单曲", "歌手", "专辑", "歌单")

#: 搜索类型 → Tab 下标
TAB_FOR_KIND: dict[SearchKind, int] = {
    SearchKind.SONG: 0,
    SearchKind.ARTIST: 1,
    SearchKind.ALBUM: 2,
    SearchKind.PLAYLIST: 3,
}


class SearchPage(BasePage):
    COLS = 5

    #: 某个 Tab 需要真实数据（关键词, Tab 下标）
    resultsRequested = pyqtSignal(str, int)
    #: 点歌单卡片 → 打开详情
    playlistActivated = pyqtSignal("qint64")
    artistActivated = pyqtSignal("qint64")
    albumActivated = pyqtSignal("qint64")
    moreRequested = pyqtSignal()      # 单曲列表「加载更多」
    suggestRequested = pyqtSignal(str)  # 空态里的推荐关键词

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.player = player
        self._tab = 0
        self._query = ""
        self._tracks: list[Track] = []
        self._artists: list[CardItem] = []
        self._albums: list[CardItem] = []
        self._lists: list[Playlist] = []
        self._remote: set[tuple[str, int]] = set()   # 已拿到真实结果的 (关键词, tab)
        self._has_more = False

        self.add_page_header("搜索", "在星海里打捞你想听的声音")

        # ---------- Tab ----------
        tabs = QHBoxLayout()
        tabs.setContentsMargins(0, 0, 0, 0)
        tabs.setSpacing(8)
        self._tab_btns: list[QPushButton] = []
        for i, name in enumerate(TABS):
            b = QPushButton(name)
            b.setObjectName("ModeBtn")
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setMinimumWidth(74)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, idx=i: self.set_tab(idx))
            tabs.addWidget(b)
            self._tab_btns.append(b)
        tabs.addStretch(1)
        bar = QWidget()
        bar.setLayout(tabs)
        tabs.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(bar)

        # ---------- 结果区 ----------
        self.table = TrackTable()
        self.table.trackActivated.connect(
            lambda t: self.player.play_track(t, self._tracks or TRACKS))
        self._table_panel = QFrame()
        self._table_panel.setObjectName("Panel")
        tpv = QVBoxLayout(self._table_panel)
        tpv.setContentsMargins(14, 8, 14, 12)
        tpv.setSpacing(0)
        tpv.addWidget(self.table)

        self.btn_more = QPushButton("加载更多")
        self.btn_more.setObjectName("GhostPill")
        self.btn_more.setFixedHeight(32)
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setVisible(False)
        self.btn_more.clicked.connect(self._request_more)
        tpv.addWidget(self.btn_more, 0, Qt.AlignmentFlag.AlignHCenter)

        self.body.addWidget(self._table_panel)

        self.grid_host = QWidget()
        self.grid_layout = QVBoxLayout(self.grid_host)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)
        self.body.addWidget(self.grid_host)

        self.empty = QLabel("输入关键词，开始搜索")
        self.empty.setObjectName("BodyText")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setFixedHeight(120)
        self.body.addWidget(self.empty)

        self._history: list[str] = []
        self._suggest = QWidget()
        self._suggest_layout = QHBoxLayout(self._suggest)
        self._suggest_layout.setContentsMargins(0, 0, 0, 0)
        self._suggest_layout.setSpacing(10)
        self.body.addWidget(self._suggest)
        self._rebuild_suggest()

        self.body.addStretch(1)
        self.player.trackChanged.connect(self.table.set_playing)
        self.set_tab(0)
        self._refresh()

    # ---------------- 对外 ----------------
    @property
    def query(self) -> str:
        return self._query

    @property
    def tab(self) -> int:
        return self._tab

    def append_tracks(self, tracks: list[Track], keyword: str) -> None:
        """追加一页单曲结果（按 id 去重）。"""
        if keyword.strip() != self._query:
            return
        known = {track.id for track in self._tracks}
        fresh = [track for track in tracks if track.id not in known]
        if fresh:
            self._tracks.extend(fresh)
            self.table.set_tracks(self._tracks)
        self.set_loading_more(False)

    def append_results(self, payload: SearchPayload, keyword: str) -> None:
        """非单曲 Tab 的追加（按 seed 去重）。"""
        if keyword.strip() != self._query:
            return
        if payload.kind is SearchKind.ARTIST:
            known = {item.seed for item in self._artists}
            self._artists.extend(item for item in payload.cards if item.seed not in known)
        elif payload.kind is SearchKind.ALBUM:
            known = {item.seed for item in self._albums}
            self._albums.extend(item for item in payload.cards if item.seed not in known)
        else:
            known = {item.seed for item in self._lists}
            self._lists.extend(item for item in payload.playlists if item.seed not in known)
        self._rebuild_grid()
        self.set_loading_more(False)

    def set_history(self, words: list[str]) -> None:
        """最近搜过的词，空关键词时和推荐词一起显示。"""
        self._history = list(words)
        self._rebuild_suggest()

    def _rebuild_suggest(self) -> None:
        while self._suggest_layout.count():
            item = self._suggest_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._suggest_layout.addStretch(1)
        for word in list(self._history)[:4]:
            self._suggest_layout.addWidget(self._make_chip(f"↻ {word}", word))
        for word in ("周杰伦", "华语", "纯音乐", "深夜"):
            self._suggest_layout.addWidget(self._make_chip(word, word))
        self._suggest_layout.addStretch(1)

    def _make_chip(self, label: str, word: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("GhostPill")
        button.setFixedHeight(30)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _=False, w=word: self.suggestRequested.emit(w))
        return button

    def set_has_more(self, has_more: bool) -> None:
        self._has_more = bool(has_more)
        self._refresh_more()

    def set_loading_more(self, loading: bool) -> None:
        self.btn_more.setEnabled(not loading)
        self.btn_more.setText("加载中…" if loading else "加载更多")

    def _request_more(self) -> None:
        self.set_loading_more(True)
        self.moreRequested.emit()

    def _refresh_more(self) -> None:
        has_content = bool(self._tracks) if self._tab == 0 else bool(self._grid_items())
        self.btn_more.setVisible(has_content and self._has_more)

    def set_results(self, payload: SearchPayload, keyword: str) -> None:
        """接收真实搜索结果；关键词已变则丢弃（防止慢请求盖掉新结果）。"""
        if keyword.strip() != self._query:
            return
        tab = TAB_FOR_KIND.get(payload.kind)
        if tab is None:
            return

        if payload.kind is SearchKind.SONG:
            self._tracks = list(payload.tracks)
            self.table.set_tracks(self._tracks)
        elif payload.kind is SearchKind.ARTIST:
            self._artists = list(payload.cards)
        elif payload.kind is SearchKind.ALBUM:
            self._albums = list(payload.cards)
        else:
            self._lists = list(payload.playlists)

        self._remote.add((keyword, tab))
        if payload.kind is SearchKind.SONG:
            self.set_loading_more(False)
        if self._tab == tab:
            self._refresh()

    # ---------------- Tab ----------------
    def set_tab(self, index: int) -> None:
        self._tab = index
        for i, b in enumerate(self._tab_btns):
            b.setChecked(i == index)
        self._refresh()
        self._refresh_more()
        if self._query and (self._query, index) not in self._remote:
            self.resultsRequested.emit(self._query, index)

    # ---------------- 搜索（本地兜底） ----------------
    def search(self, text: str) -> None:
        q = text.strip()
        if q != self._query:
            self._remote.clear()
        self._query = q
        if not q:
            self._tracks, self._artists, self._albums, self._lists = [], [], [], []
            self.table.set_tracks([])
            self._refresh()
            return

        self._tracks = [t for t in TRACKS
                        if q in t.title or q in t.artist or q in t.album]
        artists: dict[str, Track] = {}
        albums: dict[str, Track] = {}
        for t in self._tracks:
            artists.setdefault(t.artist, t)
            albums.setdefault(t.album, t)
        self._artists = [
            CardItem(seed=t.seed, hue=t.hue, title=name, subtitle="歌手")
            for name, t in artists.items()
        ]
        self._albums = [
            CardItem(seed=t.seed, hue=t.hue, title=name, subtitle=t.artist)
            for name, t in albums.items()
        ]
        self._lists = [p for p in PLAYLISTS if q in p.title or q in p.author]
        self.table.set_tracks(self._tracks)
        self._refresh()

    # ---------------- 视图切换 ----------------
    def _grid_items(self) -> list:
        return {1: self._artists, 2: self._albums, 3: self._lists}.get(self._tab, [])

    def _has_content(self) -> bool:
        return {
            0: bool(self._tracks),
            1: bool(self._artists),
            2: bool(self._albums),
            3: bool(self._lists),
        }[self._tab]

    def refresh(self) -> None:
        """外部切到本页时刷新空态（推荐词只在没有关键词时出现）。"""
        self._refresh()

    def _refresh(self) -> None:
        has = self._has_content()
        self._table_panel.setVisible(self._tab == 0 and has)
        self.grid_host.setVisible(self._tab > 0 and has)
        self.empty.setVisible(not has)

        self._suggest.setVisible(not has and not self._query)
        if not has:
            q = self._query
            self.empty.setText(f"没有找到「{q}」相关的星尘，换个词试试？" if q
                               else "输入关键词，或者点下面的推荐")
            return
        if self._tab > 0:
            self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                detach(w)
                w.hide()
                w.setParent(None)
                w.deleteLater()

        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(26)
        for c in range(self.COLS):
            grid.setColumnStretch(c, 1)

        cards: list[CoverCard] = []
        if self._tab == 1:
            for item in self._artists:
                card = CoverCard(item.seed, item.hue, item.title, item.subtitle, "",
                                 round_cover=True, cover_url=item.cover_url)
                card.clicked.connect(
                    lambda aid=item.seed: self.artistActivated.emit(aid))
                cards.append(card)
        elif self._tab == 2:
            for item in self._albums:
                card = CoverCard(item.seed, item.hue, item.title, item.subtitle, "",
                                 cover_url=item.cover_url)
                card.clicked.connect(
                    lambda alb=item.seed: self.albumActivated.emit(alb))
                cards.append(card)
        else:
            for p in self._lists:
                card = CoverCard(p.id, p.hue, p.title, p.author, p.plays_text,
                                 cover_url=p.cover_url)
                card.clicked.connect(lambda pid=p.id: self.playlistActivated.emit(pid))
                cards.append(card)

        for i, card in enumerate(cards):
            grid.addWidget(card, i // self.COLS, i % self.COLS)
        self.grid_layout.addWidget(wrap)
