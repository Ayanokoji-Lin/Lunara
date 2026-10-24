"""首页推荐接口（推荐歌单 / 新歌速递）。

实测（2026-10-24）：
- ``/api/personalized/playlist``：参数 ``limit,total,n``，返回 ``result[]``
- ``/api/personalized/newsong``：参数 ``limit,areaId,type``，返回 ``result[].song``
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import NEW_SONGS, RECOMMEND_PLAYLISTS
from ..models.personalized import NewSongEntry, NewSongResult, RecommendedPlaylist, RecommendedPlaylists

MAX_LIMIT = 50


async def get_recommended_playlists(
    client: ApiClient, *, limit: int = 10, use_cache: bool = True
) -> tuple[RecommendedPlaylist, ...]:
    """推荐歌单。首页网格是 5 列 × 2 行，默认取 10 个。"""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit 必须在 1–{MAX_LIMIT} 之间")

    response = await client.call(
        RECOMMEND_PLAYLISTS,
        {"limit": limit, "total": True, "n": 1000},
        model=RecommendedPlaylists,
        unwrap="none",  # 模型自带 result 字段，别再解一层（踩过：双重解包 → PARSE_ERROR）
        cache="list" if use_cache else "none",
    )
    return response.result


async def get_new_songs(
    client: ApiClient, *, limit: int = 5, use_cache: bool = True
) -> tuple[NewSongEntry, ...]:
    """新歌速递。首页只展示一行，默认 5 首。"""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit 必须在 1–{MAX_LIMIT} 之间")

    response = await client.call(
        NEW_SONGS,
        {"limit": limit, "areaId": 0, "type": "recommend"},
        model=NewSongResult,
        unwrap="none",  # 同上：result 在模型里
        cache="list" if use_cache else "none",
    )
    return response.result
