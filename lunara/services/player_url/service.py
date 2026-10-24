"""直链编排。

决策顺序（与任务书一致，逐条可测）：

1. 读登录/会员态（服务端判定，不信前端）；
2. 官方音源：空 url / 无版权 / 需付费且非会员 / 试听且非会员 → 不可用（试听留作兜底）；
3. 降级 GD Studio：jymaster → hires → lossless → exhigh → higher → standard，单档最多 2 次；
4. 仍失败 → ``available=False`` + 回退官方试听；
5. 成功结果进缓存（TTL 提前 2 分钟）；
6. 无论成败都产 trace。
"""
from __future__ import annotations

import json
import time
from typing import Callable

from ...api.client import ApiClient
from ...api.core import logging as api_log
from ...api.errors import ErrorCode
from ..session import SessionService, SessionState
from .cache import UrlCache
from .providers import GdStudioAdapter, OfficialProvider
from .quality import chain_from
from .types import (
    ProviderResult,
    QualityLevel,
    ResolvedUrl,
    ResolveOutcome,
    ResolveTrace,
    UrlProvider,
    UrlSource,
)


class PlayerUrlService:
    """把「一个 song_id」变成「一个能播的 url」或「一个明确的失败原因」。"""

    def __init__(
        self,
        client: ApiClient,
        session: SessionService | None = None,
        *,
        official: UrlProvider | None = None,
        gdstudio: UrlProvider | None = None,
        cache: UrlCache | None = None,
        max_attempts: int = 2,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._session = session or SessionService(client)
        self._official: UrlProvider = official or OfficialProvider(client)
        self._gd: UrlProvider = gdstudio or GdStudioAdapter.from_env()
        self._cache = cache or UrlCache()
        self._max_attempts = max(1, max_attempts)
        self._clock = clock

    @property
    def session(self) -> SessionService:
        return self._session

    @property
    def cache(self) -> UrlCache:
        return self._cache

    async def aclose(self) -> None:
        """关掉 Provider 自建的连接池（官方源复用 ApiClient，不用管）。"""
        closer = getattr(self._gd, "aclose", None)
        if closer is not None:
            await closer()

    async def __aenter__(self) -> PlayerUrlService:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def resolve(
        self,
        song_id: int,
        level: QualityLevel | None = None,
        *,
        use_cache: bool = True,
    ) -> ResolveOutcome:
        """解析直链。

        Args:
            song_id: 曲目 id。
            level: 偏好档位，默认 standard（未登录时更高档也拿不到）。
            use_cache: 是否读缓存（写入总是发生，除非 TTL 已不足）。
        """
        preferred = level or QualityLevel.STANDARD
        started = time.monotonic()
        tried: list[str] = []

        if use_cache:
            cached = self._cache.get(song_id, preferred)
            if cached is not None:
                trace = self._trace(song_id, preferred, (), cached.source, started, None)
                self._log(trace)
                return ResolveOutcome(
                    available=True, result=cached, fallback=None, trace=trace, error=None
                )

        state = await self._session.state()

        # ---- ② 官方 ----
        tried.append(self._official.name.value)
        official_result = await self._official.resolve(song_id, preferred, state)

        fallback: ResolvedUrl | None = None
        fail_reason: str | None = None

        if official_result.url:
            resolved = self._to_resolved(official_result, self._official.name)
            if not official_result.trial:
                self._cache.put(song_id, resolved)
                return self._success(song_id, preferred, tried, resolved, started)
            fallback = resolved
            fail_reason = self._reason(official_result)
        else:
            fail_reason = self._reason(official_result)

        # ---- ③ 降级 GD Studio ----
        if self._gd.configured:
            tried.append(self._gd.name.value)
            gd_result = await self._resolve_gd(song_id, preferred, state)
            if gd_result is not None and gd_result.url:
                resolved = self._to_resolved(gd_result, self._gd.name)
                self._cache.put(song_id, resolved)
                return self._success(song_id, preferred, tried, resolved, started)
            if gd_result is not None:
                fail_reason = self._reason(gd_result) or fail_reason
        elif fail_reason is None:
            fail_reason = "gdstudio:not_configured"
        else:
            # 官方已经给了原因（比如 VIP_REQUIRED），再补上「降级源缺失」
            fail_reason = f"{fail_reason}+gdstudio:not_configured"

        # ---- ④ 全失败 ----
        trace = self._trace(
            song_id,
            preferred,
            tuple(dict.fromkeys(tried)),
            None,
            started,
            fail_reason or "gdstudio:not_configured",
        )
        self._log(trace)
        return ResolveOutcome(
            available=False,
            result=None,
            fallback=fallback,
            trace=trace,
            error=ErrorCode.URL_UNAVAILABLE,
        )

    # ------------------------------------------------------------------ #
    async def _resolve_gd(
        self, song_id: int, preferred: QualityLevel, state: SessionState
    ) -> ProviderResult | None:
        """逐档下降，单档最多 ``max_attempts`` 次（只对可重试错误重试）。

        Provider 可以自己实现 ``levels_for``（GD 只有 4 个 br 档，
        jymaster/hires/lossless 会合并），没实现就用通用降级链。
        """
        levels_for = getattr(self._gd, "levels_for", None)
        candidates: tuple[QualityLevel, ...] = (
            levels_for(preferred) if callable(levels_for) else chain_from(preferred)
        )

        last: ProviderResult | None = None
        for candidate in candidates:
            for attempt in range(1, self._max_attempts + 1):
                last = await self._gd.resolve(song_id, candidate, state)
                if last.url:
                    return last
                if not last.retryable or attempt >= self._max_attempts:
                    break
        return last

    def _success(
        self,
        song_id: int,
        preferred: QualityLevel,
        tried: list[str],
        resolved: ResolvedUrl,
        started: float,
    ) -> ResolveOutcome:
        trace = self._trace(
            song_id, preferred, tuple(dict.fromkeys(tried)), resolved.source, started, None
        )
        self._log(trace)
        return ResolveOutcome(
            available=True, result=resolved, fallback=None, trace=trace, error=None
        )

    @staticmethod
    def _to_resolved(result: ProviderResult, source: UrlSource) -> ResolvedUrl:
        assert result.url is not None  # 只在 url 非空时调用
        return ResolvedUrl(
            url=result.url,
            level=result.level,
            expires_at=result.expires_at,
            source=source,
            trial=result.trial,
        )

    @staticmethod
    def _reason(result: ProviderResult) -> str | None:
        if result.fail_reason is not None:
            return result.fail_reason.value
        return result.detail

    @staticmethod
    def _trace(
        song_id: int,
        level: QualityLevel,
        tried: tuple[str, ...],
        source: UrlSource | None,
        started: float,
        fail_reason: str | None,
    ) -> ResolveTrace:
        return ResolveTrace(
            song_id=song_id,
            level=level,
            tried_providers=tried,
            final_source=source,
            latency_ms=(time.monotonic() - started) * 1000,
            fail_reason=fail_reason,
        )

    @staticmethod
    def _log(trace: ResolveTrace) -> None:
        api_log.get_logger().info(json.dumps(trace.to_log(), ensure_ascii=False))
