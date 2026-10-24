"""后台事件循环与 Qt 桥接。

Qt 部分只验证「回调回到主线程」这一件事，不启动窗口。
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from lunara.services.async_bridge import BackgroundLoop


async def _double(value: int) -> int:
    await asyncio.sleep(0.01)
    return value * 2


async def _boom() -> int:
    raise RuntimeError("boom")


def test_run_blocks_until_done() -> None:
    loop = BackgroundLoop()
    try:
        assert loop.run(_double(21), timeout=5) == 42
    finally:
        loop.shutdown()


def test_submit_returns_future() -> None:
    loop = BackgroundLoop()
    try:
        future = loop.submit(_double(2))
        assert future.result(timeout=5) == 4
    finally:
        loop.shutdown()


def test_exception_propagates() -> None:
    loop = BackgroundLoop()
    try:
        with pytest.raises(RuntimeError):
            loop.run(_boom(), timeout=5)
    finally:
        loop.shutdown()


def test_loop_runs_on_worker_thread() -> None:
    loop = BackgroundLoop()
    seen: list[str] = []

    async def record() -> None:
        seen.append(threading.current_thread().name)

    try:
        loop.run(record(), timeout=5)
    finally:
        loop.shutdown()

    assert seen and seen[0] != threading.main_thread().name


def test_restart_after_shutdown() -> None:
    loop = BackgroundLoop()
    assert loop.run(_double(1), timeout=5) == 2
    loop.shutdown()
    assert loop.running is False
    assert loop.run(_double(2), timeout=5) == 4
    loop.shutdown()


# --------------------------------------------------------------------------- #
# Qt 桥接：需要 QCoreApplication 才能验证「回到主线程」
# --------------------------------------------------------------------------- #
def _spin_until(app: object, predicate: object, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()  # type: ignore[attr-defined]
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.005)
    raise AssertionError("等待回调超时")


def test_qt_bridge_calls_back_on_main_thread() -> None:
    QtCore = pytest.importorskip("PyQt6.QtCore")
    from lunara.services.qt_bridge import QtAsyncBridge

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    bridge = QtAsyncBridge()
    result: dict[str, object] = {}

    def on_success(value: object) -> None:
        result["value"] = value
        result["thread"] = threading.current_thread().name

    bridge.submit(_double(5), on_success=on_success)
    _spin_until(app, lambda: "value" in result)

    assert result["value"] == 10
    assert result["thread"] == threading.main_thread().name


def test_qt_bridge_routes_error() -> None:
    QtCore = pytest.importorskip("PyQt6.QtCore")
    from lunara.services.qt_bridge import QtAsyncBridge

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    bridge = QtAsyncBridge()
    captured: dict[str, object] = {}

    bridge.submit(
        _boom(),
        on_success=lambda value: captured.setdefault("value", value),
        on_error=lambda err: captured.setdefault("error", type(err).__name__),
    )
    _spin_until(app, lambda: "error" in captured or "value" in captured)

    assert captured.get("error") == "RuntimeError"
    assert "value" not in captured
