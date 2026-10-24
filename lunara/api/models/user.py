"""登录态与用户模型。

实测（2026-10-24，匿名）：``/api/nuser/account/get`` → ``{"code":200,"account":null,"profile":null}``；
``/api/v1/user/detail/{uid}`` 的 ``profile.vipType`` 为会员类型（0=非会员，11=黑胶/音乐包）。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel
from .playlist import PlaylistCreator


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


#: 我喜欢的音乐是一个特殊歌单，``specialType`` 固定为 5
LIKE_SPECIAL_TYPE = 5


class UserPlaylist(StrictModel):
    """``/api/user/playlist`` 里的一项（实测 2026-10-24，登录态）。"""

    id: int
    name: str
    cover_url: str = Field(default="", alias="coverImgUrl")
    track_count: int = Field(default=0, alias="trackCount")
    play_count: int = Field(default=0, alias="playCount")
    special_type: int = Field(default=0, alias="specialType")
    subscribed: bool = False
    creator: PlaylistCreator | None = None

    @property
    def author(self) -> str:
        return self.creator.nickname if self.creator else ""

    @property
    def is_liked(self) -> bool:
        return self.special_type == LIKE_SPECIAL_TYPE

    @property
    def is_collected(self) -> bool:
        """收藏来的（而不是自己建的）。"""
        return self.subscribed or self.special_type != 0


class UserPlaylistsResponse(StrictModel):
    playlist: tuple[UserPlaylist, ...] = ()
    more: bool = False
