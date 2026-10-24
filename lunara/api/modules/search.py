"""搜索接口（四类：单曲 / 歌手 / 专辑 / 歌单）。

实测（2026-10-24）：``POST /eapi/api/cloudsearch/pc``
参数 ``s, type, limit, offset, total``，``type`` 决定返回哪个字段：

| type | 返回 |
|---|---|
| 1 | ``result.songs`` / ``songCount`` |
| 10 | ``result.albums`` / ``albumCount`` |
| 100 | ``result.artists`` / ``artistCount`` |
| 1000 | ``result.playlists`` / ``playlistCount`` |
"""
from __future__ import annotations

from enum import IntEnum
from typing import TypeVar

from pydantic import BaseModel

from ..client import ApiClient
from ..endpoints import CLOUDSEARCH
from ..models.search import AlbumSearchResult, ArtistSearchResult, PlaylistSearchResult
from ..models.song import SongSearchResult

TModel = TypeVar("TModel", bound=BaseModel)

MAX_LIMIT = 100


class SearchKind(IntEnum):
    """与上游 ``type`` 参数一一对应。"""

    SONG = 1
    ALBUM = 10
    ARTIST = 100
    PLAYLIST = 1000


def _validate(keyword: str, page: int, limit: int) -> str:
    text = keyword.strip()
    if not text:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 从 1 开始")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit 必须在 1–{MAX_LIMIT} 之间")
    return text


async def _search(
    client: ApiClient,
    keyword: str,
    kind: SearchKind,
    model: type[TModel],
    *,
    page: int,
    limit: int,
    use_cache: bool,
) -> TModel:
    text = _validate(keyword, page, limit)
    return await client.call(
        CLOUDSEARCH,
        {
            "s": text,
            "type": int(kind),
            "limit": limit,
            "offset": (page - 1) * limit,
            "total": True,
        },
        model=model,
        cache="list" if use_cache else "none",
    )


async def search_songs(
    client: ApiClient,
    keyword: str,
    *,
    page: int = 1,
    limit: int = 30,
    use_cache: bool = True,
) -> SongSearchResult:
    """按关键词搜单曲。

    Raises:
        ValueError: 关键词为空或页码/条数越界。
        ApiError: 上游或解析失败。
    """
    return await _search(
        client, keyword, SearchKind.SONG, SongSearchResult,
        page=page, limit=limit, use_cache=use_cache,
    )


async def search_artists(
    client: ApiClient,
    keyword: str,
    *,
    page: int = 1,
    limit: int = 20,
    use_cache: bool = True,
) -> ArtistSearchResult:
    return await _search(
        client, keyword, SearchKind.ARTIST, ArtistSearchResult,
        page=page, limit=limit, use_cache=use_cache,
    )


async def search_albums(
    client: ApiClient,
    keyword: str,
    *,
    page: int = 1,
    limit: int = 20,
    use_cache: bool = True,
) -> AlbumSearchResult:
    return await _search(
        client, keyword, SearchKind.ALBUM, AlbumSearchResult,
        page=page, limit=limit, use_cache=use_cache,
    )


async def search_playlists(
    client: ApiClient,
    keyword: str,
    *,
    page: int = 1,
    limit: int = 20,
    use_cache: bool = True,
) -> PlaylistSearchResult:
    return await _search(
        client, keyword, SearchKind.PLAYLIST, PlaylistSearchResult,
        page=page, limit=limit, use_cache=use_cache,
    )
