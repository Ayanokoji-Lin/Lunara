"""API 模型 → UI 数据契约（`Track` / `Playlist`）的适配层。

这一层存在的理由：页面只认 ``lunara/data.py`` 里的三个 dataclass，
接口字段（``dt`` / ``al`` / ``ar`` / ``coverImgUrl``）不能漏到 UI 里。
换数据源时只改这里，页面一行不用动。

封面策略：不下载真实封面，用 id 派生一个稳定色相，交给 ``assets.cover_pixmap``
程序化生成。这样离线可用、零素材依赖，同一个歌单每次进来颜色都一样。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..api.models.personalized import NewSongEntry, RecommendedPlaylist
from ..api.models.playlist import PlaylistDetail
from ..api.models.search import AlbumHit, ArtistHit, PlaylistHit
from ..api.models.user import UserPlaylist
from ..api.models.song import Song
from ..api.modules.search import SearchKind
from ..data import Playlist, Track

UNKNOWN_ARTIST = "未知歌手"
UNKNOWN_ALBUM = "未知专辑"
DEFAULT_AUTHOR = "网易云音乐"


@dataclass(frozen=True, slots=True)
class CardItem:
    """歌手 / 专辑卡片的最小数据（``CoverCard`` 需要的四个字段）。"""

    seed: int
    hue: int
    title: str
    subtitle: str = ""
    cover_url: str = ""


@dataclass(frozen=True, slots=True)
class SearchPayload:
    """一次搜索的结果，按 ``kind`` 只填其中一组。"""

    kind: SearchKind
    tracks: tuple[Track, ...] = ()
    cards: tuple[CardItem, ...] = ()
    playlists: tuple[Playlist, ...] = ()


def hue_for(seed: int) -> int:
    """由 id 稳定派生色相（0–359）。同一个 id 永远同一个颜色。"""
    return (abs(seed) * 37) % 360


def to_track(song: Song) -> Track:
    """搜索 / 歌单里的短字段歌曲 → UI Track。"""
    return Track(
        id=song.id,
        title=song.name or UNKNOWN_ARTIST,
        artist=song.artist_names or UNKNOWN_ARTIST,
        album=song.album.name if song.album else UNKNOWN_ALBUM,
        duration=song.duration_seconds,
        hue=hue_for(song.id),
        cover_url=song.album.pic_url if song.album else "",
    )


def to_track_from_newsong(entry: NewSongEntry) -> Track | None:
    """新歌速递（长字段名）→ UI Track；缺 song 时返回 None。"""
    song = entry.song
    if song is None:
        return None
    return Track(
        id=song.id,
        title=song.name or entry.name or UNKNOWN_ARTIST,
        artist=song.artist_names or UNKNOWN_ARTIST,
        album=song.album.name if song.album else UNKNOWN_ALBUM,
        duration=song.duration_seconds,
        hue=hue_for(song.id),
        cover_url=song.album.pic_url if song.album else "",
    )


def to_playlist(detail: PlaylistDetail) -> Playlist:
    """歌单详情 → UI Playlist（含曲目）。"""
    return Playlist(
        id=detail.id,
        title=detail.name,
        author=detail.author or DEFAULT_AUTHOR,
        plays=detail.play_count,
        hue=hue_for(detail.id),
        tag=detail.tags[0] if detail.tags else "",
        desc=detail.description or "",
        cover_url=detail.cover_url,
        tracks=[to_track(song) for song in detail.tracks],
    )


def to_playlist_card(item: RecommendedPlaylist) -> Playlist:
    """推荐歌单（首页卡片）→ UI Playlist（无曲目，点进去再拉详情）。"""
    return Playlist(
        id=item.id,
        title=item.name,
        author=item.copywriter or DEFAULT_AUTHOR,
        plays=item.play_count,
        hue=hue_for(item.id),
        cover_url=item.pic_url,
    )


def to_track_list(songs: list[Song] | tuple[Song, ...]) -> list[Track]:
    return [to_track(song) for song in songs]


def to_artist_card(hit: ArtistHit) -> CardItem:
    """歌手搜索结果 → 圆形卡片。"""
    return CardItem(
        seed=hit.id, hue=hue_for(hit.id), title=hit.name, subtitle="歌手",
        cover_url=hit.pic_url,
    )


def to_album_card(hit: AlbumHit) -> CardItem:
    """专辑搜索结果 → 方形卡片，副标题是歌手名。"""
    return CardItem(
        seed=hit.id,
        hue=hue_for(hit.id),
        title=hit.name,
        subtitle=hit.artist_name or UNKNOWN_ALBUM,
        cover_url=hit.pic_url,
    )


def to_playlist_hit(hit: PlaylistHit) -> Playlist:
    """歌单搜索结果 → 可点进详情的 Playlist。"""
    return Playlist(
        id=hit.id,
        title=hit.name,
        author=hit.author or DEFAULT_AUTHOR,
        plays=hit.play_count,
        hue=hue_for(hit.id),
        cover_url=hit.cover_url,
    )


def to_playlist_from_user(item: UserPlaylist) -> Playlist:
    """``/api/user/playlist`` 的一项 → 侧栏用的 Playlist（无曲目）。"""
    return Playlist(
        id=item.id,
        title=item.name,
        author=item.author or "我",
        plays=item.play_count,
        hue=hue_for(item.id),
        cover_url=item.cover_url,
    )


def split_user_playlists(
    items: tuple[UserPlaylist, ...] | list[UserPlaylist],
) -> tuple[list[Playlist], list[Playlist], int | None]:
    """拆成（创建的、收藏的、我喜欢的 id）。

    「我喜欢的音乐」是 ``specialType=5`` 的特殊歌单，不放进侧栏列表，
    而是留给「我喜欢的音乐」那个固定入口。
    """
    created: list[Playlist] = []
    collected: list[Playlist] = []
    liked_id: int | None = None

    for item in items:
        # 实测：收藏别人的「喜欢的音乐」也是 specialType=5，靠 subscribed 区分；
        # 只认自己那个（subscribed=False），否则会指到别人歌单上。
        if item.is_liked and not item.subscribed:
            if liked_id is None:
                liked_id = item.id
            continue
        if item.is_collected:
            collected.append(to_playlist_from_user(item))
        else:
            created.append(to_playlist_from_user(item))

    return created, collected, liked_id
