"""一条内联提示（不弹窗）。

用途：错误提示、下载完成提示、首次进入下载页的版权声明。
样式按 level 分三档，都用主题色，不引入新的视觉语言。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..theme import THEME
from .common import IconButton, font

LEVEL_STYLE = {
    "error": (THEME["danger"], "rgba(229, 72, 77, 0.12)", "rgba(229, 72, 77, 0.28)"),
    "warning": (THEME["text_main"], "rgba(245, 158, 11, 0.12)", "rgba(245, 158, 11, 0.30)"),
    "info": (THEME["text_sub"], "rgba(139, 92, 246, 0.10)", "rgba(139, 92, 246, 0.24)"),
}


class InlineBanner(QFrame):
    """内容区顶部的一条细提示。"""

    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InlineBanner")
        self.setVisible(False)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 6, 6)
        row.setSpacing(10)

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setFont(font(11))
        row.addWidget(self.label, 1)

        self.btn_action = IconButton("fa5s.check", THEME["text_sub"], 11, 24, "知道了")
        self.btn_action.clicked.connect(self._on_action)
        row.addWidget(self.btn_action)

        self.btn_close = IconButton("fa5s.times", THEME["text_dim"], 10, 24, "关闭")
        self.btn_close.clicked.connect(self.clear)
        row.addWidget(self.btn_close)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)
        self._last_text = ""

    # ------------------------------------------------------------------ #
    def show_message(
        self,
        text: str,
        *,
        level: str = "info",
        timeout_ms: int = 0,
        action_text: str = "",
    ) -> None:
        color, background, border = LEVEL_STYLE.get(level, LEVEL_STYLE["info"])
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {color}; background: transparent;")
        self.setStyleSheet(
            f"QFrame#InlineBanner {{ background: {background}; border: 1px solid {border};"
            f" border-radius: 8px; }}")
        self.btn_action.setVisible(bool(action_text))
        self.btn_action.setToolTip(action_text or "知道了")

        self._last_text = text
        self.setVisible(True)
        self._timer.stop()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)

    def clear(self) -> None:
        self._timer.stop()
        self._last_text = ""
        self.setVisible(False)
        self.dismissed.emit()

    def _on_action(self) -> None:
        self.clear()

    @property
    def text(self) -> str:
        return self._last_text
