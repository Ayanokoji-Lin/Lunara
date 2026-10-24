"""登录态接口探针：确认「我的歌单 / 喜欢的音乐」的真实字段。

需要先在本机登录（session.enc 存在）。只读，不改任何远端数据。

    .venv/Scripts/python.exe tools/probe_account_api.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, ConfigDict  # noqa: E402

from lunara.api import ApiClient  # noqa: E402
from lunara.api.core.logging import configure  # noqa: E402
from lunara.api.endpoints import ACCOUNT_STATUS, SONG_DETAIL, SONG_LIKE, USER_PLAYLIST  # noqa: E402
from lunara.services.account import AccountStore, apply_cookies  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


class Raw(BaseModel):
    """探针专用：字段全收，原样 dump 出来看。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


async def call_raw(client: ApiClient, endpoint, params: dict) -> dict:
    result = await client.call(endpoint, params, model=Raw, unwrap="none", cache="none")
    return result.model_dump()


def save(name: str, payload: dict, *, trim: dict[str, int] | None = None) -> None:
    """存夹具：按 key 截断列表，避免夹具太大。"""
    data = json.loads(json.dumps(payload))
    for key, keep in (trim or {}).items():
        if isinstance(data.get(key), list):
            data[key] = data[key][:keep]
    (FIXTURES / f"{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def main() -> int:
    configure()
    cookies = AccountStore().load()
    if not cookies:
        print("没有登录态，先在应用里登录")
        return 1

    async with ApiClient() as client:
        apply_cookies(client, cookies)

        status = await call_raw(client, ACCOUNT_STATUS, {})
        profile = status.get("profile") or {}
        uid = profile.get("userId")
        print(f"账号：{profile.get('nickname')} uid={uid} vipType={profile.get('vipType')}")
        if not uid:
            print("未取到 uid，可能登录已失效")
            return 1

        # 1) 我的歌单
        playlists = await call_raw(
            client, USER_PLAYLIST, {"uid": uid, "limit": 100, "offset": 0}
        )
        items = playlists.get("playlist") or []
        print(f"\n[user/playlist] code={playlists.get('code')} 数量={len(items)} more={playlists.get('more')}")
        if items:
            first = items[0]
            print("  字段:", sorted(first.keys())[:14])
            print(f"  示例: {first.get('name')} | id={first.get('id')} | "
                  f"trackCount={first.get('trackCount')} | creator={first.get('creator', {}).get('nickname')}")
        save("user_playlists", playlists, trim={"playlist": 6})

        # 2) 喜欢的音乐（只返回 id 列表）
        likes = await call_raw(client, SONG_LIKE, {"uid": uid})
        ids = likes.get("ids") or []
        print(f"\n[song/like] code={likes.get('code')} 数量={len(ids)} 前几个={ids[:5]}")
        save("song_like", likes, trim={"ids": 20})

        # 3) 用 id 反查歌曲详情（喜欢列表要显示成曲目就得走这里）
        if ids:
            detail = await call_raw(
                client,
                SONG_DETAIL,
                {"c": json.dumps([{"id": i} for i in ids[:5]], separators=(",", ":"))},
            )
            songs = detail.get("songs") or []
            print(f"\n[song/detail] code={detail.get('code')} 数量={len(songs)}")
            if songs:
                print("  字段:", sorted(songs[0].keys())[:14])
                print(f"  示例: {songs[0].get('name')} | id={songs[0].get('id')} | dt={songs[0].get('dt')}")
            save("song_detail", detail, trim={"songs": 5, "privileges": 5})

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
