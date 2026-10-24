"""账号：Cookie 白名单、落盘/恢复、退出清理。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lunara.api.core.cookie import CookieProvider
from lunara.services.account import (
    COOKIE_KEYS,
    AccountStore,
    apply_cookies,
    filter_cookies,
    forget_cookies,
)
from lunara.services.secret_store import SecretStore

LOGIN = {
    "MUSIC_U": "token-abc",
    "__csrf": "csrf-xyz",
    "NMTID": "device-1",
    "_ntes_nuid": "should-be-dropped",
    "JSESSIONID-WYYY": "should-be-dropped",
}


class StubClient:
    """只关心 cookie 的假客户端。"""

    def __init__(self) -> None:
        self.cookie = CookieProvider()


def make_store(tmp_path: Path) -> AccountStore:
    return AccountStore(store=SecretStore(path=tmp_path / "session.enc", force_aes=True))


def test_filter_keeps_whitelist_only() -> None:
    kept = filter_cookies(LOGIN)

    assert set(kept) == set(COOKIE_KEYS)
    assert "JSESSIONID-WYYY" not in kept


def test_filter_drops_empty_values() -> None:
    assert filter_cookies({"MUSIC_U": "", "__csrf": "x"}) == {"__csrf": "x"}


def test_save_requires_login_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.save({"__csrf": "only-csrf"}) is False
    assert store.store.exists is False


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.save(LOGIN) is True
    restored = store.load()

    assert restored["MUSIC_U"] == "token-abc"
    assert restored["__csrf"] == "csrf-xyz"
    assert "_ntes_nuid" not in restored
    assert store.logged_in is True


def test_clear_forgets_login(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(LOGIN)

    store.clear()

    assert store.load() == {}
    assert store.logged_in is False


def test_apply_and_forget_cookies() -> None:
    client = StubClient()

    apply_cookies(client, LOGIN)  # type: ignore[arg-type]
    assert client.cookie.logged_in is True
    assert "MUSIC_U=token-abc" in client.cookie.header()

    forget_cookies(client)  # type: ignore[arg-type]
    assert client.cookie.logged_in is False
    assert "MUSIC_U" not in client.cookie.header()
    assert "os=pc" in client.cookie.header()  # 匿名 Cookie 还在，浏览不受影响


def test_apply_empty_is_noop() -> None:
    client = StubClient()
    before = client.cookie.header()

    apply_cookies(client, {})  # type: ignore[arg-type]

    assert client.cookie.header() == before


def test_load_tolerates_legacy_payload(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    # 直接写一份没有 version 字段的老结构
    store.store.save({"cookies": {"MUSIC_U": "old"}})

    assert store.load() == {"MUSIC_U": "old"}


def test_load_ignores_garbage_payload(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.store.save({"cookies": "not-a-dict"})

    assert store.load() == {}
