"""演示歌单的边界：id 只存在于本地，不能被当成真实歌单去请求接口。"""
from __future__ import annotations

from lunara.data import (
    DEMO_PLAYLIST_IDS,
    PLAYLISTS,
    TRACKS,
    demo_playlist,
    is_demo_playlist,
)


def test_demo_ids_start_at_101() -> None:
    assert min(DEMO_PLAYLIST_IDS) == 101
    assert len(DEMO_PLAYLIST_IDS) == len(PLAYLISTS)


def test_ids_are_unique() -> None:
    ids = [p.id for p in PLAYLISTS]
    assert len(ids) == len(set(ids))


def test_is_demo_playlist() -> None:
    assert is_demo_playlist(101) is True
    assert is_demo_playlist(3778678) is False      # 热歌榜是真实 id
    assert is_demo_playlist(0) is False


def test_demo_playlist_has_tracks() -> None:
    playlist = demo_playlist(101)

    assert playlist is not None
    assert playlist.title
    assert playlist.tracks
    assert all(track in TRACKS for track in playlist.tracks)


def test_demo_playlist_unknown_returns_none() -> None:
    assert demo_playlist(999_999) is None


def test_every_demo_playlist_has_description() -> None:
    assert all(p.desc for p in PLAYLISTS)
