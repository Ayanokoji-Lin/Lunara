"""歌单接口。

实测（2026-10-24）：``/api/v6/playlist/detail?id=<id>&n=<limit>&s=8``
返回 ``playlist`` 对象；``n`` 控制返回的曲目数量上限（热歌榜 200 首实测完整返回）。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import PLAYLIST_DETAIL
from ..models.playlist import PlaylistDetail, PlaylistDetailResponse

MAX_TRACKS = 1000


async def get_playlist_detail(
    client: ApiClient,
    playlist_id: int,
    *,
    track_limit: int = MAX_TRACKS,
    use_cache: bool = True,
) -> PlaylistDetail:
    """取歌单详情（含曲目列表）。

    Raises:
        ValueError: id 非法或曲目上限越界。
        ApiError: 上游或解析失败。
    """
    if playlist_id <= 0:
        raise ValueError("playlist_id 必须为正整数")
    if not 1 <= track_limit <= MAX_TRACKS:
        raise ValueError(f"track_limit 必须在 1–{MAX_TRACKS} 之间")

    response = await client.call(
        PLAYLIST_DETAIL,
        {"id": playlist_id, "n": track_limit, "s": 8},
        model=PlaylistDetailResponse,
        unwrap="none",
        cache="detail" if use_cache else "none",
    )
    if response.playlist is None:
        from ..errors import ApiError, ErrorCode

        raise ApiError(ErrorCode.PARSE_ERROR, "歌单不存在或未返回 playlist")
    return response.playlist
