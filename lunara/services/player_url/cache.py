"""直链缓存。

key = ``songId:level:source``，TTL = ``min(expiresAt - now - 120s, 15min)``。
提前 2 分钟失效，避免「刚拿到就过期」导致播放器播到一半断流。
"""
from __future__ import annotations

import time
from typing import Callable

from ...store.lru import TTLCache
from .types import QualityLevel, ResolvedUrl, UrlSource


class UrlCache:
    """按 (song, level, source) 缓存直链。"""

    def __init__(
        self,
        capacity: int = 500,
        *,
        safety_margin: float = 120.0,
        ttl_cap: float = 900.0,
        default_ttl: float = 300.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._cache: TTLCache[str, ResolvedUrl] = TTLCache(capacity=capacity)
        self._safety_margin = safety_margin
        self._ttl_cap = ttl_cap
        self._default_ttl = default_ttl
        self._clock = clock

    @staticmethod
    def key(song_id: int, level: QualityLevel, source: UrlSource) -> str:
        return f"{song_id}:{level.value}:{source.value}"

    def get(self, song_id: int, level: QualityLevel) -> ResolvedUrl | None:
        """按 official → gdstudio 的顺序找，谁有就返回谁。"""
        for source in (UrlSource.OFFICIAL, UrlSource.GD):
            hit = self._cache.get(self.key(song_id, level, source))
            if hit is not None:
                return hit
        return None

    def put(self, song_id: int, result: ResolvedUrl) -> bool:
        """写入；TTL 已不足（或已过期）则不写，返回是否写入。"""
        ttl = self._ttl_for(result)
        if ttl <= 0:
            return False
        self._cache.set(self.key(song_id, result.level, result.source), result, ttl)
        return True

    def _ttl_for(self, result: ResolvedUrl) -> float:
        if result.expires_at is None:
            return self._default_ttl
        remaining = result.expires_at - self._clock() - self._safety_margin
        if remaining <= 0:
            return 0.0
        return min(remaining, self._ttl_cap)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def stats(self) -> dict[str, int]:
        return self._cache.stats
