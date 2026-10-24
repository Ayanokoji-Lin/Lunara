"""搜索（专辑 / 歌手 / 歌单）模型。

实测（2026-10-24，`/api/cloudsearch/pc`）：
- ``type=10`` → ``result.albums[]``：``{id,name,picUrl,artist,artists,size,publishTime}``
- ``type=100`` → ``result.artists[]``：``{id,name,picUrl,alias,albumSize,musicSize}``
- ``type=1000`` → ``result.playlists[]``：``{id,name,coverImgUrl,creator,playCount,trackCount}``

单曲（``type=1``）沿用 :class:`lunara.api.models.song.SongSearchResult`。
"""
from __future__ import annotations

from pydantic import Field

from .common import ArtistRef, StrictModel
from .playlist import PlaylistCreator


class ArtistHit(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    alias: tuple[str, ...] = ()
    album_size: int = Field(default=0, alias="albumSize")
    music_size: int = Field(default=0, alias="musicSize")


class AlbumHit(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    artist: ArtistRef | None = None
    artists: tuple[ArtistRef, ...] = ()
    size: int = 0
    publish_time: int = Field(default=0, alias="publishTime")

    @property
    def artist_name(self) -> str:
        if self.artist is not None:
            return self.artist.name
        if self.artists:
            return self.artists[0].name
        return ""


class PlaylistHit(StrictModel):
    id: int
    name: str
    cover_url: str = Field(default="", alias="coverImgUrl")
    creator: PlaylistCreator | None = None
    play_count: int = Field(default=0, alias="playCount")
    track_count: int = Field(default=0, alias="trackCount")

    @property
    def author(self) -> str:
        return self.creator.nickname if self.creator else ""


class ArtistSearchResult(StrictModel):
    artists: tuple[ArtistHit, ...] = ()
    artist_count: int = Field(default=0, alias="artistCount")


class AlbumSearchResult(StrictModel):
    albums: tuple[AlbumHit, ...] = ()
    album_count: int = Field(default=0, alias="albumCount")


class PlaylistSearchResult(StrictModel):
    playlists: tuple[PlaylistHit, ...] = ()
    playlist_count: int = Field(default=0, alias="playlistCount")
