"""歌曲与搜索结果模型。

字段来源：2026-10-24 实测 ``/api/cloudsearch/pc`` 的 ``result.songs[*]``。
上游用短字段名（dt=时长毫秒、al=专辑、ar=歌手、alia=别名），这里做 alias 映射。
"""
from __future__ import annotations

from pydantic import Field

from .common import AlbumRef, ArtistRef, Privilege, StrictModel


class Song(StrictModel):
    id: int
    name: str
    duration_ms: int = Field(default=0, alias="dt")
    fee: int = 0
    album: AlbumRef | None = Field(default=None, alias="al")
    artists: tuple[ArtistRef, ...] = Field(default_factory=tuple, alias="ar")
    alias: tuple[str, ...] = Field(default_factory=tuple, alias="alia")
    mv_id: int = Field(default=0, alias="mv")
    popularity: float = Field(default=0.0, alias="pop")
    privilege: Privilege | None = None

    @property
    def duration_seconds(self) -> int:
        return round(self.duration_ms / 1000)

    @property
    def artist_names(self) -> str:
        return " / ".join(artist.name for artist in self.artists)

    @property
    def vip_only(self) -> bool:
        """``fee`` 1=VIP、4=购买专辑、8=低音质免费；只有 1/4 算会员门槛。"""
        return self.fee in (1, 4)


class SongSearchResult(StrictModel):
    """``type=1`` 的搜索结果。"""

    songs: tuple[Song, ...] = Field(default_factory=tuple)
    song_count: int = Field(default=0, alias="songCount")

    def __len__(self) -> int:
        return len(self.songs)
