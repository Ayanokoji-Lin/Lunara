"""登录态与用户模型。

实测（2026-10-24，匿名）：``/api/nuser/account/get`` → ``{"code":200,"account":null,"profile":null}``；
``/api/v1/user/detail/{uid}`` 的 ``profile.vipType`` 为会员类型（0=非会员，11=黑胶/音乐包）。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class Account(StrictModel):
    id: int
    user_name: str = Field(default="", alias="userName")
    type: int = 0
    status: int = 0


class Profile(StrictModel):
    user_id: int = Field(default=0, alias="userId")
    nickname: str = ""
    avatar_url: str = Field(default="", alias="avatarUrl")
    vip_type: int = Field(default=0, alias="vipType")


class LoginStatus(StrictModel):
    """``/api/nuser/account/get`` 整包（``unwrap="none"``）。"""

    account: Account | None = None
    profile: Profile | None = None

    @property
    def logged_in(self) -> bool:
        return self.account is not None and self.profile is not None

    @property
    def vip_type(self) -> int:
        return self.profile.vip_type if self.profile else 0

    @property
    def vip(self) -> bool:
        return self.vip_type > 0
