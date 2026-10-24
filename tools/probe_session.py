"""阶段③ 前置探针：登录/会员态接口 + 音质档位实测。

只读。跑法：.venv/Scripts/python.exe tools/probe_session.py
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
    with httpx.Client(timeout=10.0) as c:
        r = c.post(f"https://music.163.com/eapi{path}", data={"params": eapi(path, payload)},
                   headers={"User-Agent": UA, "Referer": "https://music.163.com",
                            "Content-Type": "application/x-www-form-urlencoded", "Cookie": COOKIE})
        try:
            return r.json()
        except Exception:
            return {"_raw": r.text[:300], "_status": r.status_code}


print("=== /api/nuser/account/get（匿名） ===")
res = call("/api/nuser/account/get", {})
print("keys:", list(res.keys()), "code:", res.get("code"))
print(json.dumps({k: res[k] for k in res if k not in ("profile",)}, ensure_ascii=False)[:400])
if res.get("profile"):
    print("profile keys:", sorted(res["profile"].keys()))

print("\n=== /api/v1/user/detail/（匿名，uid 猜测会 301/404，看错误形态） ===")
res2 = call("/api/v1/user/detail/32953014", {})
print("code:", res2.get("code"), "keys:", list(res2.keys())[:8])

print("\n=== 音质档位实测（免费歌 347230 / VIP 歌 509781655） ===")
LEVELS = ["standard", "higher", "exhigh", "lossless", "hires", "jymaster"]
for song_id in (347230, 509781655):
    print(f"-- song {song_id}")
    for level in LEVELS:
        res = call("/api/song/enhance/player/url/v1",
                   {"ids": f"[{song_id}]", "level": level, "encodeType": "flac"})
        item = (res.get("data") or [{}])[0]
        trial = item.get("freeTrialInfo")
        print(f"   {level:<9} code={res.get('code')} item.code={item.get('code')} "
              f"level={item.get('level')} br={item.get('br')} type={item.get('type')} "
              f"expi={item.get('expi')} url={'Y' if item.get('url') else 'N'} "
              f"trial={'Y' if trial else 'N'} fee={item.get('fee')}")
