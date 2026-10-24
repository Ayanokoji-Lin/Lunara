"""登录态加密存储：两条后端、损坏容错、明文不可见。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from lunara.services.secret_store import MAGIC, MODE_AES, MODE_DPAPI, SecretStore

PAYLOAD = {"version": 1, "cookies": {"MUSIC_U": "secret-token-abc", "__csrf": "zzz"}}


def test_aes_roundtrip(tmp_path: Path) -> None:
    store = SecretStore(path=tmp_path / "s.enc", force_aes=True)

    assert store.save(PAYLOAD) is True
    assert store.load() == PAYLOAD
    assert store.backend == "aes-gcm"


@pytest.mark.skipif(os.name != "nt", reason="DPAPI 只在 Windows 上可用")
def test_dpapi_roundtrip(tmp_path: Path) -> None:
    store = SecretStore(path=tmp_path / "s.enc")

    assert store.save(PAYLOAD) is True
    blob = (tmp_path / "s.enc").read_bytes()

    assert blob.startswith(MAGIC + MODE_DPAPI)
    assert store.load() == PAYLOAD
    assert store.backend == "dpapi"


def test_plaintext_is_not_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "s.enc"
    SecretStore(path=path, force_aes=True).save(PAYLOAD)

    raw = path.read_bytes()
    assert b"secret-token-abc" not in raw
    assert b"MUSIC_U" not in raw


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert SecretStore(path=tmp_path / "nope.enc").load() is None


def test_wrong_magic_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "s.enc"
    path.write_bytes(b"XXXX" + MODE_AES + b"\x00" * 40)

    assert SecretStore(path=path, force_aes=True).load() is None


def test_truncated_aes_payload_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "s.enc"
    path.write_bytes(MAGIC + MODE_AES + b"\x00" * 6)

    assert SecretStore(path=path, force_aes=True).load() is None


def test_corrupted_ciphertext_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "s.enc"
    store = SecretStore(path=path, force_aes=True)
    store.save(PAYLOAD)

    blob = bytearray(path.read_bytes())
    blob[-1] ^= 0xFF  # 破坏最后一个字节（GCM tag）
    path.write_bytes(bytes(blob))

    assert store.load() is None


def test_clear_removes_file(tmp_path: Path) -> None:
    path = tmp_path / "s.enc"
    store = SecretStore(path=path, force_aes=True)
    store.save(PAYLOAD)

    store.clear()

    assert store.exists is False
    assert store.load() is None
    store.clear()  # 再清一次不抛错
