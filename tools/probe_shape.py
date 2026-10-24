"""结构探针：打印搜索与直链接口的字段骨架，用于写 pydantic 模型。"""
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
        r = c.post(f"https://music.163.com/eapi/api{path}", data={"params": eapi(f"/api{path}", payload)},
                   headers={"User-Agent": UA, "Referer": "https://music.163.com",
                            "Content-Type": "application/x-www-form-urlencoded", "Cookie": COOKIE})
        return r.json()


def keys(obj, prefix="", depth=2):
    if depth == 0 or not isinstance(obj, dict):
        return
    for k, v in obj.items():
        t = type(v).__name__
        extra = ""
        if isinstance(v, list) and v:
            extra = f"[{len(v)}] of {type(v[0]).__name__}"
        print(f"{prefix}{k}: {t}{extra}")
        if isinstance(v, dict):
            keys(v, prefix + "  ", depth - 1)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            keys(v[0], prefix + "  - ", depth - 1)


print("===== cloudsearch/pc =====")
s = call("/cloudsearch/pc", {"s": "周杰伦", "type": 1, "limit": 2, "offset": 0, "total": True})
print("top:", list(s.keys()))
keys(s.get("result", {}), "  ", 2)
song = s["result"]["songs"][0]
print("\nsong keys:", sorted(song.keys()))
print("privilege keys:", sorted(song.get("privilege", {}).keys()))
print("album keys:", sorted(song.get("album", {}).keys()))
print("\nsong sample:", json.dumps({k: song[k] for k in ("id", "name", "dt", "fee", "al", "ar") if k in song}, ensure_ascii=False)[:300])

print("\n===== song/enhance/player/url/v1 =====")
u = call("/song/enhance/player/url/v1", {"ids": "[347230]", "level": "standard", "encodeType": "flac"})
print("top:", list(u.keys()))
item = u["data"][0]
print("item keys:", sorted(item.keys()))
print("item:", json.dumps({k: item[k] for k in item if k not in ("url", "freeTrialPrivilege", "chargeInfoList")}, ensure_ascii=False)[:400])
print("url head:", str(item.get("url"))[:60])
print("freeTrialPrivilege:", item.get("freeTrialPrivilege"))
print("chargeInfoList:", json.dumps(item.get("chargeInfoList"))[:200])
