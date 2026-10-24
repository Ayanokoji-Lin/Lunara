"""通用动效工具：淡入、错峰入场、悬停进度。

原则：
- 只动**绘制层**（opacity / 绘制偏移），不动布局 —— 布局动画会触发整页重排，
  在 1000 行列表上直接掉帧。
- 动画结束立刻把 ``QGraphicsEffect`` 摘掉：挂着 effect 的控件会走离屏渲染，
  一直留着等于给每一帧加一次合成开销。
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer, pyqtProperty
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget

#: 统一缓动，避免各处缓动曲线不一致
EASE_OUT = QEasingCurve.Type.OutCubic
EASE_IN_OUT = QEasingCurve.Type.InOutCubic


def fade_in(widget: QWidget, *, duration: int = 220, delay: int = 0,
            start: float = 0.0, end: float = 1.0) -> QPropertyAnimation:
    """淡入。``delay`` 毫秒后开始，结束自动摘掉 effect。"""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(EASE_OUT)

    def _cleanup() -> None:
        # 动画对象挂在 widget 上，避免被 GC；effect 必须摘掉
        try:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)
        except RuntimeError:
            pass                      # 控件已经销毁（列表重建），忽略

    anim.finished.connect(_cleanup)
    widget._fade_anim = anim          # type: ignore[attr-defined]
    if delay > 0:
        # 用挂在控件上的 QTimer：控件销毁时定时器一起销毁，
        # 否则列表重建后旧定时器会去启动已删除控件的动画 → 槽里抛异常直接崩
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.timeout.connect(anim.start)
        timer.start(delay)
        widget._fade_timer = timer    # type: ignore[attr-defined]
    else:
        anim.start()
    return anim


def stagger(widgets: list[QWidget], *, step: int = 18, duration: int = 240,
            limit: int = 24) -> None:
    """错峰入场：第 i 个延迟 ``i * step`` 毫秒。超出 ``limit`` 的直接显示，
    否则长列表会变成「一张一张慢慢冒出来」。"""
    for i, widget in enumerate(widgets):
        if i >= limit:
            widget.setGraphicsEffect(None)
            continue
        fade_in(widget, duration=duration, delay=i * step)


class HoverTween(QObject):
    """0→1 的悬停进度，供 paintEvent 做插值（不触发重排）。"""

    def __init__(self, target: QWidget, *, duration: int = 140) -> None:
        super().__init__(target)
        self._target = target
        self._value = 0.0
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(EASE_OUT)

    def _get_value(self) -> float:
        return self._value

    def _set_value(self, value: float) -> None:
        self._value = float(value)
        self._target.update()

    value = pyqtProperty(float, fget=_get_value, fset=_set_value)

    def to(self, value: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(float(value))
        self._anim.start()


def detach(widget: QWidget) -> None:
    """删除控件前必须调用：先停动画、摘 effect，再让控件消失。

    否则 QPropertyAnimation 会继续往已被销毁的 QGraphicsEffect 写属性，
    在 Qt 里是直接段错误（不是 Python 异常，抓不到 traceback）。
    """
    for attr in ("_fade_anim", "_fade_timer"):
        obj = getattr(widget, attr, None)
        if obj is not None:
            try:
                obj.stop()
            except (RuntimeError, AttributeError):
                pass
    try:
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
    except RuntimeError:
        pass
