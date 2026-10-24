"""登录态：会员判定、30 秒快照、失败降级。"""
from __future__ import annotations

from typing import Any

from lunara.api.errors import ApiError, ErrorCode
from lunara.api.models.user import LoginStatus
from lunara.services.session import SessionService

ANON_PAYLOAD: dict[str, Any] = {"code": 200, "account": None, "profile": None}

VIP_PAYLOAD: dict[str, Any] = {
    "code": 200,
    "account": {"id": 12345, "userName": "138****0000", "type": 1, "status": 0},
    "profile": {"userId": 12345, "nickname": "蝶恋", "avatarUrl": "", "vipType": 11},
}

PLAIN_USER_PAYLOAD: dict[str, Any] = {
    "code": 200,
    "account": {"id": 999, "userName": "user", "type": 1, "status": 0},
    "profile": {"userId": 999, "nickname": "路人", "vipType": 0},
}


class FakeClient:
    def __init__(self, payloads: list[dict[str, Any] | Exception]) -> None:
        self._payloads = payloads
        self.calls = 0

    async def call(self, endpoint: Any, params: Any = None, **kwargs: Any) -> LoginStatus:
        payload = self._payloads[min(self.calls, len(self._payloads) - 1)]
        self.calls += 1
        if isinstance(payload, Exception):
            raise payload
        return LoginStatus.model_validate(payload)


async def test_anonymous_state() -> None:
    service = SessionService(FakeClient([ANON_PAYLOAD]))  # type: ignore[arg-type]
    state = await service.state()

    assert state.logged_in is False
    assert state.vip is False
    assert state.user_id is None


async def test_vip_state() -> None:
    service = SessionService(FakeClient([VIP_PAYLOAD]))  # type: ignore[arg-type]
    state = await service.state()

    assert state.logged_in is True
    assert state.vip is True
    assert state.vip_type == 11
    assert state.nickname == "蝶恋"
    assert state.user_id == 12345


async def test_logged_in_but_not_vip() -> None:
    service = SessionService(FakeClient([PLAIN_USER_PAYLOAD]))  # type: ignore[arg-type]
    state = await service.state()

    assert state.logged_in is True
    assert state.vip is False


async def test_snapshot_is_reused_within_ttl() -> None:
    client = FakeClient([ANON_PAYLOAD])
    service = SessionService(client, ttl=30.0)  # type: ignore[arg-type]

    await service.state()
    await service.state()

    assert client.calls == 1


async def test_force_refresh_bypasses_snapshot() -> None:
    client = FakeClient([ANON_PAYLOAD, VIP_PAYLOAD])
    service = SessionService(client, ttl=30.0)  # type: ignore[arg-type]

    first = await service.state()
    second = await service.state(force=True)

    assert first.vip is False
    assert second.vip is True
    assert client.calls == 2


async def test_invalidate_clears_snapshot() -> None:
    client = FakeClient([ANON_PAYLOAD, VIP_PAYLOAD])
    service = SessionService(client)  # type: ignore[arg-type]

    await service.state()
    service.invalidate()
    state = await service.state()

    assert state.vip is True
    assert client.calls == 2


async def test_failure_degrades_to_anonymous() -> None:
    """查状态失败不能把浏览功能拖死。"""
    error = ApiError(ErrorCode.NETWORK, "网络不可达")
    service = SessionService(FakeClient([error]))  # type: ignore[arg-type]

    state = await service.state()

    assert state.logged_in is False
    assert state.vip is False
