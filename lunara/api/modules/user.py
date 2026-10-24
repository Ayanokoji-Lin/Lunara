"""登录态接口。

实测（2026-10-24）：``/api/nuser/account/get`` 匿名返回 ``account=null``，
登录后返回 ``account`` 与 ``profile``（含 ``vipType``）。
本接口结果**不进缓存层**（隐私），只在 ``services.session`` 里做 30 秒内存快照。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import ACCOUNT_STATUS
from ..models.user import LoginStatus


async def get_login_status(client: ApiClient) -> LoginStatus:
    """查当前登录态与会员态。未登录不报错，返回 ``logged_in=False``。"""
    return await client.call(ACCOUNT_STATUS, {}, model=LoginStatus, unwrap="none")
