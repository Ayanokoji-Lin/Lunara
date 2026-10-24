"""Lunara · 顶栏：搜索 + 用户区 + 窗口控制 + 拖动"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
)

from ..assets import circular, cover_pixmap
from ..theme import THEME
from .common import IconButton
from .icons import icon


class TopBar(QFrame):
    searchSubmitted = pyqtSignal(str)
    searchChanged = pyqtSignal(str)
    backClicked = pyqtSignal()
    forwardClicked = pyqtSignal()
    accountClicked = pyqtSignal()
    notifyClicked = pyqtSignal()
    minimizeRequested = pyqtSignal()
    maximizeRequested = pyqtSignal()
    closeRequested = pyqtSignal()

    def __init__(self, parent: QFrame | None = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(56)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 8, 0)
        lay.setSpacing(6)

        self.btn_back = IconButton("fa5s.chevron-left", THEME["text_sub"], 14, 30,
                                   "后退")
        self.btn_fwd = IconButton("fa5s.chevron-right", THEME["text_sub"], 14, 30,
                                  "前进")
        self.btn_back.clicked.connect(self.backClicked)
        self.btn_fwd.clicked.connect(self.forwardClicked)
        lay.addWidget(self.btn_back)
        lay.addWidget(self.btn_fwd)
        lay.addSpacing(8)

        # ---- 搜索框 ----
        self.search = QLineEdit()
        self.search.setObjectName("SearchInput")
        self.search.setPlaceholderText("搜索音乐、歌单、歌手")
        self.search.setFixedWidth(320)
        self.search.setClearButtonEnabled(False)
        act_search = self.search.addAction(icon("fa5s.search", THEME["text_dim"]),
                                          QLineEdit.ActionPosition.LeadingPosition)
        self._mic = self.search.addAction(icon("fa5s.microphone", THEME["text_dim"]),
                                          QLineEdit.ActionPosition.TrailingPosition)
        self._mic.setToolTip("听歌识曲")
        self._mic.triggered.connect(lambda: self.search.setPlaceholderText("正在聆听…"))
        self.search.returnPressed.connect(
            lambda: self.searchSubmitted.emit(self.search.text().strip()))
        self.search.textChanged.connect(self.searchChanged)
        lay.addWidget(self.search)

        lay.addStretch(1)

        # ---- 用户区 ----
        self.avatar = QToolButton()
        self.avatar.setObjectName("AvatarButton")
        self.avatar.setFixedSize(30, 30)
        self.avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        pm = cover_pixmap(77, 60, 268, radius=30)
        self.avatar.setIcon(QIcon(pm))
        self.avatar.setIconSize(QSize(30, 30))
        self.avatar.setToolTip("未登录 · 点击打开设置")
        self.avatar.clicked.connect(self.accountClicked)
        lay.addWidget(self.avatar)
        lay.addSpacing(4)

        self.btn_bell = IconButton("fa5s.bell", THEME["text_sub"], 15, 32, "通知")
        self.btn_bell.clicked.connect(self.notifyClicked)
        self.btn_cog = IconButton("fa5s.cog", THEME["text_sub"], 15, 32, "设置")
        lay.addWidget(self.btn_bell)
        lay.addWidget(self.btn_cog)

        divider = QFrame()
        divider.setObjectName("TopBarDivider")
        divider.setFixedSize(1, 18)
        lay.addSpacing(6)
        lay.addWidget(divider)
        lay.addSpacing(6)

        # ---- 窗口控制 ----
        self.btn_min = IconButton("fa5s.minus", THEME["text_sub"], 11, 36, "最小化")
        self.btn_max = IconButton("fa5s.window-maximize", THEME["text_sub"], 11, 36, "最大化")
        self.btn_close = IconButton("fa5s.times", THEME["text_sub"], 12, 36, "关闭",
                                    obj="CloseBtn")
        self.btn_min.clicked.connect(self.minimizeRequested)
        self.btn_max.clicked.connect(self.maximizeRequested)
        self.btn_close.clicked.connect(self.closeRequested)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedHeight(34)
            lay.addWidget(b)

        self.setMouseTracking(True)

    # ---- 无边框拖动：交给系统处理，避免自己算 globalPos 产生抖动 ----
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.maximizeRequested.emit()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def set_maximized(self, on: bool) -> None:
        self.btn_max.set_icon_name("fa5s.window-restore" if on else "fa5s.window-maximize")
        self.btn_max.setToolTip("还原" if on else "最大化")

    def set_account(self, nickname: str = "", *, vip: bool = False) -> None:
        """头像的 tooltip 跟着登录态走。"""
        if nickname:
            self.avatar.setToolTip(f"{nickname}{'（会员）' if vip else ''} · 点击打开设置")
        else:
            self.avatar.setToolTip("未登录 · 点击打开设置")

    def set_avatar(self, image: QPixmap | None) -> None:
        """设置真实头像；传 None 回到默认的月牙占位。"""
        if image is None or image.isNull():
            pm = cover_pixmap(77, 60, 268, radius=30)
            self.avatar.setIcon(QIcon(pm))
            return
        side = min(image.width(), image.height())
        cropped = image.copy((image.width() - side) // 2, (image.height() - side) // 2,
                             side, side)
        self.avatar.setIcon(QIcon(cropped.scaled(
            30, 30, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)))
