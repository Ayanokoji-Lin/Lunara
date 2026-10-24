"""eapi 探针：用真实上游确认路径 / 参数 / 返回形态。

只读，不改任何东西。跑法：
    .venv/Scripts/python.exe tools/probe_eapi.py
输出每条候选的 HTTP 状态 + 响应前 240 字符，用来把 `// UNVERIFIED` 逐条落实。
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BASE = "https://music.163.com"
EAPI_KEY = b"e82ckenh8dichen8"
SEP = "-36cd479b6b5-"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)


def pkcs7(data: bytes, block: int = 16) -> bytes:
    pad = block - len(data) % block
    return data + bytes([pad]) * pad


def aes_ecb_encrypt_hex(key: bytes, text: str) -> str:
    enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return (enc.update(pkcs7(text.encode())) + enc.finalize()).hex().upper()


def eapi(path: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.md5(f"nobody{path}use{body}md5forencrypt".encode()).hexdigest()
    return aes_ecb_encrypt_hex(EAPI_KEY, f"{path}{SEP}{body}{SEP}{digest}")


CASES: list[tuple[str, str, dict[str, Any]]] = [
    ("search/get", "search/get", {"s": "周杰伦", "type": 1, "limit": 3, "offset": 0, "total": True}),
    ("cloudsearch/pc", "cloudsearch/pc", {"s": "周杰伦", "type": 1, "limit": 3, "offset": 0, "total": True}),
    ("song/enhance/player/url/v1", "song/enhance/player/url/v1",
     {"ids": "[347230]", "level": "standard", "encodeType": "flac"}),
    ("v3/song/detail", "v3/song/detail", {"c": json.dumps([{"id": 347230}])}),
]

HEADERS = {
    "User-Agent": UA,
    "Referer": "https://music.163.com",
    "Content-Type": "application/x-www-form-urlencoded",
    "Cookie": "os=pc; appver=8.9.70; osver=Microsoft-Windows-10-Professional-build-19045-64bit; "
              "channel=netease; __remember_me=true",
}


def main() -> int:
    with httpx.Client(timeout=10.0, follow_redirects=False) as c:
        for name, path, params in CASES:
            enc = eapi(path, params)
            try:
                r = c.post(f"{BASE}/eapi/{path}", data={"params": enc}, headers=HEADERS)
            except Exception as exc:  # noqa: BLE001 - 探针只关心现象
                print(f"[{name}] EXC {type(exc).__name__}: {exc}")
                continue
            body = r.text
            head = body[:240].replace("\n", " ")
            print(f"[{name}] {r.status_code} len={len(body)} :: {head}")
            print(f"    params[:24]={enc[:24]}... sha1={hashlib.sha1(enc.encode()).hexdigest()[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
