"""删除功能：任务记录与磁盘文件要能分开处理。

设计约定：
- 删任务默认只删记录；勾了「同时删除本地文件」才动磁盘
- 动磁盘时连同名 .jpg / .lrc 一起删（下载时补写的附件）
- 文件优先丢回收站，环境不支持才直接删
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from lunara.data import DownloadTask, Track  # noqa: E402
from lunara.services.download.service import DownloadService  # noqa: E402


def _task(tmp_path, name: str = "歌手 - 歌名.mp3") -> tuple[DownloadTask, "object"]:
    audio = tmp_path / name
    audio.write_bytes(b"audio")
    (tmp_path / f"{audio.stem}.jpg").write_bytes(b"cover")
    (tmp_path / f"{audio.stem}.lrc").write_text("歌词", encoding="utf-8")
    track = Track(id=1, title="歌名", artist="歌手", album="专辑",
                  duration=100, hue=10, path=str(audio))
    return DownloadTask(id=1, track=track, file_path=str(audio), state="done",
                        bytes_done=5, bytes_total=5), audio


def test_remove_files_takes_sidecars(tmp_path, qt_app) -> None:
    task, audio = _task(tmp_path)
    DownloadService._remove_files(task)

    assert not audio.exists()
    assert not (tmp_path / "歌手 - 歌名.jpg").exists()
    assert not (tmp_path / "歌手 - 歌名.lrc").exists()


def test_remove_files_is_idempotent(tmp_path, qt_app) -> None:
    task, audio = _task(tmp_path)
    audio.unlink()                      # 文件已经没了

    DownloadService._remove_files(task)  # 不能抛异常


def test_missing_sidecars_do_not_break(tmp_path, qt_app) -> None:
    audio = tmp_path / "只有音频.mp3"
    audio.write_bytes(b"x")
    track = Track(id=2, title="只有音频", artist="x", album="y",
                  duration=1, hue=1, path=str(audio))
    task = DownloadTask(id=2, track=track, file_path=str(audio), state="done",
                        bytes_done=1, bytes_total=1)

    DownloadService._remove_files(task)
    assert not audio.exists()
