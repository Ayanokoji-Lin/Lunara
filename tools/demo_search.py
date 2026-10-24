"""阶段②验收脚本：走真实上游，把搜索结果显示成播放器要用的字段。

    .venv/Scripts/python.exe tools/demo_search.py 周杰伦

请求是异步的，脚本用后台事件循环（``run_sync``）等结果，和 Qt 里同一套。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lunara.api import ApiClient, ApiError  # noqa: E402 - 需要先补 sys.path
from lunara.api.core.logging import configure  # noqa: E402
from lunara.api.modules.search import search_songs  # noqa: E402
from lunara.services.async_bridge import run_sync, shutdown  # noqa: E402


async def _fetch(keyword: str) -> object:
    async with ApiClient() as client:
        return await search_songs(client, keyword, limit=5)


def main() -> int:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "周杰伦"
    configure()
    try:
        result = run_sync(_fetch(keyword), timeout=15)
    except ApiError as err:
        print(f"失败：{err}")
        return 1
    finally:
        shutdown()

    print(f"关键词「{keyword}」共 {result.song_count} 条，展示前 {len(result)} 条")  # type: ignore[attr-defined]
    print(f"{'ID':>10}  {'时长':>5}  {'VIP':^4}  标题 — 歌手 / 专辑")
    for song in result.songs:  # type: ignore[attr-defined]
        album = song.album.name if song.album else "—"
        vip = "是" if song.vip_only else ""
        print(
            f"{song.id:>10}  {song.duration_seconds:>4}s  {vip:^4}  "
            f"{song.name} — {song.artist_names} / {album}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
