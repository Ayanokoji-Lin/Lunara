"""登录 / 会员态。

规则：
- 会员态**查接口**判定（``/api/nuser/account/get`` 的 ``profile.vipType``），
  不信任任何前端声明，也不靠 Cookie 里有没有 MUSIC_U 猜。
- 结果只做 30 秒内存快照，不落盘、不进通用缓存层。
- 查失败一律降级成「未登录」：浏览必须可用，不能因为查状态失败就整页白掉。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from ..api.client import ApiClient
from ..api.errors import ApiError
from ..api.modules.user import get_login_status


@dataclass(frozen=True, slots=True)
class SessionState:
    logged_in: bool
    vip: bool
    vip_type: int
    nickname: str
    user_id: int | None
    fetched_at: float

    @property
    def age(self) -> float:
        return time.time() - self.fetched_at


ANONYMOUS = SessionState(
    logged_in=False, vip=False, vip_type=0, nickname="", user_id=None, fetched_at=0.0
)


class SessionService:
    """登录态查询 + 短快照。线程/协程安全（asyncio.Lock）。"""

    def __init__(self, client: ApiClient, *, ttl: float = 30.0) -> None:
        self._client = client
        self._ttl = ttl
        self._state: SessionState | None = None
        self._lock = asyncio.Lock()

    @property
    def cached(self) -> SessionState | None:
        return self._state

    def invalidate(self) -> None:
        self._state = None

    async def state(self, *, force: bool = False) -> SessionState:
        """取当前状态；30 秒内直接给快照。"""
        current = self._state
        if not force and current is not None and current.age < self._ttl:
            return current

        async with self._lock:
            current = self._state
            if not force and current is not None and current.age < self._ttl:
                return current
            self._state = await self._fetch()
            return self._state

    async def _fetch(self) -> SessionState:
        try:
            status = await get_login_status(self._client)
        except ApiError:
            # 查不到就按未登录处理：匿名 Cookie 仍能浏览
            return ANONYMOUS

        profile = status.profile
        return SessionState(
            logged_in=status.logged_in,
            vip=status.vip,
            vip_type=status.vip_type,
            nickname=profile.nickname if profile else "",
            user_id=profile.user_id if profile else None,
            fetched_at=time.time(),
        )
