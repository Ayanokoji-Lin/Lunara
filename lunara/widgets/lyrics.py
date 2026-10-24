"""Lunara · 歌词视图

实现要点（QSS 做不到的部分）：
- 每行是独立 QLabel，用动态属性 active 切换字号/颜色；
- 当前行通过 QPropertyAnimation 平滑滚动到视口垂直中心；
- 首尾用可伸缩 Spacer 撑开，保证第一句/最后一句也能居中；
- 点击任意行发出 lineClicked(ms)，由播放页 seek。
"""
from __future__ import annotations

import bisect

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme import THEME

LINE_H = 40
LINE_H_ACTIVE = 58


class _LyricLine(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, ms: int, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.ms = ms
        self.setObjectName("LyricLine")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(False)
        self.setFixedHeight(LINE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", False)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ms)
        super().mouseReleaseEvent(e)


class LyricView(QScrollArea):
    lineClicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setObjectName("LyricViewport")

        self._container = QWidget()
        self._container.setObjectName("LyricViewport")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(10, 0, 10, 0)
        self._vbox.setSpacing(0)

        self._top = QWidget()
        self._bottom = QWidget()
        for sp in (self._top, self._bottom):
            sp.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._vbox.addWidget(self._top)
        self._vbox.addStretch(0)
        self._vbox.addWidget(self._bottom)
        self.setWidget(self._container)

        self._lines: list[_LyricLine] = []
        self._times: list[int] = []
        self._index = -1

        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(460)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---------------- 数据 ----------------
    def set_lyrics(self, lines: list[tuple[int, str]]) -> None:
        for w in self._lines:
            self._vbox.removeWidget(w)
            # 先摘掉父级再 deleteLater：否则旧歌词会以「幽灵行」留在视口里，
            # 直到事件循环处理 DeferredDelete 才消失（换歌词瞬间能看到两列）。
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._lines.clear()
        self._times = [ms for ms, _ in lines]
        self._index = -1

        for i, (ms, text) in enumerate(lines):
            lbl = _LyricLine(ms, text)
            lbl.clicked.connect(self.lineClicked)
            self._vbox.insertWidget(i + 1, lbl)
            self._lines.append(lbl)
        self.verticalScrollBar().setValue(0)

    def clear(self) -> None:
        self.set_lyrics([])

    # ---------------- 播放位置 ----------------
    def set_position(self, ms: int) -> None:
        if not self._times:
            return
        idx = bisect.bisect_right(self._times, ms) - 1
        idx = max(0, min(idx, len(self._lines) - 1))
        if idx != self._index:
            self._set_index(idx)

    def _set_index(self, idx: int) -> None:
        old = self._index
        self._index = idx
        for i in (old, idx):
            if 0 <= i < len(self._lines):
                lbl = self._lines[i]
                active = i == idx
                lbl.setProperty("active", active)
                lbl.setFixedHeight(LINE_H_ACTIVE if active else LINE_H)
                lbl.style().unpolish(lbl)
                lbl.style().polish(lbl)
        self._vbox.activate()
        self._container.adjustSize()
        QTimer.singleShot(0, lambda: self._scroll_to(idx))

    def _scroll_to(self, idx: int) -> None:
        if not (0 <= idx < len(self._lines)):
            return
        lbl = self._lines[idx]
        target = lbl.y() + lbl.height() // 2 - self.viewport().height() // 2
        bar = self.verticalScrollBar()
        target = max(bar.minimum(), min(target, bar.maximum()))
        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.start()

    def resizeEvent(self, e) -> None:
        pad = max(0, self.viewport().height() // 2 - LINE_H_ACTIVE // 2)
        self._top.setFixedHeight(pad)
        self._bottom.setFixedHeight(pad)
        super().resizeEvent(e)
        if self._index >= 0:
            QTimer.singleShot(0, lambda: self._scroll_to(self._index))
