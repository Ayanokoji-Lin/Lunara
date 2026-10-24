"""专辑页模型。

实测（2026-10-24）：``/api/v1/album/{id}`` → ``{album, songs[]}``。
``album.publishTime`` 是毫秒时间戳，``artists`` 是合作歌手列表。
"""
from __future__ import annotations

import datetime as dt

from pydantic import Field

from .common import ArtistRef, StrictModel
from .song import Song


class AlbumInfo(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    artist: ArtistRef | None = None
    artists: tuple[ArtistRef, ...] = Field(default_factory=tuple)
    publish_time: int = Field(default=0, alias="publishTime")
    company: str = ""
    description: str | None = ""      # 实测：个别专辑没有简介，会是 null
    size: int = 0

    @property
    def artist_names(self) -> str:
        names = [item.name for item in self.artists if item.name]
        if not names and self.artist is not None:
            names = [self.artist.name]
        return " / ".join(names) or "未知歌手"

    @property
    def publish_year(self) -> int:
        if self.publish_time <= 0:
            return 0
        return dt.datetime.fromtimestamp(self.publish_time / 1000).year


class AlbumDetail(StrictModel):
    album: AlbumInfo
    songs: tuple[Song, ...] = Field(default_factory=tuple)
