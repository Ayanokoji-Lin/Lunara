"""专辑接口。

实测（2026-10-24）：``/api/v1/album/{id}`` → ``{album, songs[]}``。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import ALBUM_DETAIL_PATH, Endpoint
from ..models.album import AlbumDetail


async def get_album(
    client: ApiClient, album_id: int, *, use_cache: bool = True
) -> AlbumDetail:
    """取专辑信息与曲目。

    Raises:
        ValueError: album_id 非法。
    """
    if album_id <= 0:
        raise ValueError("album_id 必须为正整数")

    return await client.call(
        Endpoint(ALBUM_DETAIL_PATH.format(album_id=album_id), True, "专辑详情"),
        {},
        model=AlbumDetail,
        unwrap="none",
        cache="detail" if use_cache else "none",
    )
