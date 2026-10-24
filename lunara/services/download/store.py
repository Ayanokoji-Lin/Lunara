"""下载任务表（SQLite）。

为什么落库：下载是「跨越进程生命周期」的操作，暂停后关掉应用、明天再开还要能续。
任务行的曲目元数据是**反范式存**的——重启后不必再请求接口就能把列表画出来。

线程：每个线程一个连接（``threading.local``）。主线程只在启动时 ``load_all()``，
之后的读写都在后台 loop 线程里发生；WAL + busy_timeout 让两边不互相卡住。
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from ...data import DownloadTask, Track
from ..paths import TASKS_DB

SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS download_tasks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  song_id     INTEGER NOT NULL,
  title       TEXT    NOT NULL,
  artist      TEXT    NOT NULL DEFAULT '',
  album       TEXT    NOT NULL DEFAULT '',
  duration    INTEGER NOT NULL DEFAULT 0,
  hue         INTEGER NOT NULL DEFAULT 0,
  cover_url   TEXT    NOT NULL DEFAULT '',
  quality     TEXT    NOT NULL DEFAULT 'lossless',
  file_path   TEXT    NOT NULL DEFAULT '',
  bytes_total INTEGER NOT NULL DEFAULT 0,
  bytes_done  INTEGER NOT NULL DEFAULT 0,
  state       TEXT    NOT NULL DEFAULT 'queued'
              CHECK(state IN ('queued','downloading','paused','done','failed')),
  error       TEXT    NOT NULL DEFAULT '',
  created_at  REAL    NOT NULL,
  updated_at  REAL    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_download_song ON download_tasks(song_id);
CREATE INDEX IF NOT EXISTS ix_download_state ON download_tasks(state);
"""


class DownloadStore:
    """任务表的读写门面。所有方法都可能被不同线程调用。"""

    def __init__(self, path: Path = TASKS_DB) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self._ensure_schema()

    # ------------------------------------------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            return conn

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = self._open()
        except sqlite3.DatabaseError:
            # 文件损坏：备份后重建，宁可丢任务也不要开不了应用
            self._quarantine()
            conn = self._open()

        self._local.conn = conn
        return conn

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
        except sqlite3.DatabaseError:
            # 必须先关掉：Windows 上被打开的文件改不了名，隔离会失败
            conn.close()
            raise
        return conn

    def _quarantine(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(self.path) + suffix)
            if candidate.exists():
                try:
                    candidate.replace(Path(str(candidate) + f".corrupt-{int(time.time())}"))
                except OSError:
                    pass

    def _ensure_schema(self) -> None:
        conn = self._conn()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            conn.executescript(SCHEMA_V1)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.commit()

    # ------------------------------------------------------------------ #
    def load_all(self) -> list[DownloadTask]:
        rows = self._conn().execute(
            "SELECT * FROM download_tasks ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [_row_to_task(row) for row in rows]

    def insert(self, task: DownloadTask) -> int:
        """入库；``song_id`` 已存在时复用原行（返回已有 id）。"""
        now = time.time()
        task.created_at = task.created_at or now
        task.updated_at = now
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO download_tasks
                   (song_id, title, artist, album, duration, hue, cover_url, quality,
                    file_path, bytes_total, bytes_done, state, error, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task.track.id, task.track.title, task.track.artist, task.track.album,
                    task.track.duration, task.track.hue, task.track.cover_url,
                    task.quality, task.file_path, task.bytes_total, task.bytes_done,
                    task.state, task.error, task.created_at, task.updated_at,
                ),
            )
            conn.commit()
            task.id = int(cursor.lastrowid or 0)
            return task.id
        except sqlite3.IntegrityError:
            row = conn.execute(
                "SELECT id FROM download_tasks WHERE song_id = ?", (task.track.id,)
            ).fetchone()
            task.id = int(row["id"]) if row else 0
            return task.id

    def update(self, task: DownloadTask) -> None:
        if task.id <= 0:
            return
        task.updated_at = time.time()
        conn = self._conn()
        conn.execute(
            """UPDATE download_tasks SET
                 file_path=?, bytes_total=?, bytes_done=?, state=?, error=?,
                 quality=?, updated_at=?
               WHERE id=?""",
            (task.file_path, task.bytes_total, task.bytes_done, task.state,
             task.error, task.quality, task.updated_at, task.id),
        )
        conn.commit()

    def update_progress(self, task_id: int, bytes_done: int, bytes_total: int) -> None:
        conn = self._conn()
        conn.execute(
            "UPDATE download_tasks SET bytes_done=?, bytes_total=?, updated_at=? WHERE id=?",
            (bytes_done, bytes_total, time.time(), task_id),
        )
        conn.commit()

    def delete(self, task_id: int) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM download_tasks WHERE id=?", (task_id,))
        conn.commit()

    def mark_interrupted(self) -> int:
        """把上次没跑完的任务改回 queued（崩溃/强杀后恢复用）。"""
        conn = self._conn()
        cursor = conn.execute(
            "UPDATE download_tasks SET state='queued', updated_at=? WHERE state='downloading'",
            (time.time(),),
        )
        conn.commit()
        return int(cursor.rowcount or 0)

    def close(self) -> None:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


def _row_to_task(row: sqlite3.Row) -> DownloadTask:
    track = Track(
        id=int(row["song_id"]),
        title=row["title"],
        artist=row["artist"],
        album=row["album"],
        duration=int(row["duration"]),
        hue=int(row["hue"]),
        cover_url=row["cover_url"],
        remote=True,
    )
    return DownloadTask(
        track=track,
        id=int(row["id"]),
        quality=row["quality"],
        state=row["state"],
        bytes_total=int(row["bytes_total"]),
        bytes_done=int(row["bytes_done"]),
        file_path=row["file_path"],
        error=row["error"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
