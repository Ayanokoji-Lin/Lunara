"""api 请求层：eapi 组包 → 上游 → 校验 → 缓存 → 结构化日志。

设计要点：
- 全异步。httpx.AsyncClient + asyncio 单飞，UI 侧用 ``lunara.services.async_bridge``
  把协程丢到后台事件循环，主线程不阻塞。
- 响应必须过 pydantic 模型，校验失败即 ``PARSE_ERROR``，不把脏数据往上抛。
- 缓存 key = ``path + 规范化参数``，同 key 并发由 :class:`AsyncSingleFlight` 合并。
- 重试只在 client 层做，业务层拿到的一定是「已经重试过的最终结果」。
"""
from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from typing import Any, Awaitable, Callable, Literal, Mapping, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..store.inflight import AsyncSingleFlight
from ..store.lru import TTLCache
from .core import crypto
from .core import logging as api_log
from .core.cookie import CookieProvider
from .endpoints import Endpoint
from .errors import ApiError, ErrorCode, RETRY_LIMITS

TModel = TypeVar("TModel", bound=BaseModel)

CacheKind = Literal["list", "detail", "none"]
UnwrapKind = Literal["result", "data", "none"]

DEFAULT_BASE_URL = "https://music.163.com"
DEFAULT_TIMEOUT = 10.0
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)

#: 缓存默认 TTL（秒）：列表 5min、详情 10min
DEFAULT_TTL: dict[CacheKind, float] = {"list": 300.0, "detail": 600.0, "none": 0.0}

_DETAIL_LIMIT = 512


