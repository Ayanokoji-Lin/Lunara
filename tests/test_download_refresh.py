"""刷新合并器：批量操作不能 O(n²)。

真实事故：清空 283 条已完成时，每删一条都触发一次列表重建（最多 80 个行控件），
主窗口还会每删一条重新扫描整个下载目录 → 界面卡死到闪退。
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from lunara.widgets.anim import Coalescer  # noqa: E402


def _spin(qt_app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        qt_app.processEvents()
        time.sleep(0.005)


def test_many_triggers_fire_once(qt_app) -> None:
    calls: list[int] = []
    coalescer = Coalescer(lambda: calls.append(1), delay_ms=50)

    for _ in range(50):
        coalescer.trigger()
    _spin(qt_app, 0.25)

    assert calls == [1], f"50 次触发只该回调 1 次，实际 {len(calls)} 次"


def test_trigger_after_fire_works_again(qt_app) -> None:
    calls: list[int] = []
    coalescer = Coalescer(lambda: calls.append(1), delay_ms=40)

    coalescer.trigger()
    _spin(qt_app, 0.2)
    coalescer.trigger()
    _spin(qt_app, 0.2)

    assert len(calls) == 2


def test_zero_delay_still_coalesces(qt_app) -> None:
    calls: list[int] = []
    coalescer = Coalescer(lambda: calls.append(1), delay_ms=0)

    for _ in range(10):
        coalescer.trigger()
    _spin(qt_app, 0.15)

    assert len(calls) == 1
