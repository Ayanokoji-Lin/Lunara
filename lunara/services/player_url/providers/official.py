"""官方音源 Provider。

实测（2026-10-24，匿名 Cookie）：
- ``level`` 参数会被接受，但实际下发档位看 ``data[0].level``，匿名一律是 standard。
- 未登录时**连免费歌也带** ``freeTrialInfo``（45 秒），所以 trial 判定就是它是否为 null。
- ``expi=1200`` 秒，用它算 ``expires_at``。
"""
from __future__ import annotations

import time

from ....api.client import ApiClient
from ....api.errors import ApiError, ErrorCode
from ....api.modules.song import get_song_url
from ..types import ProviderResult, QualityLevel, UrlSource
from ...session import SessionState

#: 会员门槛：fee=1 会员、fee=4 付费专辑
PAID_FEES = (1, 4)


class OfficialProvider:
    """走 ``/api/song/enhance/player/url/v1``。"""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    @property
    def name(self) -> UrlSource:
        return UrlSource.OFFICIAL

    @property
    def configured(self) -> bool:
        return True

    async def resolve(
        self, song_id: int, level: QualityLevel, session: SessionState
    ) -> ProviderResult:
        try:
            item = await get_song_url(self._client, song_id, level.value)
        except ApiError as err:
            return ProviderResult.fail(
                err.code, level, detail=err.detail, retryable=err.retryable
            )

        if item is None:
            return ProviderResult.fail(ErrorCode.NO_COPYRIGHT, level, detail="上游未返回该曲目")
        if not item.playable:
            return ProviderResult.fail(
                ErrorCode.NO_COPYRIGHT, level, detail=f"item.code={item.code} 且 url 为空"
            )

        trial = item.trial
        fail_reason: ErrorCode | None = None
        if item.fee in PAID_FEES and not session.vip:
            trial = True
            fail_reason = ErrorCode.VIP_REQUIRED

        expires_at = time.time() + item.expi if item.expi > 0 else None
        return ProviderResult(
            url=item.url,
            level=QualityLevel.parse(item.level),
            expires_at=expires_at,
            trial=trial,
            fail_reason=fail_reason,
            detail=f"fee={item.fee} trial={trial}",
        )
