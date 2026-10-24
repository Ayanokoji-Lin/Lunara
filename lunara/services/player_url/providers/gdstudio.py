"""GD Studio 适配器（已接入）。

协议来自隔壁 ``Cadenza-Public/cadenza/core/gdstudio.py``，并逐条复核：

    GET https://music-api.gdstudio.xyz/api.php
        ?types=url&source=netease&id=<song_id>&br=<128|192|320|999>
        → {"url": str, "br": int, "size": int, "from": str}

实测（2026-10-24）：
- VIP 曲目也能拿到完整文件（27MB / br=918），不是 45 秒试听；
- 失败仍是 HTTP 200 + ``url=""``，必须按「无合法 url 即失败」处理；
- ``br`` 回包是实际码率（999 → 797/918），档位按区间反推；
- 没有 ``expi``，链接过期时间未知，缓存走 ``UrlCache`` 的默认 TTL。

配置：环境变量 ``LUNARA_GDSTUDIO_BASE`` 覆盖地址，``LUNARA_GDSTUDIO_DISABLED=1`` 关掉。
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import ValidationError

from ....api.errors import ApiError, ErrorCode
from ..quality import gd_br_for, gd_levels_from, level_from_gd_br
from ..types import ProviderResult, QualityLevel, UrlSource
from ...session import SessionState
from .schema import GdStudioUrlResponse

DEFAULT_BASE = "https://music-api.gdstudio.xyz/api.php"
SOURCE_NETEASE = "netease"

DEFAULT_TIMEOUT = 20.0  # 无损文件解析慢，比 eapi 的 10s 宽一点
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)


class GdStudioAdapter:
    """第三方音源：无需登录、能给 VIP 曲目完整直链。"""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = (DEFAULT_BASE if base_url is None else base_url).strip()
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    @classmethod
    def from_env(cls) -> GdStudioAdapter:
        """读环境变量构造：默认启用，``LUNARA_GDSTUDIO_DISABLED=1`` 时禁用。"""
        if os.environ.get("LUNARA_GDSTUDIO_DISABLED") == "1":
            return cls(base_url="")
        return cls(os.environ.get("LUNARA_GDSTUDIO_BASE", DEFAULT_BASE))

    # ------------------------------------------------------------------ #
    @property
    def name(self) -> UrlSource:
        return UrlSource.GD

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def levels_for(self, preferred: QualityLevel) -> tuple[QualityLevel, ...]:
        """GD 只有 4 个 br 档，高码率三档会合并，避免重复请求同一份文件。"""
        return gd_levels_from(preferred)

    async def resolve(
        self, song_id: int, level: QualityLevel, session: SessionState
    ) -> ProviderResult:
        if not self.configured:
            return ProviderResult.fail(
                ErrorCode.URL_UNAVAILABLE, level, detail="gdstudio:not_configured"
            )

        br = gd_br_for(level)
        try:
            payload = await self._fetch(song_id, br)
        except ApiError as err:
            return ProviderResult.fail(
                err.code, level, detail=err.detail, retryable=err.retryable
            )

        if not payload.playable:
            return ProviderResult.fail(
                ErrorCode.URL_UNAVAILABLE, level, detail=f"gdstudio:empty_url(br={br})"
            )

        return ProviderResult(
            url=payload.url.strip(),
            level=level_from_gd_br(payload.br),
            expires_at=None,  # 上游不给 expi
            trial=False,
            detail=f"br={payload.br} size={payload.size} from={payload.from_}",
        )

    # ------------------------------------------------------------------ #
    async def _fetch(self, song_id: int, br: int) -> GdStudioUrlResponse:
        client = self._get_client()
        params: dict[str, Any] = {
            "types": "url",
            "source": SOURCE_NETEASE,
            "id": str(song_id),
            "br": br,
        }
        try:
            response = await client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise ApiError(ErrorCode.NETWORK, "GD Studio 请求超时", detail=str(exc)) from exc
        except httpx.TransportError as exc:
            raise ApiError(ErrorCode.NETWORK, "GD Studio 不可达", detail=str(exc)) from exc

        status = response.status_code
        if status == 429:
            raise ApiError(ErrorCode.RATE_LIMITED, "GD Studio 限流", status=status)
        if status >= 500:
            raise ApiError(ErrorCode.UPSTREAM_5XX, "GD Studio 服务异常", status=status)
        if status >= 400:
            raise ApiError(
                ErrorCode.PARSE_ERROR, f"GD Studio 拒绝请求（HTTP {status}）", status=status
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError(
                ErrorCode.PARSE_ERROR, "GD Studio 返回的不是 JSON", detail=str(exc)
            ) from exc
        if not isinstance(payload, dict):
            raise ApiError(ErrorCode.PARSE_ERROR, "GD Studio 返回顶层不是对象")

        try:
            return GdStudioUrlResponse.model_validate(payload)
        except ValidationError as exc:
            raise ApiError(
                ErrorCode.PARSE_ERROR, "GD Studio 响应结构与 schema 不符", detail=str(exc)
            ) from exc

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": UA, "Accept": "application/json, */*"},
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        """只关自己创建的连接池；外部注入的由调用方负责。"""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None