async def _default_sleeper(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _backoff(attempt: int) -> float:
    """第 n 次重试前的等待：0.2 → 0.4 → 0.8，封顶 2s，加 0~100ms 抖动。"""
    return min(0.2 * (2 ** (attempt - 1)), 2.0) + random.uniform(0, 0.1)


def _looks_like_hex(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 32 or len(stripped) % 2:
        return False
    return all(char in "0123456789abcdefABCDEF" for char in stripped)


class ApiClient:
    """一个上游会话（含 Cookie、缓存、单飞表）。整个应用共用一个实例。

    用法::

        async with ApiClient() as client:
            result = await search_songs(client, "周杰伦")

    同一个 client 必须在同一个事件循环里用（后台桥接层保证这一点）。
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        cookie: CookieProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        cache: TTLCache[str, Any] | None = None,
        user_agent: str = DEFAULT_UA,
        referer: str = "https://music.163.com",
        sleeper: Callable[[float], Awaitable[None]] = _default_sleeper,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._cookie = cookie or CookieProvider()
        self._user_agent = user_agent
        self._referer = referer
        self._sleeper = sleeper
        self._cache: TTLCache[str, Any] = cache or TTLCache(capacity=200)
        self._flight: AsyncSingleFlight[str, Any] = AsyncSingleFlight()
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ApiClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    @property
    def cookie(self) -> CookieProvider:
        return self._cookie

    @property
    def cache(self) -> TTLCache[str, Any]:
        return self._cache

    # ------------------------------------------------------------------ #
    # 对外入口
    # ------------------------------------------------------------------ #
    async def call(
        self,
        endpoint: Endpoint,
        params: Mapping[str, Any] | None = None,
        *,
        model: type[TModel],
        unwrap: UnwrapKind = "result",
        cache: CacheKind = "none",
        ttl: float | None = None,
    ) -> TModel:
        """调一个接口并返回已校验的模型。

        Args:
            endpoint: 见 :mod:`lunara.api.endpoints`。
            params: 业务参数，会被 eapi 加密。
            model: 用于校验 ``unwrap`` 之后那层结构。
            unwrap: 从响应哪一层取数据；``none`` 表示整包。
            cache: ``list`` / ``detail`` / ``none``，决定是否走缓存与默认 TTL。
            ttl: 覆盖默认 TTL（秒）。

        Raises:
            ApiError: 网络、上游、解析任一环节失败。
        """
        payload = dict(params or {})
        key = f"{endpoint.path}|{crypto.canonical_json(payload)}"
        request_id = uuid.uuid4().hex[:16]
        started = time.monotonic()

        if cache != "none":
            hit = self._cache.get(key)
            if hit is not None:
                api_log.log_request(
                    request_id=request_id,
                    route=endpoint.path,
                    upstream="eapi",
                    status=200,
                    latency_ms=(time.monotonic() - started) * 1000,
                    cache_hit=True,
                )
                return hit  # type: ignore[no-any-return]

        try:
            value, shared = await self._flight.run(
                key, lambda: self._fetch(endpoint, payload, model, unwrap, cache, ttl, key)
            )
        except ApiError as err:
            err.request_id = err.request_id or request_id
            api_log.log_request(
                request_id=request_id,
                route=endpoint.path,
                upstream="eapi",
                status=err.status,
                latency_ms=(time.monotonic() - started) * 1000,
                cache_hit=False,
                error=err.code.value,
            )
            raise
        else:
            api_log.log_request(
                request_id=request_id,
                route=endpoint.path,
                upstream="eapi",
                status=200,
                latency_ms=(time.monotonic() - started) * 1000,
                cache_hit=shared,
            )
            return value

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    async def _fetch(
        self,
        endpoint: Endpoint,
        params: dict[str, Any],
        model: type[TModel],
        unwrap: UnwrapKind,
        cache: CacheKind,
        ttl: float | None,
        key: str,
    ) -> TModel:
        payload = await self._post_with_retry(endpoint.path, params)

        body: Any = payload if unwrap == "none" else payload.get(unwrap)
        if body is None:
            raise ApiError(
                ErrorCode.PARSE_ERROR,
                f"响应缺少 {unwrap} 字段",
                detail=api_log.truncate(json.dumps(payload, ensure_ascii=False)),
            )
        try:
            value = model.model_validate(body)
        except ValidationError as exc:
            raise ApiError(
                ErrorCode.PARSE_ERROR,
                "响应结构与模型不匹配",
                detail=api_log.truncate(str(exc)),
            ) from exc

        if cache != "none":
            self._cache.set(key, value, ttl if ttl is not None else DEFAULT_TTL[cache])
        return value

    async def _post_with_retry(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        encrypted = crypto.eapi_encrypt(path, params)
        attempt = 0
        while True:
            try:
                response = await self._http.post(
                    f"/eapi{path}",
                    data={"params": encrypted},
                    headers={
                        "User-Agent": self._user_agent,
                        "Referer": self._referer,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cookie": self._cookie.header(),
                    },
                )
            except httpx.TimeoutException as exc:
                error = ApiError(
                    ErrorCode.NETWORK, "请求超时", detail=f"{type(exc).__name__}: {exc}"
                )
            except httpx.TransportError as exc:
                error = ApiError(
                    ErrorCode.NETWORK, "网络不可达", detail=f"{type(exc).__name__}: {exc}"
                )
            else:
                error = self._classify(response)
                if error is None:
                    return self._decode(response, path)

            limit = RETRY_LIMITS[error.code]
            if attempt >= limit:
                raise error
            attempt += 1
            await self._sleeper(_backoff(attempt))

    @staticmethod
    def _classify(response: httpx.Response) -> ApiError | None:
        """把 HTTP 层异常翻成错误码；正常返回 ``None``。

        4xx 的语义：401/403 → 登录态问题；其余 4xx 说明我们发的请求本身不被接受
        （路径或参数不对），归到 PARSE_ERROR，不重试。
        """
        status = response.status_code
        if status < 400:
            return None
        if status == 429:
            return ApiError(ErrorCode.RATE_LIMITED, "触发限流", status=status)
        if status >= 500:
            return ApiError(ErrorCode.UPSTREAM_5XX, "上游服务异常", status=status)
        if status in (401, 403):
            return ApiError(ErrorCode.AUTH_REQUIRED, "登录态无效", status=status)
        return ApiError(
            ErrorCode.PARSE_ERROR,
            f"上游拒绝请求（HTTP {status}）",
            detail=api_log.truncate(response.text),
            status=status,
        )

    def _decode(self, response: httpx.Response, path: str) -> dict[str, Any]:
        """解析响应体；密文自动解包，业务 code 非 200 抛错。"""
        text = response.text.strip()
        if not text:
            raise ApiError(ErrorCode.PARSE_ERROR, "上游返回空响应", status=response.status_code)

        payload: Any
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            if not _looks_like_hex(text):
                raise ApiError(
                    ErrorCode.PARSE_ERROR,
                    "响应不是 JSON",
                    detail=api_log.truncate(text),
                    status=response.status_code,
                ) from None
            try:
                payload = json.loads(crypto.eapi_decrypt(text))
            except Exception as exc:  # noqa: BLE001 - 解包失败一律按解析错误
                raise ApiError(
                    ErrorCode.PARSE_ERROR,
                    "响应解密失败",
                    detail=f"{type(exc).__name__}: {exc}",
                    status=response.status_code,
                ) from exc

        if not isinstance(payload, dict):
            raise ApiError(ErrorCode.PARSE_ERROR, "响应顶层不是对象", status=response.status_code)

        code = payload.get("code")
        if code == 200:
            return payload

        raise self._business_error(code, payload, path, response.status_code)

    @staticmethod
    def _business_error(
        code: Any, payload: Mapping[str, Any], path: str, status: int
    ) -> ApiError:
        """业务 code → 错误码。

        - 301：未登录（上游用 301 表示需要登录态）
        - 404：仅直链接口代表「无版权」，其余路径代表路径写错
        - -460 / 429：风控
        """
        detail = api_log.truncate(json.dumps(payload, ensure_ascii=False))
        if code == 301:
            return ApiError(ErrorCode.AUTH_REQUIRED, "需要登录", detail=detail, status=status)
        if code in (-460, 429):
            return ApiError(ErrorCode.RATE_LIMITED, "触发风控", detail=detail, status=status)
        if code == 404 and "player/url" in path:
            return ApiError(ErrorCode.NO_COPYRIGHT, "无版权或已下架", detail=detail, status=status)
        if isinstance(code, int) and code >= 500:
            return ApiError(ErrorCode.UPSTREAM_5XX, f"上游返回 {code}", detail=detail, status=status)
        return ApiError(
            ErrorCode.PARSE_ERROR,
            f"上游返回异常 code={code}",
            detail=detail,
            status=status,
        )
