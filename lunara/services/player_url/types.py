"""直链服务的类型契约。

UI 只认 :class:`ResolveOutcome`：能不能播、播哪个、为什么不能播、试了几家。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from ...api.errors import ErrorCode
from ..session import SessionState


class QualityLevel(str, Enum):
    """音质档位，值与上游 ``level`` 参数一致（实测可用）。"""

    STANDARD = "standard"
    HIGHER = "higher"
    EXHIGH = "exhigh"
    LOSSLESS = "lossless"
    HIRES = "hires"
    JYMASTER = "jymaster"

    @classmethod
    def parse(cls, value: str | None) -> QualityLevel:
        """上游回什么就认什么；认不出按 standard（宁可低，不要错）。"""
        try:
            return cls(value or "")
        except ValueError:
            return cls.STANDARD

    @property
    def label(self) -> str:
        return LEVEL_LABELS[self]


LEVEL_LABELS: dict[QualityLevel, str] = {
    QualityLevel.STANDARD: "标准",
    QualityLevel.HIGHER: "较高",
    QualityLevel.EXHIGH: "极高",
    QualityLevel.LOSSLESS: "无损",
    QualityLevel.HIRES: "Hi-Res",
    QualityLevel.JYMASTER: "超清母带",
}


class UrlSource(str, Enum):
    OFFICIAL = "official"
    GD = "gdstudio"


@dataclass(frozen=True, slots=True)
class ResolvedUrl:
    """一个可直接交给播放器的直链。"""

    url: str
    level: QualityLevel
    expires_at: float | None
    source: UrlSource
    trial: bool


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """单个 Provider 的一次尝试结果。"""

    url: str | None
    level: QualityLevel
    expires_at: float | None = None
    trial: bool = False
    fail_reason: ErrorCode | None = None
    retryable: bool = False
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.url)

    @classmethod
    def fail(
        cls,
        reason: ErrorCode,
        level: QualityLevel = QualityLevel.STANDARD,
        *,
        detail: str | None = None,
        retryable: bool = False,
    ) -> ProviderResult:
        return cls(url=None, level=level, fail_reason=reason, retryable=retryable, detail=detail)


@dataclass(frozen=True, slots=True)
class ResolveTrace:
    """一次解析的完整轨迹，用于日志与排障。"""

    song_id: int
    level: QualityLevel
    tried_providers: tuple[str, ...]
    final_source: UrlSource | None
    latency_ms: float
    fail_reason: str | None

    def to_log(self) -> dict[str, object]:
        return {
            "songId": self.song_id,
            "level": self.level.value,
            "triedProviders": list(self.tried_providers),
            "finalSource": self.final_source.value if self.final_source else None,
            "latencyMs": round(self.latency_ms, 1),
            "failReason": self.fail_reason,
        }


@dataclass(frozen=True, slots=True)
class ResolveOutcome:
    """给 UI 的最终结果。

    ``available=False`` 时若 ``fallback`` 有值，UI 可以播它（试听片段），
    并在界面上标注「试听」。
    """

    available: bool
    result: ResolvedUrl | None
    fallback: ResolvedUrl | None
    trace: ResolveTrace
    error: ErrorCode | None


@runtime_checkable
class UrlProvider(Protocol):
    """新增音源时实现这个协议即可，编排层不用改。"""

    @property
    def name(self) -> UrlSource: ...

    @property
    def configured(self) -> bool: ...

    async def resolve(
        self, song_id: int, level: QualityLevel, session: SessionState
    ) -> ProviderResult: ...
