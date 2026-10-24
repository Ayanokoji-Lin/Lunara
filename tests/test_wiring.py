"""接线检查：每个 pyqtSignal 都必须有人 connect。

真实 bug：`grid_page.cardActivated` 从来没被连接过——网格页（播客 / 新歌速递 /
更多歌单 / 歌手专辑）的卡片点了完全没反应，而且不报错、不提示，纯粹静默。
同类问题还波及「下载」按钮、表格右键三项、首页两个「更多」。

这种 bug 用功能测试很难覆盖（要点到才知道），用静态检查最划算。
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "lunara"


def _sources() -> dict[pathlib.Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py")}


def test_every_signal_is_connected() -> None:
    sources = _sources()
    all_text = "\n".join(sources.values())

    declared: dict[str, set[str]] = {}
    for path, text in sources.items():
        for match in re.finditer(r"^\s{4}(\w+)\s*=\s*pyqtSignal\(", text, re.M):
            declared.setdefault(match.group(1), set()).add(path.name)

    dead = sorted(
        name for name in declared
        if not re.search(rf"\.{name}\.connect\(", all_text)
    )
    assert not dead, f"这些信号发出去没人接（点了没反应）：{dead}"
