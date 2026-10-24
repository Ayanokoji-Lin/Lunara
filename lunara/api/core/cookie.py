"""Cookie 供给。

策略：未登录时用一套匿名 Cookie 保证浏览可用（实测 2026-10-24：搜索与直链接口
在只有匿名 Cookie 的情况下返回 200）；登录态 Cookie 由上层注入，本模块不落盘。

来源优先级：显式注入 > 环境变量 ``LUNARA_MUSIC_U`` > 匿名 Cookie。
// UNVERIFIED: 匿名 Cookie 的官方换取接口（/api/register/anonimous）未验证，
   当前直接用固定匿名串，失效时表现为 code=301（AUTH_REQUIRED），届时再补换取逻辑。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

#: 实测可用的匿名 Cookie 字段（顺序无关）
ANONYMOUS_FIELDS: tuple[tuple[str, str], ...] = (
    ("os", "pc"),
    ("appver", "8.9.70"),
    ("osver", "Microsoft-Windows-10-Professional-build-19045-64bit"),
    ("channel", "netease"),
    ("__remember_me", "true"),
)


@dataclass
class CookieProvider:
    """拼 ``Cookie:`` 头。线程安全（只读快照，写时整体替换）。"""

    _fields: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self._fields:
            self._fields = dict(ANONYMOUS_FIELDS)
        music_u = os.environ.get("LUNARA_MUSIC_U")
        if music_u:
            self._fields["MUSIC_U"] = music_u

    @property
    def logged_in(self) -> bool:
        return bool(self._fields.get("MUSIC_U"))

    def set_login_cookie(self, music_u: str) -> None:
        self._fields["MUSIC_U"] = music_u

    def clear_login_cookie(self) -> None:
        self._fields.pop("MUSIC_U", None)

    def merge(self, extra: Mapping[str, str]) -> None:
        self._fields.update(extra)

    def header(self) -> str:
        return "; ".join(f"{key}={value}" for key, value in self._fields.items())
