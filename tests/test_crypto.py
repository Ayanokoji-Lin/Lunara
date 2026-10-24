"""eapi 组包固定向量。

``VECTOR_HEX`` 的来历（不是自己算完自己认）：
    2026-10-24 把该 hex 原样 POST 到 https://music.163.com/eapi/api/cloudsearch/pc，
    上游回 HTTP 200 / code 200 / songCount 276 / songs 3（首条「想你就写信 (Live)」）。
    也就是说：这个向量是「被上游接受过」的密文，改坏任何一个字节都会掉到 code 400。
"""
from __future__ import annotations

import pytest

from lunara.api.core import crypto

VECTOR_PATH = "/api/cloudsearch/pc"
VECTOR_PARAMS = {"s": "周杰伦", "type": 1, "limit": 3, "offset": 0, "total": True}
VECTOR_MD5 = "535d84df0290eb1fe00394623ef15481"
VECTOR_HEX = (
    "2B5D64177AA6460FBAA3DCB1285E28954BBB4F7556E09B0FB25750F12398BB50"
    "61D31369B8FFA4BFF59E3B4A9103C9EFC4A9F27F2EB9646649834AF9158B1E0F"
    "6574ED1604FEED06594B8F3A35ACDC27AA01EC621C2F98959D73503B675810130"
    "6B1D9D7F78AFD2AC5F03963D3BD746256C90146017D76159BB695135A13A087E"
    "FD04765F3BE987D4472E72ABE52F9FF"
)


def test_fixed_vector_hex() -> None:
    assert crypto.eapi_encrypt(VECTOR_PATH, VECTOR_PARAMS) == VECTOR_HEX


def test_fixed_vector_digest() -> None:
    body = crypto.canonical_json(VECTOR_PARAMS)
    assert crypto.eapi_digest(VECTOR_PATH, body) == VECTOR_MD5


def test_plaintext_layout() -> None:
    """明文必须是 path + 分隔符 + json + 分隔符 + md5。"""
    body = crypto.canonical_json(VECTOR_PARAMS)
    plain = crypto.eapi_decrypt(VECTOR_HEX)
    assert plain == f"{VECTOR_PATH}-36cd479b6b5-{body}-36cd479b6b5-{VECTOR_MD5}"


def test_hex_is_uppercase_and_block_aligned() -> None:
    assert VECTOR_HEX == VECTOR_HEX.upper()
    assert len(VECTOR_HEX) % 32 == 0  # 16 字节一组，hex 一组 32 字符


def test_canonical_json_is_stable() -> None:
    first = crypto.canonical_json(VECTOR_PARAMS)
    second = crypto.canonical_json(dict(VECTOR_PARAMS))
    assert first == second
    assert " " not in first.replace("周杰伦", "")
    assert "周杰伦" in first  # 中文不能被转成 \uXXXX


def test_different_params_give_different_cipher() -> None:
    other = {**VECTOR_PARAMS, "offset": 3}
    assert crypto.eapi_encrypt(VECTOR_PATH, other) != VECTOR_HEX


def test_pkcs7_always_pads() -> None:
    """整块明文也要补一整块，这是 PKCS#7 的规矩。"""
    cipher_text = crypto.aes_ecb_encrypt(crypto.EAPI_KEY, b"0" * 16)
    assert len(cipher_text) == 32
    assert crypto.aes_ecb_decrypt(crypto.EAPI_KEY, cipher_text) == b"0" * 16


def test_bad_padding_rejected() -> None:
    with pytest.raises(ValueError):
        crypto.aes_ecb_decrypt(crypto.EAPI_KEY, b"\x00" * 16)
