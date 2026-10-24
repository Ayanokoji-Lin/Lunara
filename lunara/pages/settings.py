"""Lunara · 设置页（左分类导航 + QStackedWidget）"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..services.settings_store import (
    QUALITY_OPTIONS,
    SettingsStore,
    quality_at,
    quality_index,
)
from ..theme import THEME
from ..widgets.common import Divider, font
from ..widgets.sidebar import LogoMark
from ..widgets.toggle import Switch
from .base import BasePage

NAV = ("播放", "音质", "下载", "账号", "关于")


def _disabled(widget: QWidget) -> QWidget:
    """未实现的开关：直接置灰，别让它看起来能用。"""
    widget.setEnabled(False)
    widget.setToolTip("暂未实现")
    return widget


class SettingsPage(BasePage):
    loginRequested = pyqtSignal()
    logoutRequested = pyqtSignal()
    themeChanged = pyqtSignal(str)

    def __init__(self, settings: SettingsStore | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.settings = settings or SettingsStore()
        self.add_page_header("设置", "让 Lunara 更贴合你的耳朵")

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(26)

        nav = QWidget()
        nav.setFixedWidth(156)
        nv = QVBoxLayout(nav)
        nv.setContentsMargins(0, 0, 0, 0)
        nv.setSpacing(4)

        self.stack = QStackedWidget()
        self._nav_btns: list[QPushButton] = []
        for i, name in enumerate(NAV):
            b = QPushButton(name)
            b.setObjectName("SettingsNav")
            b.setCheckable(True)
            b.setFixedHeight(36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, idx=i: self.switch(idx))
            nv.addWidget(b)
            self._nav_btns.append(b)
        nv.addStretch(1)

        self.stack.addWidget(self._build_play())
        self.stack.addWidget(self._build_quality())
        self.stack.addWidget(self._build_download())
        self.stack.addWidget(self._build_account())
        self.stack.addWidget(self._build_about())

        h.addWidget(nav, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(self.stack, 1)
        row.setSizePolicy(row.sizePolicy().horizontalPolicy(),
                          row.sizePolicy().verticalPolicy())
        self.body.addWidget(row, 1)
        self.switch(0)

    # ---------------- 组件 ----------------
    def _row(self, title: str, desc: str, control: QWidget) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 14, 0, 14)
        h.setSpacing(16)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)
        t = QLabel(title)
        t.setFont(font(12, 500))
        t.setStyleSheet(f"color: {THEME['text_main']};")
        d = QLabel(desc)
        d.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        col.addWidget(t)
        col.addWidget(d)
        h.addLayout(col, 1)
        h.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return w

    def _panel(self, rows: list[tuple[str, str, QWidget]]) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(22, 6, 22, 6)
        v.setSpacing(0)
        for i, (title, desc, ctrl) in enumerate(rows):
            v.addWidget(self._row(title, desc, ctrl))
            if i < len(rows) - 1:
                v.addWidget(Divider())
        v.addStretch(1)
        return panel

    def _combo(self, items: list[str], current: int = 0) -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        cb.setCurrentIndex(current)
        cb.setFixedWidth(148)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        return cb

    # ---------------- 面板 ----------------
    def _build_play(self) -> QWidget:
        self.cb_theme = self._combo(["深空", "月光白"],
                                    1 if self.settings.get("theme") == "light" else 0)
        self.cb_theme.currentIndexChanged.connect(self._on_theme_changed)

        self.cb_view = self._combo(["唱片 + 歌词", "纯歌词", "纯封面"],
                                   int(self.settings.get("player_view", 0)))
        self.cb_view.currentIndexChanged.connect(
            lambda i: self.settings.set("player_view", i))

        return self._panel([
            ("外观主题", "切换后重启应用生效", self.cb_theme),
            ("播放页默认模式", "进入播放页时使用的展示方式", self.cb_view),
            ("记忆播放位置", "暂未实现：下次启动时从上次进度继续播放",
             _disabled(Switch(False))),
            ("淡入淡出", "暂未实现：切歌时做 300ms 的音量过渡", _disabled(Switch(False))),
            ("桌面歌词", "暂未实现：在桌面上悬浮显示当前歌词", _disabled(Switch(False))),
        ])

    def _build_quality(self) -> QWidget:
        labels = [label for label, _ in QUALITY_OPTIONS]

        self.cb_play_quality = self._combo(
            labels, quality_index(self.settings.play_quality))
        self.cb_play_quality.currentIndexChanged.connect(
            lambda i: self.settings.set("play_quality", quality_at(i).value))

        self.cb_download_quality = self._combo(
            labels, quality_index(self.settings.download_quality))
        self.cb_download_quality.currentIndexChanged.connect(
            lambda i: self.settings.set("download_quality", quality_at(i).value))

        return self._panel([
            ("在线播放音质", "网络良好时建议选择「极高」", self.cb_play_quality),
            ("下载音质", "下载到本地时使用的音质", self.cb_download_quality),
            ("移动网络自动降级", "暂未实现：检测到流量网络时自动降级",
             _disabled(Switch(False))),
        ])

    def _build_download(self) -> QWidget:
        self.lbl_download_dir = QLabel(str(self.settings.download_dir))
        self.lbl_download_dir.setStyleSheet(
            f"color: {THEME['text_sub']}; font-size: 11px;"
            f" background: {THEME['bg_input']}; border-radius: 6px;"
            f" padding: 5px 10px;")

        self.btn_change_dir = QPushButton("更改")
        self.btn_change_dir.setObjectName("GhostPill")
        self.btn_change_dir.setFixedHeight(30)
        self.btn_change_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_dir.clicked.connect(self._choose_download_dir)

        box = QWidget()
        bh = QHBoxLayout(box)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        bh.addWidget(self.lbl_download_dir)
        bh.addWidget(self.btn_change_dir)

        limits = ["2", "3", "5", "8"]
        current = self.settings.max_concurrent_downloads
        index = limits.index(str(current)) if str(current) in limits else 1
        self.cb_concurrency = self._combo(limits, index)
        self.cb_concurrency.currentIndexChanged.connect(
            lambda i: self.settings.set("max_concurrent_downloads", int(limits[i])))

        self.sw_notify = Switch(self.settings.notify_on_complete)
        self.sw_notify.toggled.connect(
            lambda on: self.settings.set("notify_on_complete", bool(on)))

        return self._panel([
            ("下载目录", "歌曲与封面会保存在该目录下", box),
            ("同时下载数量", "数量越多越占用带宽", self.cb_concurrency),
            ("下载完成后提示", "在右下角弹出通知", self.sw_notify),
        ])

    def _on_theme_changed(self, index: int) -> None:
        name = "light" if index == 1 else "dark"
        self.settings.set("theme", name)
        self.themeChanged.emit(name)

    def _choose_download_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "选择下载目录", str(self.settings.download_dir))
        if not path:
            return
        self.settings.set("download_dir", path)
        self.set_download_dir(path)

    def set_download_dir(self, path: str) -> None:
        self.lbl_download_dir.setText(path)

    def _build_account(self) -> QWidget:
        self.lbl_account = QLabel("未登录 · 只能浏览公开内容")
        self.lbl_account.setStyleSheet(
            f"color: {THEME['text_sub']}; font-size: 11px;")

        self.btn_login = QPushButton("  登录")
        self.btn_login.setObjectName("PrimaryPill")
        self.btn_login.setFixedHeight(30)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self.loginRequested)

        self.btn_logout = QPushButton("  退出登录")
        self.btn_logout.setObjectName("GhostPill")
        self.btn_logout.setFixedHeight(30)
        self.btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_logout.setVisible(False)
        self.btn_logout.clicked.connect(self.logoutRequested)

        box = QWidget()
        bh = QHBoxLayout(box)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        bh.addWidget(self.lbl_account)
        bh.addWidget(self.btn_login)
        bh.addWidget(self.btn_logout)

        local = QLabel("系统加密（DPAPI）")
        local.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")

        return self._panel([
            ("账号", "登录后可同步我的歌单、喜欢的音乐与会员曲目", box),
            ("登录信息", "Cookie 只保存在本机，不上传任何服务器", local),
        ])

    def set_account(self, *, logged_in: bool, nickname: str = "", vip: bool = False) -> None:
        """由主窗口在登录态变化时调用。"""
        if logged_in:
            name = nickname or "已登录"
            self.lbl_account.setText(f"{name}{'（会员）' if vip else ''}")
        else:
            self.lbl_account.setText("未登录 · 只能浏览公开内容")
        self.btn_login.setVisible(not logged_in)
        self.btn_logout.setVisible(logged_in)

    def _build_about(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(22, 40, 22, 40)
        v.setSpacing(12)
        v.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        logo = LogoMark(46)
        v.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        name = QLabel("Lunara")
        name.setFont(font(24, 700))
        name.setStyleSheet(f"color: {THEME['text_main']};")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(name)

        ver = QLabel("v0.1.0 · PyQt6 深空主题实验版")
        ver.setObjectName("MetaText")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(ver)

        desc = QLabel("深空、星轨、月光。\n一个把夜晚还给耳朵的播放器。")
        desc.setObjectName("BodyText")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(desc)
        v.addStretch(1)
        return panel

    # ---------------- 导航 ----------------
    def switch(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self._nav_btns):
            b.setChecked(i == index)
