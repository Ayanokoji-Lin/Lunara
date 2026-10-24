"""把协程丢到后台事件循环，主线程不阻塞。

Qt 主线程没有 asyncio loop，也不想为了几个请求引入 qasync 依赖，
所以起一个常驻后台线程跑 loop：``submit(coro)`` 返回标准
``concurrent.futures.Future``，谁想等就 ``.result()``，不想等就加回调。

    bridge = get_loop()
    future = bridge.submit(search_songs(client, "周杰伦"))
    result = future.result(timeout=10)          # 同步等（脚本里用）
    future.add_done_callback(on_done)           # 回调在 loop 线程执行
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Awaitable, TypeVar

T = TypeVar("T")

_START_TIMEOUT = 5.0
_SHUTDOWN_TIMEOUT = 3.0


class BackgroundLoop:
    """一条常驻线程 + 一个事件循环。"""

    def __init__(self, name: str = "lunara-api-loop") -> None:
        self._name = name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()
        if not self._ready.wait(timeout=_START_TIMEOUT):
            raise RuntimeError("后台事件循环启动超时")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        loop.call_soon(self._ready.set)
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

    # ------------------------------------------------------------------ #
    def submit(self, coro: Awaitable[T]) -> concurrent.futures.Future[T]:
        """提交协程，返回 ``concurrent.futures.Future``。"""
        self.start()
        loop = self._loop
        assert loop is not None
        return asyncio.run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]

    def run(self, coro: Awaitable[T], *, timeout: float | None = None) -> T:
        """提交并阻塞等结果（脚本 / 测试用，别在 Qt 主线程调）。"""
        return self.submit(coro).result(timeout=timeout)

    def shutdown(self, timeout: float = _SHUTDOWN_TIMEOUT) -> None:
        loop, thread = self._loop, self._thread
        self._loop = None
        self._thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=timeout)

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop


_default: BackgroundLoop | None = None
_default_lock = threading.Lock()


def get_loop() -> BackgroundLoop:
    """进程级默认后台循环。"""
    global _default
    with _default_lock:
        if _default is None:
            _default = BackgroundLoop()
            _default.start()
        return _default


def run_sync(coro: Awaitable[T], *, timeout: float | None = None) -> T:
    """便捷入口：``run_sync(search_songs(client, "周杰伦"))``。"""
    return get_loop().run(coro, timeout=timeout)


def shutdown() -> None:
    global _default
    with _default_lock:
        loop, _default = _default, None
    if loop is not None:
        loop.shutdown()


__all__ = ["BackgroundLoop", "get_loop", "run_sync", "shutdown"]
