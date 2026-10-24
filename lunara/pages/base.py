"""Lunara · 页面基类

内容区统一包一层 QScrollArea，并把左右页边距做成“自适应居中”：
窗口拉宽时版心最宽 1490px，多出来的空间两侧均分。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..theme import THEME
from ..widgets.common import font
from ..widgets.icons import pixmap


class BasePage(QWidget):
    MAX_W = 1490
    PAD = 40

    def __init__(self, scrollable: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._top, self._bottom = 26, 40
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if scrollable:
            self.scroll = QScrollArea()
            self.scroll.setObjectName("PageScroll")
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.canvas = QWidget()
            self.canvas.setObjectName("PageCanvas")
            self.body = QVBoxLayout(self.canvas)
            self.body.setSpacing(24)
            self.scroll.setWidget(self.canvas)
            outer.addWidget(self.scroll)
        else:
            self.scroll = None
            self.canvas = self
            self.body = QVBoxLayout(self)
            self.body.setSpacing(16)

        self._sync_margins()

    def _sync_margins(self) -> None:
        m = max(self.PAD, (self.width() - self.MAX_W) // 2)
        self.body.setContentsMargins(m, self._top, m, self._bottom)

    def resizeEvent(self, e) -> None:
        self._sync_margins()
        super().resizeEvent(e)

    # ---- 常用页头 ----
    def add_page_header(self, title: str, subtitle: str = "") -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lbl = QLabel(title)
        lbl.setObjectName("PageTitle")
        lay.addWidget(lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("BodyText")
            lay.addWidget(sub)
        self.body.addWidget(box)
        return box


class EmptyPage(BasePage):
    """播客 / 视频 / 本地等占位页（视觉上仍保持沉浸感）。"""

    def __init__(self, title: str, hint: str = "", icon_name: str = "fa5s.moon",
                 parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.body.setSpacing(0)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 90, 0, 0)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._badge = QLabel()
        self._badge.setFixedSize(72, 72)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setPixmap(pixmap(icon_name, THEME["primary"], 30))
        self._badge.setStyleSheet(
            f"background: rgba(139, 92, 246, 0.10); border-radius: 36px;"
            f" border: 1px solid rgba(139, 92, 246, 0.22);")
        lay.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignHCenter)

        self._title = QLabel(title)
        self._title.setFont(font(18, 600))
        self._title.setStyleSheet(f"color: {THEME['text_main']};")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title)

        self._hint = QLabel(hint)
        self._hint.setObjectName("BodyText")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._hint)

        self.body.addStretch(1)
        self.body.addWidget(box)
        self.body.addStretch(2)

    def configure(self, title: str, hint: str = "",
                  icon_name: str = "fa5s.moon") -> None:
        self._title.setText(title)
        self._hint.setText(hint)
        self._badge.setPixmap(pixmap(icon_name, THEME["primary"], 30))
