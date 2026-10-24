"""Lunara · 可点击跳转的进度条

QSlider 默认点击槽位只会按 pageStep 步进，必须拦截鼠标事件：
- 按下即定位（点击跳转）；
- 按住拖动持续跟随（拖拽），期间外部 position 更新被忽略，避免抖动；
- 松开才真正 seek（避免拖动过程中频繁解码）。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSlider


class SeekSlider(QSlider):
    seekRequested = pyqtSignal(int)   # 0..maximum 的比值，调用方换算成毫秒

    HANDLE = 11          # 与 QSS 中 handle 宽度保持一致

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setObjectName("SeekSlider")
        self.setRange(0, 1000)
        self.setSingleStep(1)
        self.setPageStep(20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTracking(True)
        self._dragging = False

    # ---------------- 内部换算 ----------------
    def _value_at(self, x: float) -> int:
        span = max(1.0, self.width() - self.HANDLE)
        ratio = (x - self.HANDLE / 2) / span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * self.maximum()))

    @property
    def dragging(self) -> bool:
        return self._dragging

    # ---------------- 事件拦截 ----------------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            self._dragging = True
            self.setSliderDown(True)
            self.setValue(self._value_at(e.position().x()))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._dragging:
            self.setValue(self._value_at(e.position().x()))
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._dragging:
            self._dragging = False
            self.setSliderDown(False)
            self.setValue(self._value_at(e.position().x()))
            self.seekRequested.emit(self.value())
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e) -> None:
        e.ignore()          # 滚轮不改变进度，避免误触

    # ---------------- 外部驱动 ----------------
    def set_progress(self, position_ms: int, duration_ms: int) -> None:
        if self._dragging or duration_ms <= 0:
            return
        self.blockSignals(True)
        self.setValue(int(position_ms / duration_ms * self.maximum()))
        self.blockSignals(False)
