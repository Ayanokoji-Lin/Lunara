"""GD Studio 适配器：schema、档位映射、错误映射、与编排层的配合。

协议参考 ``Cadenza-Public/cadenza/core/gdstudio.py``，响应夹具是 2026-10-24 的真实回包。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from lunara.api.errors import ErrorCode
from lunara.services.player_url import PlayerUrlService, ProviderResult, QualityLevel, UrlSource
from lunara.services.player_url.providers.gdstudio import GdStudioAdapter
from lunara.services.player_url.quality import (
    gd_br_for,
    gd_levels_from,
    level_from_gd_br,
)
from lunara.services.session import SessionState

FIXTURES = Path(__file__).parent / "fixtures"
ANON = SessionState(
    logged_in=False, vip=False, vip_type=0, nickname="", user_id=None, fetched_at=0.0
)

Handler = Callable[[httpx.Request], httpx.Response]


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_adapter(handler: Handler) -> tuple[GdStudioAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GdStudioAdapter("https://music-api.gdstudio.xyz/api.php", client=client), client


# --------------------------------------------------------------------------- #
# schema / 档位映射
# --------------------------------------------------------------------------- #
async def test_parses_real_response() -> None:
    adapter, client = make_adapter(
        lambda request: httpx.Response(200, json=_fixture("gdstudio_url.json"))
    )
    try:
        result = await adapter.resolve(347230, QualityLevel.LOSSLESS, ANON)
    finally:
        await client.aclose()

    assert result.url is not None
    assert result.url.endswith(".flac")
    assert result.level is QualityLevel.LOSSLESS  # br=797 → lossless
    assert result.trial is False
    assert result.detail is not None and "br=797" in result.detail


async def test_request_params_are_the_documented_ones() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=_fixture("gdstudio_url.json"))

    adapter, client = make_adapter(handler)
    try:
        await adapter.resolve(347230, QualityLevel.JYMASTER, ANON)
    finally:
        await client.aclose()

    assert seen == {"types": "url", "source": "netease", "id": "347230", "br": "999"}


@pytest.mark.parametrize(
    ("level", "br"),
    [
        (QualityLevel.JYMASTER, 999),
        (QualityLevel.HIRES, 999),
        (QualityLevel.LOSSLESS, 999),
        (QualityLevel.EXHIGH, 320),
        (QualityLevel.HIGHER, 192),
        (QualityLevel.STANDARD, 128),
    ],
)
def test_br_mapping(level: QualityLevel, br: int) -> None:
    assert gd_br_for(level) == br


@pytest.mark.parametrize(
    ("br", "level"),
    [
        (918, QualityLevel.LOSSLESS),
        (797, QualityLevel.LOSSLESS),
        (320, QualityLevel.EXHIGH),
        (192, QualityLevel.HIGHER),
        (128, QualityLevel.STANDARD),
        (0, QualityLevel.STANDARD),
    ],
)
def test_level_from_actual_br(br: int, level: QualityLevel) -> None:
    assert level_from_gd_br(br) is level


def test_high_levels_are_deduped() -> None:
    """jymaster/hires/lossless 都是 br=999，只能请求一次。"""
    assert [level.value for level in gd_levels_from(QualityLevel.JYMASTER)] == [
        "jymaster",
        "exhigh",
        "higher",
        "standard",
    ]
    assert [level.value for level in gd_levels_from(QualityLevel.LOSSLESS)] == [
        "lossless",
        "exhigh",
        "higher",
        "standard",
    ]


# --------------------------------------------------------------------------- #
# 错误映射
# --------------------------------------------------------------------------- #
async def test_empty_url_is_failure_not_retryable() -> None:
    adapter, client = make_adapter(
        lambda request: httpx.Response(200, json=_fixture("gdstudio_empty.json"))
    )
    try:
        result = await adapter.resolve(0, QualityLevel.EXHIGH, ANON)
    finally:
        await client.aclose()

    assert result.url is None
    assert result.fail_reason is ErrorCode.URL_UNAVAILABLE
    assert result.retryable is False  # 空 url 换档才有意义，别原地重试


async def test_http_5xx_is_retryable() -> None:
    adapter, client = make_adapter(lambda request: httpx.Response(503, text="down"))
    try:
        result = await adapter.resolve(1, QualityLevel.STANDARD, ANON)
    finally:
        await client.aclose()

    assert result.fail_reason is ErrorCode.UPSTREAM_5XX
    assert result.retryable is True


async def test_network_error_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    adapter, client = make_adapter(handler)
    try:
        result = await adapter.resolve(1, QualityLevel.STANDARD, ANON)
    finally:
        await client.aclose()

    assert result.fail_reason is ErrorCode.NETWORK
    assert result.retryable is True


async def test_bad_json_is_parse_error() -> None:
    adapter, client = make_adapter(lambda request: httpx.Response(200, text="<html>"))
    try:
        result = await adapter.resolve(1, QualityLevel.STANDARD, ANON)
    finally:
        await client.aclose()

    assert result.fail_reason is ErrorCode.PARSE_ERROR
    assert result.retryable is False


async def test_rate_limited() -> None:
    adapter, client = make_adapter(lambda request: httpx.Response(429, text="slow"))
    try:
        result = await adapter.resolve(1, QualityLevel.STANDARD, ANON)
    finally:
        await client.aclose()

    assert result.fail_reason is ErrorCode.RATE_LIMITED
    assert result.retryable is False


async def test_disabled_adapter_reports_not_configured() -> None:
    adapter = GdStudioAdapter("")
    assert adapter.configured is False

    result = await adapter.resolve(1, QualityLevel.STANDARD, ANON)
    assert result.fail_reason is ErrorCode.URL_UNAVAILABLE
    assert result.detail == "gdstudio:not_configured"


# --------------------------------------------------------------------------- #
# 与编排层配合
# --------------------------------------------------------------------------- #
class _TrialOfficial:
    name = UrlSource.OFFICIAL
    configured = True

    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, song_id: int, level: QualityLevel, session: SessionState) -> ProviderResult:
        self.calls += 1
        return ProviderResult(
            url="http://trial.mp3",
            level=QualityLevel.STANDARD,
            trial=True,
            fail_reason=ErrorCode.VIP_REQUIRED,
        )


class _AnonSession:
    async def state(self, *, force: bool = False) -> SessionState:
        return ANON


async def test_service_uses_gd_for_anonymous_vip_song() -> None:
    official = _TrialOfficial()
    adapter, client = make_adapter(
        lambda request: httpx.Response(200, json=_fixture("gdstudio_url.json"))
    )
    try:
        service = PlayerUrlService(
            None,  # type: ignore[arg-type]
            _AnonSession(),
            official=official,
            gdstudio=adapter,
        )
        outcome = await service.resolve(347230, QualityLevel.JYMASTER)
    finally:
        await client.aclose()

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.GD
    # 请求 jymaster，实际拿到 br=797 → 如实标成 lossless，不吹
    assert outcome.result.level is QualityLevel.LOSSLESS
    assert outcome.result.trial is False
    assert outcome.trace.tried_providers == ("official", "gdstudio")
    assert official.calls == 1


async def test_service_tries_each_br_once_when_all_fail() -> None:
    official = _TrialOfficial()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params)["br"])
        return httpx.Response(200, json=_fixture("gdstudio_empty.json"))

    adapter, client = make_adapter(handler)
    try:
        service = PlayerUrlService(
            None,  # type: ignore[arg-type]
            _AnonSession(),
            official=official,
            gdstudio=adapter,
        )
        outcome = await service.resolve(347230, QualityLevel.JYMASTER)
    finally:
        await client.aclose()

    assert calls == ["999", "320", "192", "128"]  # 4 个不同 br，各一次
    assert outcome.available is False
    assert outcome.fallback is not None
    assert outcome.fallback.trial is True
