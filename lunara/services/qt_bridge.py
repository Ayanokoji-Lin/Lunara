"""Qt 侧桥接：后台协程跑完 → 回主线程回调。

用法::

    self._bridge = QtAsyncBridge(self)
    self._bridge.submit(
        search_songs(client, text),
        on_success=self._show_results,
        on_error=self._show_error,
    )

回调一定在主线程执行，可以放心碰控件。
"""
from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from .async_bridge import BackgroundLoop, get_loop


class _Emitter(QObject):
    """只在主线程创建，跨线程 emit 时 Qt 会自动排队。"""

    done = pyqtSignal(str, object, object)  # token, value, error


class QtAsyncBridge(QObject):
    def __init__(self, parent: QObject | None = None, *, loop: BackgroundLoop | None = None) -> None:
        super().__init__(parent)
        self._loop = loop or get_loop()
        self._emitter = _Emitter(self)
        self._handlers: dict[str, tuple[Callable[[Any], None], Callable[[BaseException], None] | None]] = {}
        self._emitter.done.connect(self._deliver)

    def submit(
        self,
        coro: Awaitable[Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
    ) -> str:
        """提交协程，返回 token（可用于取消/去重）。"""
        token = uuid.uuid4().hex[:12]
        self._handlers[token] = (on_success, on_error)
        future = self._loop.submit(coro)
        future.add_done_callback(lambda done: self._emit(token, done))
        return token

    # ------------------------------------------------------------------ #
    def _emit(self, token: str, future: Any) -> None:
        """在后台 loop 线程执行；emit 后由 Qt 排队回主线程。"""
        try:
            if future.cancelled():
                self._emitter.done.emit(token, None, RuntimeError("任务已取消"))
                return
            error = future.exception()
            if error is not None:
                self._emitter.done.emit(token, None, error)
            else:
                self._emitter.done.emit(token, future.result(), None)
        except Exception as exc:  # noqa: BLE001 - 兜底，不能让回调线程崩
            self._emitter.done.emit(token, None, exc)

    def _deliver(self, token: str, value: Any, error: BaseException | None) -> None:
        """在主线程执行。"""
        handler = self._handlers.pop(token, None)
        if handler is None:
            return
        on_success, on_error = handler
        if error is None:
            on_success(value)
        elif on_error is not None:
            on_error(error)

    @property
    def pending(self) -> int:
        return len(self._handlers)
