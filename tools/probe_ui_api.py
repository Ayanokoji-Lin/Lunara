"""阶段④ 前置探针：把 UI 需要的接口逐条打一遍，确认路径与字段。

只读。跑法：.venv/Scripts/python.exe tools/probe_ui_api.py
"""
from __future__ import annotations

import hashlib
import json

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

EAPI_KEY = b"e82ckenh8dichen8"
SEP = "-36cd479b6b5-"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0")
COOKIE = ("os=pc; appver=8.9.70; osver=Microsoft-Windows-10-Professional-build-19045-64bit; "
          "channel=netease; __remember_me=true")


def eapi(path: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.md5(f"nobody{path}use{body}md5forencrypt".encode()).hexdigest()
    plain = f"{path}{SEP}{body}{SEP}{digest}".encode()
    pad = 16 - len(plain) % 16
    e = Cipher(algorithms.AES(EAPI_KEY), modes.ECB()).encryptor()
    return (e.update(plain + bytes([pad]) * pad) + e.finalize()).hex().upper()


def call(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=15.0) as c:
        r = c.post(f"https://music.163.com/eapi{path}", data={"params": eapi(path, payload)},
                   headers={"User-Agent": UA, "Referer": "https://music.163.com",
                            "Content-Type": "application/x-www-form-urlencoded", "Cookie": COOKIE})
        try:
            return r.json()
        except Exception:
            return {"_status": r.status_code, "_raw": r.text[:200]}


def show(name: str, res: dict, keys: list[str]) -> None:
    code = res.get("code")
    print(f"[{name}] code={code} top={list(res.keys())[:6]}")
    for key in keys:
        value = res
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, list):
            sample = value[0] if value else {}
            print(f"    {key}: list[{len(value)}] keys={list(sample.keys())[:12] if isinstance(sample, dict) else type(sample).__name__}")
        elif isinstance(value, dict):
            print(f"    {key}: dict keys={list(value.keys())[:12]}")
        else:
            print(f"    {key}: {str(value)[:80]}")


# 1) 歌单详情（首页卡片点进去要用）
res = call("/api/v6/playlist/detail", {"id": 3778678, "n": 1000, "s": 8})
show("v6/playlist/detail", res, ["playlist.name", "playlist.coverImgUrl", "playlist.trackCount",
                                 "playlist.playCount", "playlist.creator.nickname",
                                 "playlist.description", "playlist.tags", "playlist.tracks"])

# 2) 歌词（播放页要用）
res = call("/api/song/lyric", {"id": 347230, "lv": -1, "kv": -1, "tv": -1})
show("song/lyric", res, ["lrc.lyric", "tlyric.lyric", "klyric.lyric"])

# 3) 推荐歌单（首页网格）
res = call("/api/personalized/playlist", {"limit": 6, "total": True, "n": 1000})
show("personalized/playlist", res, ["result"])
if isinstance(res.get("result"), list) and res["result"]:
    print("    sample:", json.dumps({k: res["result"][0].get(k) for k in
                                     ("id", "name", "picUrl", "playCount", "copywriter")},
                                    ensure_ascii=False)[:200])

# 4) 新歌速递（首页第二块）
res = call("/api/personalized/newsong", {"limit": 5, "areaId": 0, "type": "recommend"})
show("personalized/newsong", res, ["result"])
if isinstance(res.get("result"), list) and res["result"]:
    print("    sample keys:", list(res["result"][0].keys()))

# 5) 搜索其它类型：专辑 10 / 歌手 100 / 歌单 1000
for type_id in (10, 100, 1000):
    res = call("/api/cloudsearch/pc", {"s": "周杰伦", "type": type_id, "limit": 3, "offset": 0, "total": True})
    body = res.get("result", {})
    print(f"[cloudsearch type={type_id}] code={res.get('code')} keys={list(body.keys())}")
    for key, value in body.items():
        if isinstance(value, list) and value:
            print(f"    {key}: list[{len(value)}] keys={list(value[0].keys())[:12]}")

# 6) 我喜欢的音乐 / 我的歌单（需要登录，预期 301）
res = call("/api/song/like", {"uid": 0})
print(f"[song/like] code={res.get('code')} keys={list(res.keys())[:5]}")
res = call("/api/user/playlist", {"uid": 0, "limit": 30, "offset": 0})
print(f"[user/playlist] code={res.get('code')} keys={list(res.keys())[:5]}")
