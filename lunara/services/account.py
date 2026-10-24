"""账号：登录态的保存 / 恢复 / 清除。

只保存真正需要的几个 Cookie 键，不把整份 Cookie 搬进来：
- ``MUSIC_U``：登录凭据，所有接口都靠它
- ``__csrf``：写操作（喜欢 / 收藏 / 新建歌单）要带
- ``NMTID``：网页端的设备标识，部分接口会校验

文件由 :class:`SecretStore` 加密（DPAPI 或 AES-GCM），路径见 ``SESSION_FILE``。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..api.client import ApiClient
from .secret_store import SESSION_FILE, SecretStore

#: 允许落盘的键（其余一律丢弃，避免把统计类 Cookie 也存下来）
COOKIE_KEYS: tuple[str, ...] = ("MUSIC_U", "__csrf", "NMTID")

#: 登录凭据的键名
LOGIN_KEY = "MUSIC_U"

SCHEMA_VERSION = 1


def filter_cookies(cookies: Mapping[str, str]) -> dict[str, str]:
    """只保留白名单里的键，且值非空。"""
    return {
        key: value
        for key, value in cookies.items()
        if key in COOKIE_KEYS and isinstance(value, str) and value
    }


@dataclass
class AccountStore:
    """登录态的读写门面。"""

    store: SecretStore = field(default_factory=lambda: SecretStore(path=SESSION_FILE))

    def save(self, cookies: Mapping[str, str]) -> bool:
        kept = filter_cookies(cookies)
        if LOGIN_KEY not in kept:
            return False
        return self.store.save({"version": SCHEMA_VERSION, "cookies": kept})

    def load(self) -> dict[str, str]:
        payload = self.store.load()
        if not payload:
            return {}
        cookies = payload.get("cookies")
        if not isinstance(cookies, dict):
            return {}
        kept = filter_cookies({str(k): str(v) for k, v in cookies.items()})
        return kept if LOGIN_KEY in kept else {}

    def clear(self) -> None:
        self.store.clear()

    @property
    def logged_in(self) -> bool:
        return LOGIN_KEY in self.load()


def apply_cookies(client: ApiClient, cookies: Mapping[str, str]) -> None:
    """把登录 Cookie 灌进请求层。"""
    if cookies:
        client.cookie.merge(dict(cookies))


def forget_cookies(client: ApiClient) -> None:
    """退出登录：把登录相关的键从请求层摘掉，回落到匿名。"""
    client.cookie.remove(COOKIE_KEYS)
