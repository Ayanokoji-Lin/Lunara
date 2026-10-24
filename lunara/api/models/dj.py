"""播客（电台）模型。

实测（2026-10-24）：``/api/personalized/djprogram`` → ``{code, result[], category}``。
``result[i]`` 是**单集**（不是电台）：``name`` 是单集标题，``program.mainSong`` 是音频，
``program.radio`` 是所属电台。单集 id 能直接走直链解析（实测走 GD 降级拿到完整音频）。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class DjMainSong(StrictModel):
    id: int
    name: str


class DjRadio(StrictModel):
    id: int
    name: str


class DjProgramBody(StrictModel):
    main_song: DjMainSong | None = Field(default=None, alias="mainSong")
    radio: DjRadio | None = None
    listener_count: int = Field(default=0, alias="listenerCount")


class DjProgram(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")
    program: DjProgramBody | None = None

    @property
    def song_id(self) -> int:
        return self.program.main_song.id if self.program and self.program.main_song else 0

    @property
    def song_name(self) -> str:
        if self.program and self.program.main_song:
            return self.program.main_song.name
        return self.name

    @property
    def radio_name(self) -> str:
        if self.program and self.program.radio:
            return self.program.radio.name
        return "星轨播客"


class DjRecommend(StrictModel):
    result: tuple[DjProgram, ...] = ()
    category: int | str = 0      # 实测是数字 4，个别场景是字符串
