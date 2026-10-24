"""下载任务表：建表、往返、唯一约束、崩溃恢复、损坏自愈。"""
from __future__ import annotations

from pathlib import Path

from lunara.data import DownloadTask, Track
from lunara.services.download.store import SCHEMA_VERSION, DownloadStore


def make_track(song_id: int = 1, title: str = "歌") -> Track:
    return Track(id=song_id, title=title, artist="人", album="专辑",
                 duration=200, hue=10, cover_url="https://x/c.jpg")


def make_task(song_id: int = 1, **kwargs) -> DownloadTask:
    return DownloadTask(track=make_track(song_id), **kwargs)


def open_store(tmp_path: Path) -> DownloadStore:
    return DownloadStore(tmp_path / "tasks.db")


def test_schema_version(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    version = store._conn().execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_insert_and_load(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    task = make_task(state="queued", quality="lossless")
    task_id = store.insert(task)

    assert task_id > 0 and task.id == task_id
    loaded = store.load_all()
    assert len(loaded) == 1
    row = loaded[0]
    assert row.track.id == 1
    assert row.track.title == "歌"
    assert row.track.cover_url == "https://x/c.jpg"
    assert row.state == "queued"
    assert row.quality == "lossless"


def test_song_id_is_unique(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    first = store.insert(make_task(1))
    second = store.insert(make_task(1))

    assert first == second
    assert len(store.load_all()) == 1


def test_update_roundtrip(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    task = make_task()
    store.insert(task)
    task.state = "done"
    task.bytes_total = 1_000
    task.bytes_done = 1_000
    task.file_path = "D:/Music/Lunara/x.flac"
    store.update(task)

    row = DownloadStore(tmp_path / "tasks.db").load_all()[0]

    assert (row.state, row.bytes_total, row.bytes_done) == ("done", 1000, 1000)
    assert row.file_path.endswith("x.flac")


def test_update_progress(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    task = make_task()
    store.insert(task)

    store.update_progress(task.id, 512, 1024)

    row = store.load_all()[0]
    assert (row.bytes_done, row.bytes_total) == (512, 1024)


def test_mark_interrupted(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.insert(make_task(1, state="downloading"))
    store.insert(make_task(2, state="done"))
    store.insert(make_task(3, state="paused"))

    changed = store.mark_interrupted()

    states = {row.track.id: row.state for row in store.load_all()}
    assert changed == 1
    assert states == {1: "queued", 2: "done", 3: "paused"}


def test_delete(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    task = make_task()
    store.insert(task)

    store.delete(task.id)

    assert store.load_all() == []


def test_ordering_is_stable(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    for song_id in (3, 1, 2):
        task = make_task(song_id, created_at=float(song_id))
        store.insert(task)

    assert [row.track.id for row in store.load_all()] == [1, 2, 3]


def test_corrupt_db_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "tasks.db"
    path.write_bytes(b"this is not a sqlite file" * 10)

    store = DownloadStore(path)          # 不该抛异常
    assert store.load_all() == []
    assert any(p.name.startswith("tasks.db.corrupt-") for p in tmp_path.iterdir())
