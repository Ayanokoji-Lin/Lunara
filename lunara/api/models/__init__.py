"""领域模型出口。"""
from __future__ import annotations

from .common import AlbumRef, ArtistRef, Privilege, StrictModel
from .lyric import LyricBody, LyricResponse
from .personalized import (
    NewSongEntry,
    NewSongResult,
    NewSongTrack,
    RecommendedPlaylist,
    RecommendedPlaylists,
)
from .player_url import FreeTrialInfo, SongUrlItem, SongUrlResponse
from .playlist import PlaylistCreator, PlaylistDetail, PlaylistDetailResponse
from .song import Song, SongSearchResult
from .user import Account, LoginStatus, Profile

__all__ = [
    "Account",
    "AlbumRef",
    "ArtistRef",
    "FreeTrialInfo",
    "LoginStatus",
    "LyricBody",
    "LyricResponse",
    "NewSongEntry",
    "NewSongResult",
    "NewSongTrack",
    "PlaylistCreator",
    "PlaylistDetail",
    "PlaylistDetailResponse",
    "Privilege",
    "Profile",
    "RecommendedPlaylist",
    "RecommendedPlaylists",
    "Song",
    "SongSearchResult",
    "SongUrlItem",
    "SongUrlResponse",
    "StrictModel",
]
