"""首页推荐模型。

实测（2026-10-24）：
- ``/api/personalized/playlist`` → ``result[].{id,name,picUrl,playCount,copywriter,trackCount}``
- ``/api/personalized/newsong`` → ``result[].{id,name,picUrl,song}``，
  但 ``song`` 用的是**长字段名**（``album`` / ``artists`` / ``duration``），与搜索结果的短字段不同，
  所以这里单独建模型，不复用 :class:`Song`。
"""
from __future__ import annotations

from pydantic import Field

from .common import AlbumRef, ArtistRef, StrictModel


class RecommendedPlaylist(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    play_count: int = Field(default=0, alias="playCount")
    track_count: int = Field(default=0, alias="trackCount")
    copywriter: str = ""


class RecommendedPlaylists(StrictModel):
    result: tuple[RecommendedPlaylist, ...] = ()


class NewSongTrack(StrictModel):
    """``newsong.result[].song``：长字段名。"""

    id: int
    name: str
    duration: int = 0  # 毫秒
    fee: int = 0
    album: AlbumRef | None = None
    artists: tuple[ArtistRef, ...] = ()
    alias: tuple[str, ...] = ()

    @property
    def duration_seconds(self) -> int:
        return round(self.duration / 1000)

    @property
    def artist_names(self) -> str:
        return " / ".join(artist.name for artist in self.artists)


class NewSongEntry(StrictModel):
    id: int
    name: str = ""
    pic_url: str = Field(default="", alias="picUrl")
    song: NewSongTrack | None = None


class NewSongResult(StrictModel):
    result: tuple[NewSongEntry, ...] = ()
