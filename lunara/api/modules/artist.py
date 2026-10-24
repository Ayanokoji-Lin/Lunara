"""歌手接口。

实测（2026-10-24）：``/api/v1/artist/{id}`` → ``{artist, hotSongs[50], more}``。
路径带 id，所以每次调用现拼一个 ``Endpoint``；结果按 id 走详情缓存。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import ARTIST_DETAIL_PATH, Endpoint
from ..models.artist import ArtistDetail


async def get_artist(
    client: ApiClient, artist_id: int, *, use_cache: bool = True
) -> ArtistDetail:
    """取歌手信息与热门 50 首。

    Raises:
        ValueError: artist_id 非法。
    """
    if artist_id <= 0:
        raise ValueError("artist_id 必须为正整数")

    return await client.call(
        Endpoint(ARTIST_DETAIL_PATH.format(artist_id=artist_id), True, "歌手详情"),
        {},
        model=ArtistDetail,
        unwrap="none",
        cache="detail" if use_cache else "none",
    )
