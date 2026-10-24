"""动效工具：effect 生命周期与 detach 的回归测试。

重点是 ``detach``：控件被删除前不摘 effect、不停动画，Qt 会直接段错误
（不是 Python 异常），所以这条必须钉住。
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from PyQt6.QtWidgets import QWidget  # noqa: E402

from lunara.widgets.anim import detach, fade_in, stagger  # noqa: E402


def _settle(qt_app, seconds: float = 0.35) -> None:
    end = time.time() + seconds
    while time.time() < end:
        qt_app.processEvents()
        time.sleep(0.005)


def test_fade_in_removes_effect_when_done(qt_app) -> None:
    widget = QWidget()
    fade_in(widget, duration=60)
    assert widget.graphicsEffect() is not None

    _settle(qt_app)
    assert widget.graphicsEffect() is None, "动画结束必须摘掉 effect，否则每帧多一次离屏合成"


def test_detach_stops_animation_and_effect(qt_app) -> None:
    widget = QWidget()
    fade_in(widget, duration=500)
    detach(widget)

    assert widget.graphicsEffect() is None


def test_stagger_limits_animation_count(qt_app) -> None:
    widgets = [QWidget() for _ in range(30)]
    stagger(widgets, step=1, duration=50, limit=5)

    animated = [w for w in widgets if w.graphicsEffect() is not None]
    assert len(animated) == 5, "超出 limit 的卡片直接显示，不该排队动画"
