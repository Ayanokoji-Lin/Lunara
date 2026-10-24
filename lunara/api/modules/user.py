"""登录态接口。

实测（2026-10-24）：``/api/nuser/account/get`` 匿名返回 ``account=null``，
登录后返回 ``account`` 与 ``profile``（含 ``vipType``）。
本接口结果**不进缓存层**（隐私），只在 ``services.session`` 里做 30 秒内存快照。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import ACCOUNT_STATUS, USER_PLAYLIST
from ..models.user import LoginStatus, UserPlaylistsResponse

MAX_LIMIT = 1000


async def get_login_status(client: ApiClient) -> LoginStatus:
    """查当前登录态与会员态。未登录不报错，返回 ``logged_in=False``。"""
    return await client.call(ACCOUNT_STATUS, {}, model=LoginStatus, unwrap="none")


async def get_user_playlists(
    client: ApiClient,
    uid: int,
    *,
    limit: int = 100,
    offset: int = 0,
    use_cache: bool = True,
) -> UserPlaylistsResponse:
    """取某个用户的歌单（含「我喜欢的音乐」这个 specialType=5 的特殊项）。

    实测（2026-10-24，登录态）：返回 ``playlist[]`` 与 ``more``；
    匿名请求也能拿到公开歌单，但私密歌单需要登录。

    Raises:
        ValueError: uid 非法或分页参数越界。
    """
    if uid <= 0:
        raise ValueError("uid 必须为正整数")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit 必须在 1–{MAX_LIMIT} 之间")
    if offset < 0:
        raise ValueError("offset 不能为负")

    return await client.call(
        USER_PLAYLIST,
        {"uid": uid, "limit": limit, "offset": offset},
        model=UserPlaylistsResponse,
        unwrap="none",
        cache="detail" if use_cache else "none",
    )
