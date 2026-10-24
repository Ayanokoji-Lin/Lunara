"""阶段③验收脚本：打印一次直链解析的完整决策轨迹。

    .venv/Scripts/python.exe tools/demo_player_url.py 347230 lossless
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lunara.api import ApiClient  # noqa: E402
from lunara.api.core.logging import configure  # noqa: E402
from lunara.services.async_bridge import run_sync, shutdown  # noqa: E402
from lunara.services.player_url import PlayerUrlService, QualityLevel  # noqa: E402


async def _resolve(song_id: int, level: QualityLevel) -> object:
    async with ApiClient() as client:
        service = PlayerUrlService(client)
        return await service.resolve(song_id, level)


def main() -> int:
    song_id = int(sys.argv[1]) if len(sys.argv) > 1 else 347230
    raw_level = sys.argv[2] if len(sys.argv) > 2 else "lossless"
    level = QualityLevel.parse(raw_level)
    configure()

    try:
        outcome = run_sync(_resolve(song_id, level), timeout=20)
    finally:
        shutdown()

    print("trace:", json.dumps(outcome.trace.to_log(), ensure_ascii=False))  # type: ignore[attr-defined]
    print("available:", outcome.available)  # type: ignore[attr-defined]
    if outcome.result is not None:  # type: ignore[attr-defined]
        result = outcome.result
        print(f"  直链：{result.url[:72]}…")
        print(f"  档位：{result.level.value}（{result.level.label}） 源：{result.source.value} 试听：{result.trial}")
    if outcome.fallback is not None:  # type: ignore[attr-defined]
        fallback = outcome.fallback
        print(f"  兜底试听：{fallback.url[:72]}…（trial={fallback.trial}）")
    if outcome.error is not None:  # type: ignore[attr-defined]
        print(f"  错误码：{outcome.error.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
