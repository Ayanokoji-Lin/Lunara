"""适配层：接口模型 → UI 的 Track / Playlist。

夹具全部是 2026-10-24 的真实回包，字段改名/缺失会在这里先炸。
"""
from __future__ import annotations

import json
from pathlib import Path

from lunara.api.models.personalized import (
    NewSongEntry,
    NewSongResult,
    RecommendedPlaylists,
)
from lunara.api.models.playlist import PlaylistDetailResponse
from lunara.api.models.song import SongSearchResult
from lunara.services.catalog import (
    hue_for,
    to_playlist,
    to_playlist_card,
    to_track,
    to_track_from_newsong,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
def test_hue_is_stable_and_in_range() -> None:
    assert hue_for(12345) == hue_for(12345)
    assert 0 <= hue_for(0) <= 359
    assert 0 <= hue_for(2_147_483_647) <= 359
    assert hue_for(-5) == hue_for(5)


def test_to_track_maps_short_fields() -> None:
    payload = SongSearchResult.model_validate(_load("cloudsearch_songs")["result"])
    song = payload.songs[0]

    track = to_track(song)

    assert track.id == song.id
    assert track.title == song.name
    assert track.artist == " / ".join(a.name for a in song.artists)
    assert track.album == (song.album.name if song.album else "未知专辑")
    assert track.duration == round(song.duration_ms / 1000)
    assert track.hue == hue_for(song.id)
    assert track.duration_text.count(":") == 1


def test_to_track_falls_back_on_missing_album() -> None:
    song = SongSearchResult.model_validate(
        {"songs": [{"id": 1, "name": "无专辑", "dt": 61000, "al": None, "ar": [{"id": 2, "name": "某人"}]}]}
    ).songs[0]

    track = to_track(song)
    assert track.album == "未知专辑"
    assert track.duration == 61
    assert track.duration_text == "01:01"


def test_to_playlist_from_real_detail() -> None:
    response = PlaylistDetailResponse.model_validate(_load("playlist_detail"))
    assert response.playlist is not None

    playlist = to_playlist(response.playlist)

    assert playlist.id == response.playlist.id
    assert playlist.title == response.playlist.name
    assert playlist.author == (response.playlist.creator.nickname if response.playlist.creator else "")
    assert playlist.plays == response.playlist.play_count
    assert len(playlist.tracks) == len(response.playlist.tracks)
    assert playlist.tracks[0].id == response.playlist.tracks[0].id
    assert playlist.desc == response.playlist.description  # 真实简介，不再用硬编码文案
    assert playlist.plays_text  # 已实现「万/亿」缩写


def test_to_playlist_card_from_recommend() -> None:
    payload = RecommendedPlaylists.model_validate(_load("personalized_playlist"))
    assert payload.result

    card = to_playlist_card(payload.result[0])

    assert card.id == payload.result[0].id
    assert card.title == payload.result[0].name
    assert card.plays == payload.result[0].play_count
    assert card.tracks == []


def test_to_track_from_newsong_uses_long_fields() -> None:
    payload = NewSongResult.model_validate(_load("personalized_newsong"))
    entry = payload.result[0]

    track = to_track_from_newsong(entry)

    assert track is not None
    assert track.id == entry.song.id  # type: ignore[union-attr]
    assert track.duration == round(entry.song.duration / 1000)  # type: ignore[union-attr]
    assert track.artist


def test_to_track_from_newsong_handles_missing_song() -> None:
    entry = NewSongEntry.model_validate({"id": 1, "name": "x"})
    assert to_track_from_newsong(entry) is None


# --------------------------------------------------------------------------- #
# 搜索卡片：歌手 / 专辑 / 歌单
# --------------------------------------------------------------------------- #
def test_artist_hit_to_card() -> None:
    from lunara.api.models.search import ArtistSearchResult
    from lunara.services.catalog import to_artist_card

    payload = ArtistSearchResult.model_validate(_load("search_artists")["result"])
    hit = payload.artists[0]

    card = to_artist_card(hit)

    assert card.seed == hit.id
    assert card.hue == hue_for(hit.id)
    assert card.title == hit.name
    assert card.subtitle == "歌手"


def test_album_hit_to_card() -> None:
    from lunara.api.models.search import AlbumSearchResult
    from lunara.services.catalog import to_album_card

    payload = AlbumSearchResult.model_validate(_load("search_albums")["result"])
    hit = payload.albums[0]

    card = to_album_card(hit)

    assert card.seed == hit.id
    assert card.title == hit.name
    assert card.subtitle == hit.artist_name
    assert card.subtitle  # 专辑必须能显示歌手名


def test_playlist_hit_to_playlist() -> None:
    from lunara.api.models.search import PlaylistSearchResult
    from lunara.services.catalog import to_playlist_hit

    payload = PlaylistSearchResult.model_validate(_load("search_playlists")["result"])
    hit = payload.playlists[0]

    playlist = to_playlist_hit(hit)

    assert playlist.id == hit.id
    assert playlist.title == hit.name
    assert playlist.plays == hit.play_count
    assert playlist.tracks == []          # 卡片阶段不带曲目
    assert playlist.plays_text


# --------------------------------------------------------------------------- #
# 封面地址：真实图有就用，没有就回落月牙空态
# --------------------------------------------------------------------------- #
def test_track_carries_cover_url() -> None:
    payload = SongSearchResult.model_validate(_load("cloudsearch_songs")["result"])
    song = payload.songs[0]

    track = to_track(song)

    assert track.cover_url == (song.album.pic_url if song.album else "")


def test_playlist_detail_carries_cover_url() -> None:
    response = PlaylistDetailResponse.model_validate(_load("playlist_detail"))
    assert response.playlist is not None

    playlist = to_playlist(response.playlist)

    assert playlist.cover_url == response.playlist.cover_url
    assert playlist.cover_url.startswith("http")


def test_recommend_card_carries_cover_url() -> None:
    payload = RecommendedPlaylists.model_validate(_load("personalized_playlist"))
    card = to_playlist_card(payload.result[0])

    assert card.cover_url == payload.result[0].pic_url


def test_artist_and_album_cards_carry_cover_url() -> None:
    from lunara.api.models.search import AlbumSearchResult, ArtistSearchResult
    from lunara.services.catalog import to_album_card, to_artist_card

    artists = ArtistSearchResult.model_validate(_load("search_artists")["result"])
    albums = AlbumSearchResult.model_validate(_load("search_albums")["result"])

    assert to_artist_card(artists.artists[0]).cover_url == artists.artists[0].pic_url
    assert to_album_card(albums.albums[0]).cover_url == albums.albums[0].pic_url


# --------------------------------------------------------------------------- #
# 我的歌单：创建 / 收藏 / 我喜欢的拆分
# --------------------------------------------------------------------------- #
def test_split_user_playlists() -> None:
    from lunara.api.models.user import UserPlaylistsResponse
    from lunara.services.catalog import split_user_playlists

    payload = UserPlaylistsResponse.model_validate(_load("user_playlists"))
    created, collected, liked_id = split_user_playlists(payload.playlist)

    assert liked_id == 9687758128          # 自己的「喜欢的音乐」
    assert all(p.title != "到桔子林去喜欢的音乐" for p in created + collected)
    assert created and collected


def test_split_prefers_own_liked_playlist() -> None:
    """收藏别人的「喜欢的音乐」也是 specialType=5，不能抢走 liked_id。"""
    from lunara.api.models.user import UserPlaylistsResponse
    from lunara.services.catalog import split_user_playlists

    payload = UserPlaylistsResponse.model_validate({
        "playlist": [
            {"id": 1, "name": "我的喜欢", "specialType": 5, "subscribed": False},
            {"id": 2, "name": "别人的喜欢", "specialType": 5, "subscribed": True},
        ]
    })
    created, collected, liked_id = split_user_playlists(payload.playlist)

    assert liked_id == 1
    assert [p.id for p in collected] == [2]   # 收藏的那份进「收藏的歌单」
    assert created == []


def test_playlist_tolerates_null_fields() -> None:
    """实测：私密歌单的 description / creator.nickname 可能是 null。"""
    response = PlaylistDetailResponse.model_validate(
        {"code": 200, "playlist": {"id": 1, "name": "无简介", "description": None,
                                   "creator": {"nickname": None}}}
    )
    assert response.playlist is not None

    playlist = to_playlist(response.playlist)

    assert playlist.desc == ""
    assert playlist.author  # 回落到默认作者，不是 None
