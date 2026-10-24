"""歌词接口。

实测（2026-10-24）：``/api/song/lyric?id=<id>&lv=-1&kv=-1&tv=-1``
``lv/kv/tv = -1`` 表示要原文 / 逐字 / 翻译三种；我们只用原文，翻译留作后续。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import LYRIC
from ..models.lyric import LyricResponse


async def get_lyric(client: ApiClient, song_id: int, *, use_cache: bool = True) -> LyricResponse:
    """取歌词。无歌词时 ``lrc.lyric`` 为空串，不抛错。"""
    if song_id <= 0:
        raise ValueError("song_id 必须为正整数")

    return await client.call(
        LYRIC,
        {"id": song_id, "lv": -1, "kv": -1, "tv": -1},
        model=LyricResponse,
        unwrap="none",
        cache="detail" if use_cache else "none",
    )
