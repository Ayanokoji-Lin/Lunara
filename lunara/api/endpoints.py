"""接口路径集中表。

每一条都带 ``verified`` 与实测日期。``verified=False`` 的条目一律带
``// UNVERIFIED:`` 注释说明缺什么，禁止凭记忆填参数。

eapi 的真实 URL = ``https://music.163.com`` + ``/eapi`` + ``path``，
path 里必须含 ``/api`` 前缀（实测：``/eapi/api/cloudsearch/pc`` 通，
``/eapi/cloudsearch/pc`` 回「接口未找到」）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Endpoint:
    """一个上游接口。

    Attributes:
        path: 传给 eapi 的路径，含 ``/api`` 前缀。
        verified: 是否已在真实上游验证通过。
        note: 实测结论 / 缺口说明。
    """

    path: str
    verified: bool
    note: str = ""


# --------------------------------------------------------------------------- #
# 已实测（2026-10-24，匿名 Cookie，HTTP 200 + code 200）
# --------------------------------------------------------------------------- #
CLOUDSEARCH = Endpoint(
    "/api/cloudsearch/pc",
    True,
    "type=1 返回 result.songs / result.songCount；参数 s,type,limit,offset,total",
)

SONG_URL_V1 = Endpoint(
    "/api/song/enhance/player/url/v1",
    True,
    "参数 ids(JSON 字符串),level,encodeType；返回 data[0].{url,br,expi,fee,level,freeTrialInfo}",
)

ACCOUNT_STATUS = Endpoint(
    "/api/nuser/account/get",
    True,
    "当前登录态：匿名时 account=null/profile=null，登录后含 account.id 与 profile.vipType",
)

USER_DETAIL = Endpoint(
    "/api/v1/user/detail/{uid}",
    True,
    "用户详情：返回 level(用户等级)、profile.vipType(会员类型)、bindings 等",
)

PLAYLIST_DETAIL = Endpoint(
    "/api/v6/playlist/detail",
    True,
    "参数 id,n,s；返回 playlist.{name,coverImgUrl,playCount,creator.nickname,tags,tracks[]}",
)

LYRIC = Endpoint(
    "/api/song/lyric",
    True,
    "参数 id,lv,kv,tv；返回 lrc.lyric（标准 LRC 文本）/ tlyric.lyric（翻译）",
)

RECOMMEND_PLAYLISTS = Endpoint(
    "/api/personalized/playlist",
    True,
    "参数 limit,total,n；返回 result[].{id,name,picUrl,playCount,copywriter,trackCount}",
)

NEW_SONGS = Endpoint(
    "/api/personalized/newsong",
    True,
    "参数 limit,areaId,type；返回 result[].song（注意是长字段名 album/artists/duration）",
)

SONG_DETAIL = Endpoint(
    "/api/v3/song/detail",
    True,
    "参数 c=[{id}]（JSON 字符串）；返回 songs[]（短字段 al/ar/dt）与 privileges[]",
)

SONG_LIKE = Endpoint(
    "/api/song/like",
    True,
    "参数 trackId,like('true'/'false'),time；返回 {code:200, playlistId}（实测 2026-10-24）",
)

USER_PLAYLIST = Endpoint(
    "/api/user/playlist",
    True,
    "参数 uid,limit,offset；返回 playlist[] 与 more（需要登录 Cookie）",
)

DJ_RECOMMEND = Endpoint(
    "/api/personalized/djprogram",
    True,
    "推荐单集：返回 result[]，每项 program.mainSong 是音频、program.radio 是所属电台",
)

#: 歌手详情：路径里带 id，调用时用 ``ARTIST_DETAIL_PATH.format(artist_id=...)`` 拼 Endpoint
ARTIST_DETAIL_PATH = "/api/v1/artist/{artist_id}"

#: 专辑详情：同上
ALBUM_DETAIL_PATH = "/api/v1/album/{album_id}"

# --------------------------------------------------------------------------- #
# 待验证（阶段③④ 逐条跑真请求确认，未确认前不写实现）
# --------------------------------------------------------------------------- #
UNVERIFIED: tuple[tuple[str, str], ...] = (
    ("/api/mv/detail", "MV 详情：路径待实测"),
    ("/api/comment/music", "评论：分页游标语义（before/time/limit/offset）待实测"),
    ("/api/register/anonimous", "匿名 Cookie 换取：是否需要 deviceId/加密参数待实测"),
    ("/api/song/like", "eapi 下 uid 传什么都 code=400（疑似仅 weapi 支持）；改走「我喜欢的音乐」歌单，无需此接口"),
    ("/api/login/qrcode/unikey", "扫码登录：eapi 是否支持待实测（NeteaseCloudMusicApi 用 weapi）"),
)
