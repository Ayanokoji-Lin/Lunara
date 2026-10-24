"""请求层行为：重试、错误映射、缓存、单飞。

全部用 httpx.MockTransport 打桩，不碰真网。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import pytest

from lunara.api.client import ApiClient
from lunara.api.endpoints import CLOUDSEARCH
from lunara.api.errors import ApiError, ErrorCode
from lunara.api.models.song import SongSearchResult
from lunara.api.modules.search import search_songs

FIXTURE = Path(__file__).parent / "fixtures" / "cloudsearch_songs.json"

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


async def _no_sleep(_seconds: float) -> None:
    return None


def _fixture_body() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_client(handler: Handler) -> ApiClient:
    """测试用客户端：mock 传输 + 不真的 sleep。"""
    return ApiClient(transport=httpx.MockTransport(handler), sleeper=_no_sleep)


def ok_handler(counter: list[int] | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if counter is not None:
            counter[0] += 1
        return httpx.Response(200, json=_fixture_body())

    return handler


async def test_success_parses_model() -> None:
    async with make_client(ok_handler()) as client:
        result = await search_songs(client, "周杰伦", limit=2)

    assert isinstance(result, SongSearchResult)
    assert len(result) == 2
    assert result.song_count > 0
    first = result.songs[0]
    assert first.name
    assert first.duration_seconds > 0
    assert first.artist_names
    assert first.album is not None


async def test_cookie_header_is_sent() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie", "")
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture_body())

    async with make_client(handler) as client:
        await client.call(CLOUDSEARCH, {"s": "x"}, model=SongSearchResult)

    assert "os=pc" in seen["cookie"]
    assert "/eapi/api/cloudsearch/pc" in seen["url"]


async def test_cache_hit_avoids_second_request() -> None:
    counter = [0]
    async with make_client(ok_handler(counter)) as client:
        await search_songs(client, "周杰伦", limit=2)
        await search_songs(client, "周杰伦", limit=2)
        assert client.cache.stats["hits"] == 1

    assert counter[0] == 1


async def test_cache_can_be_disabled() -> None:
    counter = [0]
    async with make_client(ok_handler(counter)) as client:
        await search_songs(client, "周杰伦", limit=2, use_cache=False)
        await search_songs(client, "周杰伦", limit=2, use_cache=False)

    assert counter[0] == 2


async def test_different_params_use_different_cache_slots() -> None:
    counter = [0]
    async with make_client(ok_handler(counter)) as client:
        await search_songs(client, "周杰伦", limit=2)
        await search_songs(client, "陈奕迅", limit=2)

    assert counter[0] == 2


async def test_network_error_retries_twice_then_raises() -> None:
    counter = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        raise httpx.ConnectError("boom", request=request)

    async with make_client(handler) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.NETWORK
    assert excinfo.value.retryable is True
    assert counter[0] == 3  # 首次 + 2 次重试


async def test_upstream_5xx_retries_once_then_succeeds() -> None:
    counter = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        if counter[0] == 1:
            return httpx.Response(503, text="upstream down")
        return httpx.Response(200, json=_fixture_body())

    async with make_client(handler) as client:
        result = await search_songs(client, "周杰伦", limit=2)

    assert counter[0] == 2
    assert len(result) == 2


async def test_rate_limited_is_not_retried() -> None:
    counter = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        return httpx.Response(429, text="slow down")

    async with make_client(handler) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.RATE_LIMITED
    assert counter[0] == 1


async def test_plain_text_body_is_parse_error() -> None:
    async with make_client(lambda request: httpx.Response(200, text="not json at all")) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.PARSE_ERROR
    assert excinfo.value.retryable is False


async def test_business_code_301_means_auth_required() -> None:
    async with make_client(
        lambda request: httpx.Response(200, json={"code": 301, "msg": "need login"})
    ) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.AUTH_REQUIRED
    assert excinfo.value.retryable is False


async def test_schema_mismatch_is_parse_error() -> None:
    body = {"code": 200, "result": {"songs": [{"id": "not-an-int", "name": None}]}}
    async with make_client(lambda request: httpx.Response(200, json=body)) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.PARSE_ERROR
    assert excinfo.value.detail


async def test_missing_unwrap_key_is_parse_error() -> None:
    async with make_client(
        lambda request: httpx.Response(200, json={"code": 200, "data": []})
    ) as client:
        with pytest.raises(ApiError) as excinfo:
            await search_songs(client, "周杰伦")

    assert excinfo.value.code is ErrorCode.PARSE_ERROR


async def test_single_flight_merges_concurrent_calls() -> None:
    counter = [0]

    async def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        await asyncio.sleep(0.05)  # 让第二个协程一定落进等待队列
        return httpx.Response(200, json=_fixture_body())

    async with make_client(handler) as client:
        first, second = await asyncio.gather(
            search_songs(client, "周杰伦", limit=2),
            search_songs(client, "周杰伦", limit=2),
        )

    assert counter[0] == 1  # 上游只被打了一次
    assert len(first) == len(second) == 2


async def test_single_flight_broadcasts_error() -> None:
    counter = [0]

    async def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        await asyncio.sleep(0.02)
        return httpx.Response(200, json={"code": 301})

    async with make_client(handler) as client:
        results = await asyncio.gather(
            search_songs(client, "周杰伦"),
            search_songs(client, "周杰伦"),
            return_exceptions=True,
        )

    assert counter[0] == 1
    assert all(isinstance(item, ApiError) for item in results)
