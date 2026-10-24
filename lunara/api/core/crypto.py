"""eapi 组包：MD5 摘要 + AES-128-ECB（PKCS#7），输出大写 hex。

实测依据（2026-10-24，见 docs/API-PLAN.md「已验证事实」）：
    POST https://music.163.com/eapi/api/cloudsearch/pc
    body: params=<本模块输出的 hex>
    响应: 明文 JSON {"code":200,"result":{...}}，说明组包方式被上游接受。

明文结构：
    {path} + "-36cd479b6b5-" + {json} + "-36cd479b6b5-" + md5("nobody{path}use{json}md5forencrypt")

注意：任务书里写的「AES + RSA 分段」是 weapi 的做法，eapi 实际是上面这一套。
weapi 目前用不到，不实现、不猜测。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

#: eapi 固定密钥（仅存在于 api 层，UI 永不接触）
EAPI_KEY = b"e82ckenh8dichen8"

#: 明文里的分隔符，长度 16，正好一个分组
DIGEST_SEPARATOR = "-36cd479b6b5-"

_BLOCK = 16


def _pkcs7_pad(data: bytes) -> bytes:
    pad = _BLOCK - len(data) % _BLOCK
    return data + bytes([pad]) * pad


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty cipher text")
    pad = data[-1]
    if not 1 <= pad <= _BLOCK or data[-pad:] != bytes([pad]) * pad:
        raise ValueError("bad pkcs7 padding")
    return data[:-pad]


def canonical_json(payload: Mapping[str, Any]) -> str:
    """稳定序列化：紧凑分隔符、保留中文、键序即插入序。

    同一份 payload 必须得到同一个字符串，否则固定测试向量和缓存 key 都不成立。
    """
    return json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=False)


def aes_ecb_encrypt(key: bytes, plain: bytes) -> bytes:
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(_pkcs7_pad(plain)) + encryptor.finalize()


def aes_ecb_decrypt(key: bytes, cipher_text: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return _pkcs7_unpad(decryptor.update(cipher_text) + decryptor.finalize())


def eapi_digest(path: str, payload_json: str) -> str:
    """md5("nobody{path}use{json}md5forencrypt")。"""
    raw = f"nobody{path}use{payload_json}md5forencrypt".encode()
    return hashlib.md5(raw).hexdigest()


def eapi_encrypt(path: str, payload: Mapping[str, Any]) -> str:
    """把 (path, params) 变成可直接塞进 ``params=`` 的大写 hex。"""
    body = canonical_json(payload)
    plain = f"{path}{DIGEST_SEPARATOR}{body}{DIGEST_SEPARATOR}{eapi_digest(path, body)}"
    return aes_ecb_encrypt(EAPI_KEY, plain.encode()).hex().upper()


def eapi_decrypt(hex_text: str) -> str:
    """解回明文。目前上游返回明文 JSON，此函数备用（响应加密时用）。"""
    return aes_ecb_decrypt(EAPI_KEY, bytes.fromhex(hex_text)).decode()
