"""id 信号必须用 qint64，不能用 int。

真实 bug：网易云有些歌单/专辑 id 是 10 位数（如 17854472861），超过 2^31。
``pyqtSignal(int)`` 在 PyQt 里对应 C++ 的 32 位 int，emit 时会被截断成负数，
下游拿到 ``id <= 0`` 就报「playlist id 必须为正整数」，或者卡片点了没反应。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from lunara.core.player import Player  # noqa: E402
from lunara.pages.grid import GridPage  # noqa: E402
from lunara.pages.search import SearchPage  # noqa: E402

BIG_ID = 17854472861          # 2^31 约等于 2.1e9，这个数一定会溢出


def test_grid_card_signal_keeps_large_id(qt_app) -> None:
    grid = GridPage()
    got: list[int] = []
    grid.cardActivated.connect(got.append)

    grid.cardActivated.emit(BIG_ID)
    assert got == [BIG_ID]


def test_search_signals_keep_large_id(qt_app) -> None:
    page = SearchPage(Player(engine="clock"))
    got: dict[str, int] = {}
    for name in ("playlistActivated", "artistActivated", "albumActivated"):
        signal = getattr(page, name)
        signal.connect(lambda value, key=name: got.setdefault(key, value))
        signal.emit(BIG_ID)

    assert len(got) == 3
    assert all(value == BIG_ID for value in got.values())
