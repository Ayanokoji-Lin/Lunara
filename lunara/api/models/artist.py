"""歌手页模型。

实测（2026-10-24）：``/api/v1/artist/{id}`` → ``{artist, hotSongs[50], more}``。
``artist.picUrl`` 是头像，``musicSize`` / ``albumSize`` 是作品数量。
"""
from __future__ import annotations

from pydantic import Field

from .common import ArtistRef, StrictModel
from .song import Song


class ArtistInfo(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    brief_desc: str = Field(default="", alias="briefDesc")
    album_size: int = Field(default=0, alias="albumSize")
    music_size: int = Field(default=0, alias="musicSize")
    alias: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def subtitle(self) -> str:
        """别名优先，没有就用作品数量拼一句。"""
        if self.alias:
            return " / ".join(self.alias)
        return f"歌手 · {self.music_size} 首 · {self.album_size} 张专辑"


class ArtistDetail(StrictModel):
    artist: ArtistInfo
    hot_songs: tuple[Song, ...] = Field(default_factory=tuple, alias="hotSongs")
    more: bool = False

    @property
    def artist_ref(self) -> ArtistRef:
        return ArtistRef(id=self.artist.id, name=self.artist.name)
