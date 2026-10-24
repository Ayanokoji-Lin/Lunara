"""Lunara · 侧边栏

结构：Logo → 主导航 → 我的音乐 → 可折叠歌单组。
选中态 = QSS 背景 + 左侧 3px 主色指示条 + 图标/文字转为主色。
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..data import Playlist
from ..theme import THEME
from .common import font
from .icons import icon


class LogoMark(QWidget):
    """极简弯月 Logo（程序化绘制，无需 SVG 资源）。"""

    def __init__(self, size: int = 26, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = self._size
        glow = QRadialGradient(QPointF(s / 2, s / 2), s * 1.1)
        glow.setColorAt(0.0, QColor(139, 92, 246, 95))
        glow.setColorAt(1.0, QColor(139, 92, 246, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(s / 2, s / 2), s * 1.1, s * 1.1)

        outer = QPainterPath()
        outer.addEllipse(1.0, 1.0, s - 2.0, s - 2.0)
        inner = QPainterPath()
        inner.addEllipse(1.0 + s * 0.42, 1.0 - s * 0.10, s - 2.0, s - 2.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(THEME["primary"]))
        p.drawPath(outer.subtracted(inner))


class SidebarItem(QPushButton):
    def __init__(self, key: str, text: str, icon_name: str = "",
                 parent: QWidget | None = None):
        super().__init__(text, parent)
        self.key = key
        self._icon_name = icon_name
        self.setObjectName("SidebarItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(16, 16))
        if icon_name:
            self.setIcon(icon(icon_name, THEME["text_sub"]))

        self._indicator = QFrame(self)
        self._indicator.setObjectName("NavIndicator")
        self._indicator.setFixedWidth(3)
        self._indicator.hide()

        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, on: bool) -> None:
        self._indicator.setVisible(on)
        if self._icon_name:
            self.setIcon(icon(self._icon_name,
                              THEME["primary"] if on else THEME["text_sub"]))

    def resizeEvent(self, e) -> None:
        self._indicator.setGeometry(0, (self.height() - 18) // 2, 3, 18)
        self._indicator.raise_()
        super().resizeEvent(e)


class Sidebar(QFrame):
    navigate = pyqtSignal(str)

    #: 歌单名可用宽度：按钮 192 - padding-left 36 - 余量 6
    TEXT_WIDTH = 150

    NAV_MAIN = [
        ("home", "月海拾音", "fa5s.moon"),
        ("podcast", "星轨播客", "fa5s.podcast"),
        ("roam", "私人漫游", "fa5s.compass"),
    ]
    NAV_MINE = [
        ("liked", "我喜欢的音乐", "fa5s.star"),
        ("recent", "最近播放", "fa5s.history"),
        ("local", "本地下载", "fa5s.download"),
        ("library", "本地曲库", "fa5s.folder-open"),
    ]
    GROUPS = [
        ("创建的歌单", ["深夜飞行手册", "月海拾音 · 私藏", "凌晨四点的城市"]),
        ("收藏的歌单", ["后摇：银河尽头的噪音", "月光下的钢琴", "潮汐白噪音"]),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(204)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 10)
        root.setSpacing(2)

        # ---------- Logo ----------
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(6, 0, 0, 10)
        logo_row.setSpacing(9)
        logo_row.addWidget(LogoMark(24))
        wordmark = QLabel("Lunara")
        wordmark.setFont(font(18, 600))
        wordmark.setStyleSheet(f"color: {THEME['text_main']}; letter-spacing: 1px;")
        logo_row.addWidget(wordmark)
        logo_row.addStretch(1)
        root.addLayout(logo_row)

        # ---------- 滚动导航区 ----------
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        self._items: dict[str, SidebarItem] = {}

        for key, text, ico in self.NAV_MAIN:
            col.addWidget(self._add_item(key, text, ico))

        col.addSpacing(10)
        col.addWidget(self._section("我的音乐"))
        for key, text, ico in self.NAV_MINE:
            col.addWidget(self._add_item(key, text, ico))

        self._col = col
        self._group_widgets: list[QWidget] = []
        self._rebuild_groups()

        col.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        foot = QLabel("深空模式 · v0.1")
        foot.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px; padding-left: 8px;")
        root.addWidget(foot)

        self.select("home")

    # ---------------- 构建 ----------------
    def _add_item(self, key: str, text: str, ico: str) -> SidebarItem:
        item = SidebarItem(key, text, ico)
        item.clicked.connect(lambda _=False, k=key: self._on_click(k))
        self._items[key] = item
        return item

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SidebarSection")
        lbl.setFixedHeight(26)
        return lbl

    def _default_groups(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """演示用的分组（未登录时显示）。"""
        return [
            (title, [(name, f"playlist:{gi * 3 + ni}") for ni, name in enumerate(names)])
            for gi, (title, names) in enumerate(self.GROUPS)
        ]

    def _rebuild_groups(
        self, groups: list[tuple[str, list[tuple[str, str]]]] | None = None
    ) -> None:
        """重建「歌单分组」区域；``entries`` 是 (显示文案, 导航 key)。"""
        for widget in self._group_widgets:
            self._col.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._group_widgets.clear()

        # 演示分组的 key 是 ``playlist:N``，真实歌单是 ``myplaylist:<id>``。
        # 两批都要清掉：只清 myplaylist 的话，切到真实歌单后 ``_items`` 里还留着
        # 已被 deleteLater 的演示按钮，点任何导航项都会 RuntimeError。
        for key in [k for k in self._items
                    if k.startswith(("playlist:", "myplaylist:"))]:
            self._items.pop(key, None)

        # 插到末尾的 stretch 之前
        for gi, (title, entries) in enumerate(groups or self._default_groups()):
            index = self._col.count() - 1
            self._col.insertSpacing(index, 10)
            box = self._group(title, entries)
            self._group_widgets.append(box)
            self._col.insertWidget(self._col.count() - 1, box)

    def set_my_playlists(self, created: list[Playlist], collected: list[Playlist]) -> None:
        """登录后把侧栏换成真实歌单；两个都空则恢复演示分组。"""
        if not created and not collected:
            self._rebuild_groups()
            return

        groups: list[tuple[str, list[tuple[str, str]]]] = []
        if created:
            groups.append(("创建的歌单", [(p.title, f"myplaylist:{p.id}") for p in created]))
        if collected:
            groups.append(("收藏的歌单", [(p.title, f"myplaylist:{p.id}") for p in collected]))
        self._rebuild_groups(groups)

    def _group(self, title: str, entries: list[tuple[str, str]]) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)

        btn = QPushButton(f"  {title}")
        btn.setObjectName("SidebarGroup")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setIcon(icon("fa5s.chevron-down", THEME["text_dim"]))
        btn.setIconSize(QSize(9, 9))
        lay.addWidget(btn)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(1)
        for text, key in entries:
            sub = QPushButton()
            # 歌单名可能很长，按实际宽度省略，鼠标悬停看全名
            metrics = QFontMetrics(sub.font())
            sub.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, self.TEXT_WIDTH))
            sub.setToolTip(text)
            sub.setObjectName("SidebarSubItem")
            sub.setCheckable(True)
            sub.setCursor(Qt.CursorShape.PointingHandCursor)
            sub.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            sub.clicked.connect(lambda _=False, k=key: self._on_click(k))
            self._items[key] = sub
            bl.addWidget(sub)
        lay.addWidget(body)

        def toggle(checked: bool, b=body, t=btn) -> None:
            b.setVisible(checked)
            t.setIcon(icon("fa5s.chevron-down" if checked else "fa5s.chevron-right",
                           THEME["text_dim"]))

        btn.clicked.connect(lambda _=False, b=body: toggle(b.isVisible(), b, btn))
        return box

    # ---------------- 选中 ----------------
    def _on_click(self, key: str) -> None:
        self.select(key)
        self.navigate.emit(key)

    def select(self, key: str) -> None:
        dead: list[str] = []
        for k, w in self._items.items():
            try:
                w.setChecked(k == key)
            except RuntimeError:
                # 控件已被销毁（分组重建过）：记下来，遍历完统一剔除
                dead.append(k)
        for k in dead:
            self._items.pop(k, None)
