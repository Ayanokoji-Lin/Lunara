"""直链服务出口。

UI 侧只需要::

    service = PlayerUrlService(get_client())
    outcome = await service.resolve(song_id, QualityLevel.LOSSLESS)
    if outcome.available:
        player.play(outcome.result.url)
    elif outcome.fallback:
        player.play(outcome.fallback.url, trial=True)
"""
from __future__ import annotations

from .cache import UrlCache
from .providers import GdStudioAdapter, OfficialProvider
from .quality import DEGRADE_CHAIN, chain_from
from .service import PlayerUrlService
from .types import (
    LEVEL_LABELS,
    ProviderResult,
    QualityLevel,
    ResolvedUrl,
    ResolveOutcome,
    ResolveTrace,
    UrlProvider,
    UrlSource,
)

__all__ = [
    "DEGRADE_CHAIN",
    "LEVEL_LABELS",
    "GdStudioAdapter",
    "OfficialProvider",
    "PlayerUrlService",
    "ProviderResult",
    "QualityLevel",
    "ResolvedUrl",
    "ResolveOutcome",
    "ResolveTrace",
    "UrlCache",
    "UrlProvider",
    "UrlSource",
    "chain_from",
]
