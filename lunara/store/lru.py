"""带 TTL 的 LRU 缓存。

- 用 ``time.monotonic()`` 计时，避免系统时钟跳变把条目算成「永不过期」。
- 读命中会刷新 LRU 顺序；过期条目在读取时惰性删除。
- 线程安全：Qt 里可能在 worker 线程取数据、主线程读缓存。
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """容量 + 过期时间的双向约束缓存。"""

    def __init__(self, capacity: int = 200, *, clock: Callable[[], float] = time.monotonic) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._clock = clock
        self._data: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at <= self._clock():
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: K, value: V, ttl: float) -> None:
        if ttl <= 0:
            return
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = _Entry(value=value, expires_at=self._clock() + ttl)
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)
                self.evictions += 1

    def delete(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def purge_expired(self) -> int:
        """主动清理过期条目，返回清掉的数量。"""
        now = self._clock()
        with self._lock:
            dead = [key for key, entry in self._data.items() if entry.expires_at <= now]
            for key in dead:
                del self._data[key]
            return len(dead)

    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
            }
