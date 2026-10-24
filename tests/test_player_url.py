"""直链决策链：7 个核心场景 + 缓存 + trace。

Provider 全部用假实现，不碰网络；真上游行为由 tests/test_live.py 覆盖。
"""
from __future__ import annotations

import time
from typing import Any, Callable

from lunara.api.errors import ErrorCode
from lunara.services.player_url import (
    PlayerUrlService,
    ProviderResult,
    QualityLevel,
    UrlSource,
    chain_from,
)
from lunara.services.session import SessionState

ANON = SessionState(
    logged_in=False, vip=False, vip_type=0, nickname="", user_id=None, fetched_at=0.0
)
VIP = SessionState(
    logged_in=True, vip=True, vip_type=11, nickname="蝶恋", user_id=1, fetched_at=0.0
)


def full(level: QualityLevel = QualityLevel.STANDARD, url: str = "http://full.mp3") -> ProviderResult:
    return ProviderResult(url=url, level=level, expires_at=time.time() + 1200, trial=False)


def trial(level: QualityLevel = QualityLevel.STANDARD) -> ProviderResult:
    return ProviderResult(
        url="http://trial.mp3",
        level=level,
        expires_at=time.time() + 1200,
        trial=True,
        fail_reason=ErrorCode.VIP_REQUIRED,
    )


def missing(
    reason: ErrorCode = ErrorCode.NO_COPYRIGHT,
    level: QualityLevel = QualityLevel.STANDARD,
    *,
    retryable: bool = False,
) -> ProviderResult:
    return ProviderResult.fail(reason, level, retryable=retryable)


Entry = ProviderResult | Callable[[QualityLevel], ProviderResult] | list[ProviderResult]


class FakeProvider:
    def __init__(
        self,
        name: UrlSource,
        results: dict[Any, Entry] | None = None,
        *,
        configured: bool = True,
    ) -> None:
        self._name = name
        self._configured = configured
        self._results: dict[Any, Entry] = results or {}
        self.calls: list[QualityLevel] = []

    @property
    def name(self) -> UrlSource:
        return self._name

    @property
    def configured(self) -> bool:
        return self._configured

    async def resolve(self, song_id: int, level: QualityLevel, session: SessionState) -> ProviderResult:
        self.calls.append(level)
        entry = self._results.get(level, self._results.get("*"))
        if entry is None:
            return ProviderResult.fail(ErrorCode.URL_UNAVAILABLE, level)
        if callable(entry):
            return entry(level)
        if isinstance(entry, list):
            return entry.pop(0)
        return entry


class FakeSession:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    async def state(self, *, force: bool = False) -> SessionState:
        return self._state


def make_service(
    state: SessionState,
    official: FakeProvider,
    gd: FakeProvider,
    **kwargs: Any,
) -> PlayerUrlService:
    return PlayerUrlService(
        None,  # type: ignore[arg-type] - Provider 全注入，client 不会被用到
        FakeSession(state),
        official=official,
        gdstudio=gd,
        **kwargs,
    )


async def test_anonymous_plain_song_uses_official() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": full()})
    gd = FakeProvider(UrlSource.GD, {"*": full()})

    outcome = await make_service(ANON, official, gd).resolve(1)

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.OFFICIAL
    assert outcome.result.trial is False
    assert outcome.trace.tried_providers == ("official",)
    assert gd.calls == []  # 官方给了完整直链就不该再问第三方


async def test_anonymous_vip_song_falls_back_to_gd() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": trial()})
    gd = FakeProvider(UrlSource.GD, {"*": full(QualityLevel.EXHIGH)})

    outcome = await make_service(ANON, official, gd).resolve(1)

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.GD
    assert outcome.result.level is QualityLevel.EXHIGH
    assert outcome.trace.tried_providers == ("official", "gdstudio")


async def test_member_with_copyright_uses_official() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": full(QualityLevel.LOSSLESS)})
    gd = FakeProvider(UrlSource.GD, {"*": full()})

    outcome = await make_service(VIP, official, gd).resolve(1, QualityLevel.LOSSLESS)

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.OFFICIAL
    assert outcome.result.level is QualityLevel.LOSSLESS
    assert gd.calls == []


async def test_member_without_copyright_goes_to_gd() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": missing(ErrorCode.NO_COPYRIGHT)})
    gd = FakeProvider(UrlSource.GD, {"*": full()})

    outcome = await make_service(VIP, official, gd).resolve(1)

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.GD
    assert outcome.trace.tried_providers == ("official", "gdstudio")


