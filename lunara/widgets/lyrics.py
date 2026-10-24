"""Lunara · 歌词视图

实现要点（QSS 做不到的部分）：
- 每行是独立 QLabel，用动态属性 active 切换字号/颜色；
- 当前行用 QPropertyAnimation 平滑移动到视口垂直中心；
- 首尾留出半屏空白，保证第一句/最后一句也能居中；
- 点击任意行发出 lineClicked(ms)，由播放页 seek。

**为什么不用 QScrollArea**：滚动条 + ``setWidgetResizable`` 的组合下，
歌词一多（上百行）滚动值会落在布局还没算完的位置上，整屏变成空白。
这里改成自己控制容器位移：没有滚动条，位置只由「行高累计」算出来，可预期。
"""
from __future__ import annotations

import bisect

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..theme import THEME

LINE_H = 40
LINE_H_ACTIVE = 58


class _LyricLine(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, ms: int, text: str, trans: str = "",
                 parent: QWidget | None = None, *, tall: bool = False):
        if trans:
            # 译文用小一号、暗一档的字，塞在同一行里（富文本，不额外占行）
            super().__init__(
                f"{text}<br><span style='font-size:12px; color:{THEME['text_dim']}'>"
                f"{trans}</span>", parent)
        else:
            super().__init__(text, parent)
        self.ms = ms
        self.tall = bool(trans) or tall
        self.setObjectName("LyricLine")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(False)
        self.setFixedHeight(LINE_H + 20 if self.tall else LINE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", False)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ms)
        super().mouseReleaseEvent(e)


class LyricView(QWidget):
    lineClicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("LyricViewport")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setClipping = True

        self._container = QWidget(self)
        self._container.setObjectName("LyricViewport")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(10, 0, 10, 0)
        self._vbox.setSpacing(0)

        self._lines: list[_LyricLine] = []
        self._times: list[int] = []
        self._index = -1
        self._offset_px = 0.0
        self._offset_ms = 0

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---------------- 动画属性 ----------------
    def get_offset(self) -> float:
        return self._offset_px

    def set_offset_px(self, value: float) -> None:
        self._offset_px = float(value)
        self._container.move(0, -int(round(self._offset_px)))

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset_px)

    # ---------------- 数据 ----------------
    def set_lyrics(self, lines: list[tuple]) -> None:
        for widget in self._lines:
            self._vbox.removeWidget(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._lines.clear()

        self._times = [item[0] for item in lines]
        self._index = -1

        has_trans = any(len(item) > 2 and item[2] for item in lines)
        for item in lines:
            ms, text = item[0], item[1]
            trans = item[2] if len(item) > 2 else ""
            label = _LyricLine(ms, text, trans, tall=has_trans)
            label.clicked.connect(self.lineClicked)
            self._vbox.addWidget(label)
            self._lines.append(label)

        self._relayout()
        self.set_offset_px(0.0)

    def clear(self) -> None:
        self.set_lyrics([])

    # ---------------- 布局 ----------------
    def _relayout(self) -> None:
        """把容器高度算出来，首尾各留半屏，便于首句/末句居中。"""
        half = max(0, self.height() // 2)
        total = half * 2 + sum(label.height() for label in self._lines)
        self._container.setGeometry(0, -int(self._offset_px), self.width(), total)
        self._vbox.setContentsMargins(10, half, 10, half)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()
        if self._index >= 0:
            self._scroll_to(self._index, animate=False)

    # ---------------- 播放位置 ----------------
    def set_offset(self, ms: int) -> None:
        """歌词偏移：正数=歌词晚一点，负数=早一点。"""
        self._offset_ms = int(ms)
        self._index = -1

    def set_position(self, ms: int) -> None:
        if not self._times:
            return
        idx = bisect.bisect_right(self._times, ms + self._offset_ms) - 1
        idx = max(0, min(idx, len(self._lines) - 1))
        if idx != self._index:
            self._set_index(idx)

    def _set_index(self, idx: int) -> None:
        old = self._index
        self._index = idx
        for i in (old, idx):
            if 0 <= i < len(self._lines):
                label = self._lines[i]
                active = i == idx
                label.setProperty("active", active)
                base = LINE_H + 20 if getattr(label, "tall", False) else LINE_H
                label.setFixedHeight(base + 18 if active else base)
                label.style().unpolish(label)
                label.style().polish(label)
        self._relayout()
        QTimer.singleShot(0, lambda: self._scroll_to(idx, animate=True))

    def _scroll_to(self, idx: int, *, animate: bool) -> None:
        if not (0 <= idx < len(self._lines)):
            return
        # 用累计行高算中心，不依赖 label.y()（布局没跑完时它是旧值）
        top = self._vbox.contentsMargins().top()
        center = top + sum(label.height() for label in self._lines[:idx]) \
            + self._lines[idx].height() / 2
        target = center - self.height() / 2
        limit = max(0.0, self._container.height() - self.height())
        target = max(0.0, min(target, limit))

        self._anim.stop()
        if not animate:
            self.set_offset_px(target)
            return
        self._anim.setStartValue(self._offset_px)
        self._anim.setEndValue(target)
        self._anim.start()
