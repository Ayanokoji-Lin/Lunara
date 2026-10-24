"""歌曲接口（直链部分）。

实测（2026-10-24）：``/api/song/enhance/player/url/v1``
参数 ``ids``（JSON 数组字符串，如 ``"[347230]"``）、``level``、``encodeType``。
"""
from __future__ import annotations

import json

from ..client import ApiClient
from ..endpoints import SONG_LIKE, SONG_URL_V1
from ..models.player_url import SongUrlItem, SongUrlResponse
from ..models.song import LikeResponse


async def get_song_urls(
    client: ApiClient,
    song_ids: list[int],
    level: str = "standard",
    *,
    encode_type: str = "flac",
) -> SongUrlResponse:
    """批量取直链（上游支持一次多个 id，这里保留能力，编排层按单曲调用）。

    Args:
        song_ids: 非空 id 列表。
        level: ``standard/higher/exhigh/lossless/hires/jymaster`` 之一。
        encode_type: 上游 ``encodeType``，实测 ``flac`` 可用。

    Raises:
        ValueError: id 列表为空。
    """
    if not song_ids:
        raise ValueError("song_ids 不能为空")

    ids = json.dumps(song_ids, separators=(",", ":"))
    return await client.call(
        SONG_URL_V1,
        {"ids": ids, "level": level, "encodeType": encode_type},
        model=SongUrlResponse,
        unwrap="none",  # 整包给模型，由 SongUrlResponse 自己取 data
        cache="none",
    )


async def get_song_url(
    client: ApiClient,
    song_id: int,
    level: str = "standard",
    *,
    encode_type: str = "flac",
) -> SongUrlItem | None:
    """取单曲直链。上游没给数据时返回 ``None``（不是错误，由编排层判定不可用）。"""
    response = await get_song_urls(client, [song_id], level, encode_type=encode_type)
    return response.first()


async def like_song(client: ApiClient, track_id: int, liked: bool) -> int:
    """喜欢 / 取消喜欢一首歌，返回「我喜欢的音乐」歌单 id。

    实测（2026-10-24）：参数是 ``trackId`` + ``like``（字符串 ``"true"``/``"false"``）+ ``time``；
    传 ``uid`` 会一直 400。写操作需要登录 Cookie（含 ``__csrf``）。

    Raises:
        ValueError: track_id 非法。
    """
    if track_id <= 0:
        raise ValueError("track_id 必须为正整数")

    response = await client.call(
        SONG_LIKE,
        {"trackId": track_id, "like": "true" if liked else "false", "time": 0},
        model=LikeResponse,
        unwrap="none",
        cache="none",          # 写操作绝不能命中缓存
    )
    return response.playlist_id
