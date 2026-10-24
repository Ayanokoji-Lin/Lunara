"""Lunara · 设置页（左分类导航 + QStackedWidget）"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..theme import THEME
from ..widgets.common import Divider, font
from ..widgets.sidebar import LogoMark
from ..widgets.toggle import Switch
from .base import BasePage

NAV = ("播放", "音质", "下载", "关于")


class SettingsPage(BasePage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
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
        return self._panel([
            ("记忆播放位置", "下次启动时从上一次的进度继续播放", Switch(True)),
            ("淡入淡出", "切歌时做 300ms 的音量过渡", Switch(True)),
            ("桌面歌词", "在桌面上悬浮显示当前歌词", Switch(False)),
            ("播放页默认模式", "进入播放页时使用的展示方式",
             self._combo(["唱片 + 歌词", "纯歌词", "纯封面"], 0)),
        ])

    def _build_quality(self) -> QWidget:
        return self._panel([
            ("在线播放音质", "网络良好时建议选择「极高」", self._combo(
                ["标准 128k", "较高 192k", "极高 320k", "无损 FLAC"], 2)),
            ("下载音质", "下载到本地时使用的音质", self._combo(
                ["标准 128k", "较高 192k", "极高 320k", "无损 FLAC"], 3)),
            ("移动网络自动降级", "检测到流量网络时自动切换到标准音质", Switch(True)),
        ])

    def _build_download(self) -> QWidget:
        path = QLabel(r"D:\Music\Lunara")
        path.setStyleSheet(f"color: {THEME['text_sub']}; font-size: 11px;"
                           f" background: {THEME['bg_input']}; border-radius: 6px;"
                           f" padding: 5px 10px;")
        change = QPushButton("更改")
        change.setObjectName("GhostPill")
        change.setFixedHeight(30)
        change.setCursor(Qt.CursorShape.PointingHandCursor)
        box = QWidget()
        bh = QHBoxLayout(box)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        bh.addWidget(path)
        bh.addWidget(change)

        return self._panel([
            ("下载目录", "歌曲与封面会保存在该目录下", box),
            ("同时下载数量", "数量越多越占用带宽", self._combo(["2", "3", "5", "8"], 1)),
            ("下载完成后提示", "在右下角弹出通知", Switch(True)),
        ])

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
