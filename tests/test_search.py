"""搜索模块：参数拼装与入参校验（四类）。"""
from __future__ import annotations

from typing import Any

import pytest

from lunara.api.endpoints import CLOUDSEARCH
from lunara.api.models.song import SongSearchResult
from lunara.api.modules.search import (
    SearchKind,
    search_albums,
    search_artists,
    search_playlists,
    search_songs,
)


class RecordingClient:
    """只记录调用参数，不发请求。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call(
        self,
        endpoint: Any,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SongSearchResult:
        self.calls.append({"endpoint": endpoint, "params": params, "kwargs": kwargs})
        return SongSearchResult(songs=(), songCount=0)


async def test_builds_expected_params() -> None:
    client = RecordingClient()
    await search_songs(client, "  周杰伦  ", page=3, limit=20)  # type: ignore[arg-type]

    call = client.calls[0]
    assert call["endpoint"] is CLOUDSEARCH
    assert call["params"] == {
        "s": "周杰伦",
        "type": 1,
        "limit": 20,
        "offset": 40,  # (3-1) * 20
        "total": True,
    }
    assert call["kwargs"]["cache"] == "list"


async def test_cache_flag_can_be_turned_off() -> None:
    client = RecordingClient()
    await search_songs(client, "周杰伦", use_cache=False)  # type: ignore[arg-type]
    assert client.calls[0]["kwargs"]["cache"] == "none"


@pytest.mark.parametrize("keyword", ["", "   ", "\n\t"])
async def test_blank_keyword_rejected(keyword: str) -> None:
    with pytest.raises(ValueError):
        await search_songs(RecordingClient(), keyword)  # type: ignore[arg-type]


@pytest.mark.parametrize(("page", "limit"), [(0, 30), (1, 0), (1, 101)])
async def test_bounds_rejected(page: int, limit: int) -> None:
    with pytest.raises(ValueError):
        await search_songs(RecordingClient(), "周杰伦", page=page, limit=limit)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 四类搜索：type 参数必须与上游枚举一致
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("func", "kind", "type_id"),
    [
        (search_songs, SearchKind.SONG, 1),
        (search_artists, SearchKind.ARTIST, 100),
        (search_albums, SearchKind.ALBUM, 10),
        (search_playlists, SearchKind.PLAYLIST, 1000),
    ],
)
async def test_kind_is_sent_as_type(func: Any, kind: SearchKind, type_id: int) -> None:
    client = RecordingClient()
    await func(client, "周杰伦", page=2, limit=10)  # type: ignore[arg-type]

    params = client.calls[0]["params"]
    assert params["type"] == type_id
    assert params["type"] == int(kind)
    assert params["offset"] == 10  # (2-1) * 10


async def test_kind_enum_values_match_upstream() -> None:
    assert [int(kind) for kind in SearchKind] == [1, 10, 100, 1000]
