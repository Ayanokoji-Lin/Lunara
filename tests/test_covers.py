"""封面服务：缓存路径、请求去重、磁盘读写。

不测 QPixmap 解码（需要 QGuiApplication，且与其它测试的 QCoreApplication 抢实例），
解码路径由 tools/verify_ui_live.py 的真机截图覆盖。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PyQt6.QtCore")

from lunara.services.covers import CoverService  # noqa: E402


class FakeLoop:
    """只记录 submit 次数，不真的跑协程。"""

    def __init__(self) -> None:
        self.calls = 0

    def submit(self, coro: Any) -> None:
        self.calls += 1
        close = getattr(coro, "close", None)
        if close is not None:
            close()


def make_service(tmp_path: Path) -> tuple[CoverService, FakeLoop]:
    loop = FakeLoop()
    return CoverService(loop=loop, cache_dir=tmp_path), loop  # type: ignore[arg-type]


def test_empty_url_returns_none(tmp_path: Path) -> None:
    service, loop = make_service(tmp_path)
    assert service.pixmap(1, "") is None
    assert loop.calls == 0


def test_same_seed_is_requested_once(tmp_path: Path) -> None:
    service, loop = make_service(tmp_path)
    url = "https://p1.music.126.net/demo.jpg"

    assert service.pixmap(1, url) is None
    assert service.pixmap(1, url) is None  # 正在下载，不重复排队
    assert loop.calls == 1


def test_cache_path_is_stable_and_unique(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)

    first = service._cache_path("https://a/1.jpg")
    second = service._cache_path("https://a/1.jpg")
    other = service._cache_path("https://a/2.jpg")

    assert first == second
    assert first != other
    assert first.parent == tmp_path


def test_disk_roundtrip(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    url = "https://p1.music.126.net/demo.jpg"

    assert service._read_disk(url) is None
    service._write_disk(url, b"\x89PNG\r\n\x1a\nfake")
    assert service._read_disk(url) == b"\x89PNG\r\n\x1a\nfake"
