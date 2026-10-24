"""并发单飞（async 版）。

同一 key 上的并发协程只真正执行一次，其余协程等结果。
失败原样广播，不会把异常吞成空值；用 Event 而不是 Future，
避免「没人取结果」时 asyncio 打 unretrieved exception 警告。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _Call:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    value: Any = None
    error: BaseException | None = None


class AsyncSingleFlight(Generic[K, V]):
    """``await run(key, fn)`` → ``(value, shared)``，``shared=True`` 表示蹭了别人的结果。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._calls: dict[K, _Call] = {}

    async def run(self, key: K, fn: Callable[[], Awaitable[V]]) -> tuple[V, bool]:
        async with self._lock:
            call = self._calls.get(key)
            leader = call is None
            if leader:
                call = _Call()
                self._calls[key] = call

        assert call is not None  # leader 分支一定赋过值，这里只为类型收窄

        if not leader:
            await call.event.wait()
            if call.error is not None:
                raise call.error
            return call.value, True

        try:
            call.value = await fn()
            return call.value, False
        except BaseException as exc:  # noqa: BLE001 - 需要原样广播给等待者
            call.error = exc
            raise
        finally:
            async with self._lock:
                self._calls.pop(key, None)
            call.event.set()

    @property
    def inflight(self) -> int:
        return len(self._calls)
