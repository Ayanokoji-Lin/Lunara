"""TTLCache 行为：过期、容量淘汰、命中统计。"""
from __future__ import annotations

from lunara.store.lru import TTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_get_returns_none_for_missing_key() -> None:
    cache: TTLCache[str, int] = TTLCache(capacity=2)
    assert cache.get("nope") is None
    assert cache.stats["misses"] == 1


def test_expires_after_ttl() -> None:
    clock = FakeClock()
    cache: TTLCache[str, int] = TTLCache(capacity=4, clock=clock)
    cache.set("k", 1, ttl=10)
    assert cache.get("k") == 1

    clock.advance(9.9)
    assert cache.get("k") == 1

    clock.advance(0.2)
    assert cache.get("k") is None
    assert len(cache) == 0


def test_lru_evicts_oldest() -> None:
    cache: TTLCache[str, int] = TTLCache(capacity=2)
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=60)
    cache.get("a")  # 刷新 a 的 LRU 位置
    cache.set("c", 3, ttl=60)

    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.stats["evictions"] == 1


def test_zero_ttl_is_not_stored() -> None:
    cache: TTLCache[str, int] = TTLCache(capacity=2)
    cache.set("k", 1, ttl=0)
    assert cache.get("k") is None


def test_purge_expired() -> None:
    clock = FakeClock()
    cache: TTLCache[str, int] = TTLCache(capacity=8, clock=clock)
    cache.set("a", 1, ttl=5)
    cache.set("b", 2, ttl=60)
    clock.advance(10)
    assert cache.purge_expired() == 1
    assert cache.get("b") == 2