async def test_official_empty_url_goes_to_gd() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": missing(ErrorCode.URL_UNAVAILABLE)})
    gd = FakeProvider(UrlSource.GD, {"*": full()})

    outcome = await make_service(ANON, official, gd).resolve(1)

    assert outcome.available is True
    assert outcome.result is not None
    assert outcome.result.source is UrlSource.GD


async def test_gd_degrades_level_by_level() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": trial()})
    gd = FakeProvider(
        UrlSource.GD,
        {QualityLevel.LOSSLESS: missing(), QualityLevel.EXHIGH: full(QualityLevel.EXHIGH)},
    )

    outcome = await make_service(ANON, official, gd).resolve(1, QualityLevel.LOSSLESS)

    assert gd.calls == [QualityLevel.LOSSLESS, QualityLevel.EXHIGH]
    assert outcome.result is not None
    assert outcome.result.level is QualityLevel.EXHIGH


async def test_gd_retries_retryable_failure_once() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": trial()})
    gd = FakeProvider(
        UrlSource.GD,
        {
            QualityLevel.STANDARD: [
                missing(ErrorCode.NETWORK, retryable=True),
                full(QualityLevel.STANDARD),
            ]
        },
    )

    outcome = await make_service(ANON, official, gd, max_attempts=2).resolve(1)

    assert gd.calls == [QualityLevel.STANDARD, QualityLevel.STANDARD]
    assert outcome.available is True


async def test_gd_all_levels_fail_falls_back_to_official_trial() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": trial()})
    gd = FakeProvider(UrlSource.GD, {"*": missing(ErrorCode.URL_UNAVAILABLE)})

    outcome = await make_service(ANON, official, gd).resolve(1, QualityLevel.LOSSLESS)

    assert outcome.available is False
    assert outcome.result is None
    assert outcome.error is ErrorCode.URL_UNAVAILABLE
    assert outcome.fallback is not None
    assert outcome.fallback.url == "http://trial.mp3"
    assert outcome.fallback.trial is True
    assert gd.calls == list(chain_from(QualityLevel.LOSSLESS))
    assert outcome.trace.fail_reason == ErrorCode.URL_UNAVAILABLE.value


async def test_gd_not_configured_is_reported_in_trace() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": trial()})
    gd = FakeProvider(UrlSource.GD, {}, configured=False)

    outcome = await make_service(ANON, official, gd).resolve(1)

    assert outcome.available is False
    assert outcome.trace.tried_providers == ("official",)
    assert outcome.trace.fail_reason is not None
    assert "gdstudio:not_configured" in outcome.trace.fail_reason
    assert outcome.fallback is not None  # 至少还能播试听


async def test_cache_hit_skips_providers() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": full()})
    gd = FakeProvider(UrlSource.GD, {"*": full()})
    service = make_service(ANON, official, gd)

    first = await service.resolve(1)
    second = await service.resolve(1)

    assert first.available and second.available
    assert len(official.calls) == 1
    assert second.trace.tried_providers == ()  # 命中缓存，没打任何 Provider


async def test_cache_can_be_bypassed() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": full()})
    service = make_service(ANON, official, FakeProvider(UrlSource.GD, {}))

    await service.resolve(1)
    await service.resolve(1, use_cache=False)

    assert len(official.calls) == 2


async def test_trace_contains_required_fields() -> None:
    official = FakeProvider(UrlSource.OFFICIAL, {"*": full()})
    outcome = await make_service(ANON, official, FakeProvider(UrlSource.GD, {})).resolve(42)

    payload = outcome.trace.to_log()
    assert payload["songId"] == 42
    assert payload["level"] == QualityLevel.STANDARD.value
    assert payload["finalSource"] == UrlSource.OFFICIAL.value
    assert payload["triedProviders"] == ["official"]
    assert payload["failReason"] is None
    assert isinstance(payload["latencyMs"], float)


def test_chain_from_preferred_level() -> None:
    assert [level.value for level in chain_from(QualityLevel.LOSSLESS)] == [
        "lossless",
        "exhigh",
        "higher",
        "standard",
    ]
    assert chain_from(QualityLevel.STANDARD) == (QualityLevel.STANDARD,)
    assert chain_from(QualityLevel.JYMASTER)[0] is QualityLevel.JYMASTER
