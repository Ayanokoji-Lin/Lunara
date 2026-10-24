"""侧栏回归：分组重建后，导航项不能指向已销毁的按钮。

真实 bug：登录后 ``set_my_playlists`` 会重建分组，但演示分组的 key
（``playlist:N``）没从 ``_items`` 里清掉。等 ``deleteLater`` 生效后，
点任意导航项都会在 ``select()`` 里抛
``RuntimeError: wrapped C/C++ object of type QPushButton has been deleted``。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from lunara.data import Playlist  # noqa: E402
from lunara.widgets.sidebar import Sidebar  # noqa: E402


def _pump(qt_app) -> None:
    """让 deleteLater 真正执行。"""
    qt_app.processEvents()
    qt_app.sendPostedEvents(None, 0)      # 处理 DeferredDelete
    qt_app.processEvents()


def _playlist(pid: int, title: str) -> Playlist:
    return Playlist(id=pid, title=title, author="我", plays=0, hue=200)


def test_select_after_real_playlists(qt_app) -> None:
    side = Sidebar()
    side.set_my_playlists([_playlist(1, "我的歌单")], [_playlist(2, "收藏的")])
    _pump(qt_app)

    side.select("home")          # 不能抛 RuntimeError


def test_select_after_switching_back_to_demo(qt_app) -> None:
    side = Sidebar()
    side.set_my_playlists([_playlist(1, "我的歌单")], [])
    _pump(qt_app)
    side.set_my_playlists([], [])
    _pump(qt_app)

    side.select("home")


def test_dead_entries_are_dropped(qt_app) -> None:
    side = Sidebar()
    before = len(side._items)
    side.set_my_playlists([_playlist(1, "我的歌单")], [])
    _pump(qt_app)

    # 演示分组的 6 个 key 必须被清掉，不能残留死引用
    assert not [k for k in side._items if k.startswith("playlist:")]
    assert len(side._items) < before + 1
