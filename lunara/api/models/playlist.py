"""歌单详情模型。

实测（2026-10-24，`/api/v6/playlist/detail?id=3778678`）：
``playlist.{id,name,coverImgUrl,description,trackCount,playCount,creator.nickname,tags,tracks}``；
其中 ``tracks[*]`` 与搜索结果是同一套短字段（``al`` / ``ar`` / ``dt``），所以直接复用 :class:`Song`。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel
from .song import Song


class PlaylistCreator(StrictModel):
    # 实测：个别歌单的 creator.nickname 会是 null，别让整个响应挂掉
    nickname: str | None = ""
    user_id: int = Field(default=0, alias="userId")


class PlaylistDetail(StrictModel):
    id: int
    name: str
    cover_url: str = Field(default="", alias="coverImgUrl")
    description: str | None = ""   # 实测：私密歌单的 description 可能是 null
    track_count: int = Field(default=0, alias="trackCount")
    play_count: int = Field(default=0, alias="playCount")
    creator: PlaylistCreator | None = None
    tags: tuple[str, ...] = ()
    tracks: tuple[Song, ...] = ()

    @property
    def author(self) -> str:
        return (self.creator.nickname or "") if self.creator else ""


class PlaylistDetailResponse(StrictModel):
    playlist: PlaylistDetail | None = None
