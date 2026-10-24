"""真实上游冒烟测试：默认跳过，``LUNARA_LIVE=1`` 才跑。

用途：验证「crypto 组包 + 请求层 + 模型 + 直链决策」这条链在真网上仍然成立。
上游改协议时这里会先红。
"""
from __future__ import annotations

import os

import pytest

from lunara.api import ApiClient
from lunara.api.modules.search import search_songs
from lunara.services.player_url import PlayerUrlService, QualityLevel, UrlSource
from lunara.services.player_url.providers.gdstudio import GdStudioAdapter
from lunara.services.session import SessionService, SessionState

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("LUNARA_LIVE") != "1", reason="需要 LUNARA_LIVE=1"),
]

_ANON = SessionState(
    logged_in=False, vip=False, vip_type=0, nickname="", user_id=None, fetched_at=0.0
)


async def test_live_search_returns_songs() -> None:
    async with ApiClient() as client:
        result = await search_songs(client, "周杰伦", limit=3)

    assert result.song_count > 0
    assert len(result) == 3
    assert all(song.name for song in result.songs)
    assert all(song.artists for song in result.songs)


async def test_live_cache_hits_second_time() -> None:
    async with ApiClient() as client:
        await search_songs(client, "陈奕迅", limit=2)
        await search_songs(client, "陈奕迅", limit=2)
        assert client.cache.stats["hits"] >= 1


async def test_live_login_status_does_not_raise_when_anonymous() -> None:
    async with ApiClient() as client:
        state = await SessionService(client).state()

    # 本机没登录 → 未登录；登录了也不该崩
    assert isinstance(state.logged_in, bool)
    assert state.vip is False or state.vip is True


async def test_live_anonymous_vip_song_resolves_via_gd() -> None:
    """匿名态实测：官方只给 45s 试听 → 降级 GD 拿完整文件。"""
    async with ApiClient() as client:
        service = PlayerUrlService(client)
        try:
            outcome = await service.resolve(509781655, QualityLevel.LOSSLESS)
        finally:
            await service.aclose()

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.GD
    assert outcome.result.trial is False
    assert outcome.result.level is QualityLevel.LOSSLESS
    assert outcome.trace.tried_providers == ("official", "gdstudio")
    assert outcome.result.url.startswith("http")


async def test_live_gdstudio_adapter_returns_full_file() -> None:
    adapter = GdStudioAdapter.from_env()
    try:
        result = await adapter.resolve(347230, QualityLevel.LOSSLESS, _ANON)
    finally:
        await adapter.aclose()

    assert result.url is not None
    assert result.trial is False
    assert result.level is QualityLevel.LOSSLESS
