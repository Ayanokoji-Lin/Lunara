"""歌手页 / 专辑页：模型解析、接口拼装、catalog 映射。

夹具是 2026-10-24 的真实回包（裁剪过：只留 5 首歌、去掉大字段）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lunara.api.models.album import AlbumDetail
from lunara.api.models.artist import ArtistDetail
from lunara.api.modules.album import get_album
from lunara.api.modules.artist import get_artist
from lunara.services.catalog import to_playlist_from_album, to_playlist_from_artist

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class RecordingClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    async def call(self, endpoint: Any, params: Any = None, **kwargs: Any) -> Any:
        self.calls.append({"path": endpoint.path, "params": params, "kwargs": kwargs})
        return ArtistDetail.model_validate(self.payload)


# --------------------------------------------------------------------------- #
# 模型
# --------------------------------------------------------------------------- #
def test_artist_detail_parses() -> None:
    detail = ArtistDetail.model_validate(load("artist_detail"))

    assert detail.artist.name == "周杰伦"
    assert detail.artist.pic_url.startswith("http")
    assert detail.artist.music_size > 0
    assert len(detail.hot_songs) == 5
    assert detail.hot_songs[0].name
    assert detail.more in (True, False)


def test_artist_alias_subtitle() -> None:
    detail = ArtistDetail.model_validate(load("artist_detail"))

    assert "Jay Chou" in detail.artist.subtitle


def test_album_detail_parses() -> None:
    detail = AlbumDetail.model_validate(load("album_detail"))

    assert detail.album.name == "看我72变"
    assert detail.album.artist_names == "蔡依林"
    assert detail.album.publish_year == 2003
    assert len(detail.songs) == 5


def test_album_tolerates_null_description() -> None:
    detail = AlbumDetail.model_validate({
        "album": {"id": 1, "name": "无简介", "description": None},
        "songs": [],
    })

    assert detail.album.description is None
    assert detail.album.artist_names == "未知歌手"


# --------------------------------------------------------------------------- #
# 接口拼装
# --------------------------------------------------------------------------- #
async def test_get_artist_builds_path() -> None:
    client = RecordingClient(load("artist_detail"))

    await get_artist(client, 6452)  # type: ignore[arg-type]

    call = client.calls[0]
    assert call["path"] == "/api/v1/artist/6452"
    assert call["params"] == {}
    assert call["kwargs"]["cache"] == "detail"


async def test_get_artist_rejects_bad_id() -> None:
    client = RecordingClient(load("artist_detail"))

    with pytest.raises(ValueError):
        await get_artist(client, 0)  # type: ignore[arg-type]


async def test_get_album_builds_path() -> None:
    client = RecordingClient(load("artist_detail"))
    client.payload = load("album_detail")

    # 用一个只返回 AlbumDetail 的假客户端
    class AlbumClient(RecordingClient):
        async def call(self, endpoint: Any, params: Any = None, **kwargs: Any) -> Any:
            self.calls.append({"path": endpoint.path, "params": params, "kwargs": kwargs})
            return AlbumDetail.model_validate(self.payload)

    album_client = AlbumClient(load("album_detail"))
    await get_album(album_client, 21349)  # type: ignore[arg-type]

    assert album_client.calls[0]["path"] == "/api/v1/album/21349"


# --------------------------------------------------------------------------- #
# catalog 映射
# --------------------------------------------------------------------------- #
def test_artist_to_playlist() -> None:
    playlist = to_playlist_from_artist(ArtistDetail.model_validate(load("artist_detail")))

    assert playlist.title == "周杰伦"
    assert playlist.tag == "歌手"
    assert playlist.cover_url.startswith("http")
    assert len(playlist.tracks) == 5
    assert all(track.remote for track in playlist.tracks)


def test_album_to_playlist() -> None:
    playlist = to_playlist_from_album(AlbumDetail.model_validate(load("album_detail")))

    assert playlist.title == "看我72变"
    assert playlist.tag == "专辑"
    assert playlist.author == "蔡依林"
    assert len(playlist.tracks) == 5
    assert all(track.remote for track in playlist.tracks)
