"""eapi 探针 2：确定 URL 前缀（host + path 组合）。

上游对错误加密一般回 code 400/-460，回「接口未找到」说明是路由问题，
所以这里固定 payload，只换 host 与 path。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

EAPI_KEY = b"e82ckenh8dichen8"
SEP = "-36cd479b6b5-"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
COOKIE = (
    "os=pc; appver=8.9.70; osver=Microsoft-Windows-10-Professional-build-19045-64bit; "
    "channel=netease; __remember_me=true"
)


def pkcs7(data: bytes) -> bytes:
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad


def enc_hex(text: str) -> str:
    e = Cipher(algorithms.AES(EAPI_KEY), modes.ECB()).encryptor()
    return (e.update(pkcs7(text.encode())) + e.finalize()).hex().upper()


def eapi(path: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.md5(f"nobody{path}use{body}md5forencrypt".encode()).hexdigest()
    return enc_hex(f"{path}{SEP}{body}{SEP}{digest}")


PAYLOAD = {"s": "周杰伦", "type": 1, "limit": 3, "offset": 0, "total": True}

CASES = [
    ("music/eapi/api/cloudsearch/pc", "https://music.163.com/eapi/api/cloudsearch/pc", "/api/cloudsearch/pc"),
    ("iface/eapi/api/cloudsearch/pc", "https://interface.music.163.com/eapi/api/cloudsearch/pc", "/api/cloudsearch/pc"),
    ("iface/eapi/cloudsearch/pc", "https://interface.music.163.com/eapi/cloudsearch/pc", "/cloudsearch/pc"),
    ("music/api/cloudsearch/pc", "https://music.163.com/api/cloudsearch/pc", "/api/cloudsearch/pc"),
    ("iface/eapi/api/search/get", "https://interface.music.163.com/eapi/api/search/get", "/api/search/get"),
    ("music/eapi/api/song/enhance/player/url/v1", "https://music.163.com/eapi/api/song/enhance/player/url/v1",
     "/api/song/enhance/player/url/v1"),
]

HEADERS = {
    "User-Agent": UA,
    "Referer": "https://music.163.com",
    "Content-Type": "application/x-www-form-urlencoded",
    "Cookie": COOKIE,
}


def main() -> None:
    with httpx.Client(timeout=10.0) as c:
        for name, url, cpath in CASES:
            params = eapi(cpath, PAYLOAD if "search" in cpath else {"ids": "[347230]", "level": "standard", "encodeType": "flac"})
            try:
                r = c.post(url, data={"params": params}, headers=HEADERS)
                print(f"[{name}] {r.status_code} :: {r.text[:200].replace(chr(10), ' ')}")
            except Exception as exc:  # noqa: BLE001
                print(f"[{name}] EXC {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
