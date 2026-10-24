"""歌词模型。

实测（2026-10-24）：``/api/song/lyric`` → ``{lrc:{lyric}, tlyric:{lyric}, klyric:{lyric}}``，
``lrc.lyric`` 是标准 LRC 文本（``[mm:ss.xxx] 歌词``），纯音乐或未收录时为空串。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class LyricBody(StrictModel):
    lyric: str = ""
    version: int = 0


class LyricResponse(StrictModel):
    lrc: LyricBody = Field(default_factory=LyricBody)
    tlyric: LyricBody = Field(default_factory=LyricBody)

    @property
    def text(self) -> str:
        """原文歌词；没有就返回空串（调用方据此回退演示歌词）。"""
        return self.lrc.lyric

    @property
    def translation(self) -> str:
        return self.tlyric.lyric
