"""歌曲表格：行数变了必须重算高度。

真实 bug：给表格加右键菜单时，把 ``_sync_height()`` 从 ``set_tracks`` 末尾
误挪到了 ``contextMenuEvent`` 末尾。结果任何一次 ``set_tracks`` 之后高度都停在
「表头 + 40px」，歌单里 891 首歌只显示表头——数据和模型都是对的，就是看不见。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from lunara.data import Track  # noqa: E402
from lunara.widgets.track_table import TrackDelegate, TrackTable  # noqa: E402


def _tracks(count: int) -> list[Track]:
    return [Track(id=i + 1, title=f"歌 {i}", artist="歌手", album="专辑",
                  duration=200, hue=200) for i in range(count)]


def _expected(count: int) -> int:
    return count * TrackDelegate.ROW_H + 40


def test_height_follows_row_count(qt_app) -> None:
    table = TrackTable()
    table.set_tracks(_tracks(5))
    assert table.height() == _expected(5)


def test_height_shrinks_and_grows(qt_app) -> None:
    table = TrackTable()
    table.set_tracks(_tracks(40))
    assert table.height() == _expected(40)

    table.set_tracks(_tracks(3))
    assert table.height() == _expected(3), "换成短列表后高度必须跟着缩回去"

    table.set_tracks([])
    assert table.height() == _expected(0)


def test_891_rows_are_tall_enough_to_show(qt_app) -> None:
    table = TrackTable()
    table.set_tracks(_tracks(891))
    assert table.height() > 1000, "大歌单不能只剩表头"
