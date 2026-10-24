"""首页 / 歌单 / 歌词三个模块：参数、解包、缓存、异常。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

import httpx
import pytest

from lunara.api.client import ApiClient
from lunara.api.core import crypto
from lunara.api.errors import ApiError, ErrorCode
from lunara.api.modules.lyric import get_lyric
from lunara.api.modules.personalized import get_new_songs, get_recommended_playlists
from lunara.api.modules.playlist import get_playlist_detail

FIXTURES = Path(__file__).parent / "fixtures"
Handler = Callable[[httpx.Request], httpx.Response]


async def _no_sleep(_seconds: float) -> None:
    return None


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def make_client(handler: Handler) -> ApiClient:
    return ApiClient(transport=httpx.MockTransport(handler), sleeper=_no_sleep)


def echo(fixture: str, seen: dict[str, Any] | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen["path"] = request.url.path
            seen["params"] = decode_params(request)
        return httpx.Response(200, json=_load(fixture))

    return handler


def decode_params(request: httpx.Request) -> dict[str, Any]:
    """参数在 POST body 里且被 eapi 加密，这里解开来看真实发出去的字段。

    明文结构是 ``path-36cd479b6b5-json-36cd479b6b5-md5``，取中间那段才是 JSON。
    """
    body = request.content.decode()
    raw = parse_qs(body)["params"][0]
    plain = crypto.eapi_decrypt(raw)
    return json.loads(plain.split(crypto.DIGEST_SEPARATOR, 2)[1])


async def test_playlist_detail_parses_and_caches() -> None:
    counter = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        return httpx.Response(200, json=_load("playlist_detail"))

    async with make_client(handler) as client:
        detail = await get_playlist_detail(client, 3778678)
        await get_playlist_detail(client, 3778678)

    assert detail.id == 3778678
    assert detail.name
    assert detail.tracks
    assert counter[0] == 1  # 详情缓存 10min，第二次不再打上游


async def test_playlist_detail_rejects_bad_input() -> None:
    async with make_client(echo("playlist_detail")) as client:
        with pytest.raises(ValueError):
            await get_playlist_detail(client, 0)
        with pytest.raises(ValueError):
            await get_playlist_detail(client, 1, track_limit=5000)


async def test_playlist_detail_missing_payload_is_parse_error() -> None:
    async with make_client(lambda request: httpx.Response(200, json={"code": 200})) as client:
        with pytest.raises(ApiError) as excinfo:
            await get_playlist_detail(client, 1)

    assert excinfo.value.code is ErrorCode.PARSE_ERROR


async def test_lyric_parses_text() -> None:
    async with make_client(echo("lyric")) as client:
        lyric = await get_lyric(client, 347230)

    assert lyric.text.startswith("[00:00")
    assert lyric.translation == ""


async def test_lyric_empty_is_not_an_error() -> None:
    body = {"code": 200, "lrc": {"lyric": ""}, "tlyric": {"lyric": ""}}
    async with make_client(lambda request: httpx.Response(200, json=body)) as client:
        lyric = await get_lyric(client, 1)

    assert lyric.text == ""


async def test_recommended_playlists_sends_expected_params() -> None:
    seen: dict[str, Any] = {}
    async with make_client(echo("personalized_playlist", seen)) as client:
        items = await get_recommended_playlists(client, limit=10)

    assert seen["path"].endswith("/eapi/api/personalized/playlist")
    assert seen["params"] == {"limit": 10, "total": True, "n": 1000}
    assert len(items) == 6  # 夹具就是 6 个
    assert items[0].name


async def test_new_songs_sends_expected_params() -> None:
    seen: dict[str, Any] = {}
    async with make_client(echo("personalized_newsong", seen)) as client:
        items = await get_new_songs(client, limit=5)

    assert seen["params"] == {"limit": 5, "areaId": 0, "type": "recommend"}
    assert items and items[0].song is not None


@pytest.mark.parametrize("limit", [0, 51])
async def test_limits_are_validated(limit: int) -> None:
    async with make_client(echo("personalized_playlist")) as client:
        with pytest.raises(ValueError):
            await get_recommended_playlists(client, limit=limit)
        with pytest.raises(ValueError):
            await get_new_songs(client, limit=limit)
