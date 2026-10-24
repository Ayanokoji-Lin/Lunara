"""歌词视图：滚动位置必须落在内容里（不能滚到空白）。

这条是为一个真实 bug 写的：旧实现用 ``label.y()`` 算滚动目标，布局还没算完时
拿到的是旧值，上百行歌词会滚到空白处——演示歌词只有十几行，所以一直没暴露。
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.widgets.lyrics import LINE_H, LyricView  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def _settle(app, seconds: float = 0.6) -> None:
    """滚动是 420ms 的动画，得把事件循环转够。"""
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _make_view(app, lines: int = 200) -> LyricView:
    view = LyricView()
    view.resize(640, 520)
    view.show()
    view.set_lyrics([(i * 3000, f"第 {i} 行", "") for i in range(lines)])
    app.processEvents()
    return view


def test_many_lines_scroll_inside_content(app) -> None:
    view = _make_view(app)
    view.set_position(150 * 3000)
    _settle(app)

    offset = view.get_offset()
    content = view._container.height()
    assert offset > 0, "第 150 行应该已经滚下去了"
    assert offset <= content - view.height() + 1, "滚到内容之外了"


def test_first_line_stays_at_top(app) -> None:
    view = _make_view(app)
    view.set_position(0)
    _settle(app)

    # 首行居中会有一点点位移（上留白 260 - 视口一半 260 + 行高一半 20），不该滚远
    assert 0 <= view.get_offset() < 60


def test_offset_shifts_target_line(app) -> None:
    view = _make_view(app)
    view.set_position(100 * 3000)
    _settle(app)
    plain = view.get_offset()

    view.set_offset(-1000)          # 歌词提前 1 秒
    view.set_position(100 * 3000)
    _settle(app)

    assert view.get_offset() != pytest.approx(plain)


def test_translation_lines_are_taller(app) -> None:
    view = LyricView()
    view.resize(640, 520)
    view.set_lyrics([(0, "hello", "你好"), (3000, "world", "世界")])

    assert view._lines[0].height() == LINE_H + 20
