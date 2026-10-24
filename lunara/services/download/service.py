"""下载服务：调度、流式下载、断点续传、状态持久化。

线程模型
--------
- **主线程**：持有 ``_mirror``（UI 用的副本），只读；所有控制方法把协程丢给后台 loop。
- **后台 loop 线程**：持有 ``_live``（权威状态）、httpx 客户端、SQLite 连接，负责真正的下载。
- 两者之间只通过信号传递**不可变事件**，不共享可变对象，所以没有锁。

并发上限
--------
不用 ``asyncio.Semaphore``：设置页要能实时改上限，而 Semaphore 建好之后不能安全缩容。
这里用「调度器 + 整数上限」——每轮 ``_pump()`` 只补到上限为止，任务结束时再补一次。
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Sequence

import httpx
from PyQt6.QtCore import QObject, pyqtSignal

from ...data import DownloadTask, Track
from ..async_bridge import BackgroundLoop, get_loop, run_sync
from ..error_text import error_text
from ..player_url.service import PlayerUrlService
from ..player_url.types import QualityLevel, ResolvedUrl
from .naming import (
    build_stem,
    guess_extension,
    parse_content_range,
    part_path,
    unique_path,
)
from .store import DownloadStore

#: 进度回传间隔（秒）：4Hz 足够顺滑，又不会把主线程刷爆
EMIT_INTERVAL = 0.25
#: 单次读块大小
CHUNK_SIZE = 64 * 1024
#: 网络类失败的重试次数与退避
MAX_RETRIES = 3
RETRY_BACKOFF = (0.5, 1.0, 2.0)
#: 进度写库间隔（秒）
PERSIST_INTERVAL = 1.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
REFERER = "https://music.163.com/"


class DownloadError(Exception):
    """可展示给用户的下载错误。"""


class _LinkExpired(Exception):
    """直链过期（403/410），需要重新解析。"""


class _Retryable(Exception):
    """网络抖动/5xx，值得重试。"""


class _RestartFromZero(Exception):
    """服务端忽略 Range，必须从头下。"""


@dataclass
class _Runtime:
    """每个任务的非持久化运行时状态（速度、上次回传时间）。"""

    last_emit: float = 0.0
    last_t: float = 0.0
    last_bytes: int = 0
    speed: float = 0.0


@dataclass(frozen=True, slots=True)
class DownloadEvent:
    task_id: int
    state: str
    bytes_done: int
    bytes_total: int
    speed: float
    error: str
    file_path: str


class DownloadService(QObject):
    taskAdded = pyqtSignal(object)       # DownloadTask（副本）
    taskChanged = pyqtSignal(object)     # DownloadEvent
    taskRemoved = pyqtSignal(int)        # task_id
    taskFinished = pyqtSignal(object)    # DownloadTask（副本）
    errorRaised = pyqtSignal(str)        # 全局错误（目录不可写等）

    def __init__(
        self,
        resolver: PlayerUrlService,
        store: DownloadStore,
        *,
        download_dir: Callable[[], Path] | None = None,
        concurrency: int = 3,
        loop: BackgroundLoop | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        self._resolver = resolver
        self._store = store
        self._dir_of = download_dir or (lambda: Path.home() / "Music" / "Lunara")
        self._limit = max(1, int(concurrency))
        self._retries = MAX_RETRIES
        self.last_skipped = 0
        self._min_interval = 0.0     # 每秒最少耗时，用于限速；0 = 不限速
        self._loop = loop or get_loop()
        self._client = client
        self._owns_client = client is None

        rows = store.load_all()
        # 主线程副本（UI 读这个）与 loop 线程权威副本（下载改这个）各一份
        self._mirror: dict[int, DownloadTask] = {row.id: row for row in rows}
        self._live: dict[int, DownloadTask] = {row.id: replace(row) for row in rows}
        self._jobs: dict[int, asyncio.Task] = {}
        self._rt: dict[int, _Runtime] = {}
        self._closing = False
        self._started = False

        self.taskAdded.connect(self._on_task_added)
        self.taskChanged.connect(self._on_task_changed)
        self.taskRemoved.connect(self._on_task_removed)

    # ------------------------------------------------------------------ #
    # 主线程接口
    # ------------------------------------------------------------------ #
    def tasks(self) -> list[DownloadTask]:
        return sorted(self._mirror.values(), key=lambda t: (t.created_at, t.id))

    def start(self) -> None:
        """恢复上次没跑完的任务并开始调度。"""
        if self._started:
            return
        self._started = True
        self._loop.submit(self._start())

    def enqueue(self, track: Track, *, quality: str | None = None) -> int:
        return self.enqueue_many([track], quality=quality)

    def enqueue_many(self, tracks: Sequence[Track], *, quality: str | None = None) -> int:
        """加入队列；已在队列里、或磁盘上已有同名文件的都跳过。返回**实际新增**的数量。"""
        known = {task.track.id for task in self._mirror.values()}
        directory = self._dir_of()
        on_disk: set[str] = set()
        if directory.exists():
            on_disk = {path.stem for path in directory.glob("*") if path.is_file()}

        fresh: list[Track] = []
        self.last_skipped = 0
        for track in tracks:
            if track.id in known:
                continue
            stem = f"{track.artist} - {track.title}"
            if any(name == stem or name.startswith(stem + " (") for name in on_disk):
                self.last_skipped += 1
                continue
            known.add(track.id)
            fresh.append(track)
        if fresh:
            level = quality or QualityLevel.LOSSLESS.value
            self._loop.submit(self._enqueue(fresh, level))
        return len(fresh)

    def import_done(self, tasks: Sequence[DownloadTask]) -> int:
        """把磁盘上已有、任务表里没有的文件补登记成「已完成」。"""
        known = {Path(task.file_path).name for task in self._mirror.values()}
        added = 0
        for task in tasks:
            if Path(task.file_path).name in known:
                continue
            task_id = self._store.insert(task)
            task.id = task_id
            self._mirror[task_id] = task
            self._live[task_id] = replace(task)
            self.taskAdded.emit(replace(task))
            added += 1
        return added

    def pause(self, task_id: int) -> None:
        self._loop.submit(self._pause(task_id))

    def resume(self, task_id: int) -> None:
        self._loop.submit(self._resume(task_id))

    def retry(self, task_id: int) -> None:
        self._loop.submit(self._resume(task_id, reset_error=True))

    def delete(self, task_id: int) -> None:
        self._loop.submit(self._delete(task_id))

    def pause_all(self) -> None:
        for task_id, task in list(self._mirror.items()):
            if task.state in ("queued", "downloading"):
                self.pause(task_id)

    def resume_all(self) -> None:
        for task_id, task in list(self._mirror.items()):
            if task.state in ("paused", "failed"):
                self.resume(task_id)

    def set_concurrency(self, limit: int) -> None:
        self._limit = max(1, int(limit))
        self._loop.submit(self._pump())

    def set_limits(self, *, retries: int | None = None,
                   speed_kbps: int | None = None) -> None:
        """重试次数与限速（``speed_kbps <= 0`` 表示不限速）。"""
        if retries is not None:
            self._retries = max(0, min(10, int(retries)))
        if speed_kbps is not None:
            kbps = int(speed_kbps)
            # 每块 64KB：限速 1MB/s → 每块至少 64/1024 秒
            self._min_interval = (CHUNK_SIZE / 1024) / kbps if kbps > 0 else 0.0

    def shutdown(self, timeout: float = 3.0) -> None:
        try:
            run_sync(self._shutdown(), timeout=timeout)
        except Exception:  # noqa: BLE001 - 退出路径不该再抛
            pass

    # ------------------------------------------------------------------ #
    # loop 线程：调度
    # ------------------------------------------------------------------ #
    async def _start(self) -> None:
        """恢复上次没跑完的任务：DB 与内存副本都改回 queued，再开始调度。"""
        self._store.mark_interrupted()
        for task in self._live.values():
            if task.state == "downloading":
                task.state = "queued"
        await self._pump()

    async def _enqueue(self, tracks: Sequence[Track], quality: str) -> None:
        directory = Path(self._dir_of())
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.errorRaised.emit(f"下载目录不可用：{exc}")
            return

        for track in tracks:
            if any(item.track.id == track.id for item in self._live.values()):
                continue
            task = DownloadTask(track=track, quality=quality, state="queued",
                                created_at=time.time())
            stem = build_stem(track)
            ext = guess_extension("", None, quality)
            task.file_path = str(unique_path(directory, stem, ext))
            self._store.insert(task)
            self._live[task.id] = task
            self.taskAdded.emit(replace(task))

        await self._pump()

    async def _pump(self) -> None:
        if self._closing:
            return
        while len(self._jobs) < self._limit:
            task = next(
                (item for item in sorted(self._live.values(), key=lambda t: (t.created_at, t.id))
                 if item.state == "queued"),
                None,
            )
            if task is None:
                return
            task.state = "downloading"
            self._store.update(task)
            self._emit(task, force=True)
            self._jobs[task.id] = asyncio.create_task(self._run(task.id))

    # ------------------------------------------------------------------ #
    # loop 线程：单个任务
    # ------------------------------------------------------------------ #
    async def _run(self, task_id: int) -> None:
        task = self._live[task_id]
        try:
            resolved = await self._resolve(task)
            ext = guess_extension(resolved.url, None, task.quality)
            final = Path(task.file_path)
            if final.suffix.lower() != ext:
                final = final.with_suffix(ext)
                task.file_path = str(final)

            try:
                await self._download(task, resolved.url)
            except _LinkExpired:
                resolved = await self._resolve(task, force=True)
                await self._download(task, resolved.url)

            self._finalize(task)
        except asyncio.CancelledError:
            raise
        except DownloadError as exc:
            self._fail(task, str(exc))
        except Exception as exc:  # noqa: BLE001 - 任何意外都落到任务行，不炸 loop
            detail = str(exc).strip() or type(exc).__name__
            self._fail(task, f"下载失败：{detail}")
        finally:
            self._jobs.pop(task_id, None)
            if not self._closing:
                await self._pump()

    async def _resolve(self, task: DownloadTask, *, force: bool = False) -> ResolvedUrl:
        level = QualityLevel.parse(task.quality)
        outcome = await self._resolver.resolve(task.track.id, level, use_cache=not force)

        if outcome.available and outcome.result is not None and not outcome.result.trial:
            return outcome.result
        if outcome.fallback is not None:
            raise DownloadError("该歌曲仅提供 45 秒试听，无法下载完整版")
        raise DownloadError(error_text(outcome.error, "无法获取下载地址"))

    async def _download(self, task: DownloadTask, url: str) -> None:
        """带重试的流式下载（Range 续传）。"""
        for attempt in range(self._retries + 1):
            try:
                await self._stream_once(task, url)
                return
            except _RestartFromZero:
                # 服务端忽略 Range：清掉半截文件，从 0 再来一次（只重试一次）
                self._unlink_part(task)
                task.bytes_done = 0
                try:
                    await self._stream_once(task, url)
                except _RestartFromZero as exc:
                    raise DownloadError("服务器不接受断点续传，重新下载也失败了") from exc
                return
            except _Retryable as exc:
                if attempt >= self._retries:
                    raise DownloadError(f"网络中断：{exc}") from exc
                await asyncio.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
            except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                if attempt >= self._retries:
                    raise DownloadError("下载超时，请检查网络后重试") from exc
                await asyncio.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
            except httpx.HTTPError as exc:
                if attempt >= self._retries:
                    raise DownloadError(f"网络中断：{exc or type(exc).__name__}") from exc
                await asyncio.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])

    async def _stream_once(self, task: DownloadTask, url: str) -> None:
        client = await self._ensure_client()
        final = Path(task.file_path)
        part = part_path(final)
        offset = part.stat().st_size if part.exists() else 0

        headers = {"Accept-Encoding": "identity", "Referer": REFERER}
        if offset:
            headers["Range"] = f"bytes={offset}-"

        async with client.stream("GET", url, headers=headers) as response:
            if response.status_code == 416:
                span = parse_content_range(response.headers.get("Content-Range"))
                if span and span[2] and offset >= span[2]:
                    task.bytes_total = task.bytes_done = span[2]
                    return
                raise _RestartFromZero
            if response.status_code in (403, 410):
                raise _LinkExpired
            if response.status_code >= 500:
                raise _Retryable(f"HTTP {response.status_code}")
            if response.status_code >= 400:
                raise DownloadError(f"服务器返回 {response.status_code}")

            if response.status_code == 200 and offset:
                raise _RestartFromZero

            span = parse_content_range(response.headers.get("Content-Range"))
            if span:
                task.bytes_total = span[2]
            else:
                length = response.headers.get("Content-Length")
                if length and length.isdigit():
                    task.bytes_total = offset + int(length)

            part.parent.mkdir(parents=True, exist_ok=True)
            mode = "ab" if offset else "wb"
            written = offset
            last_persist = 0.0
            with open(part, mode) as handle:
                async for chunk in response.aiter_bytes(CHUNK_SIZE):
                    if not chunk:
                        continue
                    if self._min_interval:
                        started = time.monotonic()
                    handle.write(chunk)
                    written += len(chunk)
                    task.bytes_done = written
                    self._emit(task)
                    if self._min_interval:
                        gap = self._min_interval - (time.monotonic() - started)
                        if gap > 0:
                            await asyncio.sleep(gap)
                    now = time.monotonic()
                    if now - last_persist >= PERSIST_INTERVAL:
                        last_persist = now
                        self._store.update_progress(task.id, written, task.bytes_total)
                handle.flush()

        task.bytes_done = written
        if not task.bytes_total:
            task.bytes_total = written
        self._store.update_progress(task.id, task.bytes_done, task.bytes_total)

    # ------------------------------------------------------------------ #
    # loop 线程：状态变更
    # ------------------------------------------------------------------ #
    async def _pause(self, task_id: int) -> None:
        task = self._live.get(task_id)
        if task is None or task.state not in ("queued", "downloading"):
            return

        task.state = "paused"
        task.speed = 0.0
        job = self._jobs.pop(task_id, None)
        if job is not None:
            job.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await job
        task.bytes_done = self._part_size(task)
        self._store.update(task)
        self._emit(task, force=True)

    async def _resume(self, task_id: int, *, reset_error: bool = False) -> None:
        task = self._live.get(task_id)
        if task is None or task.state in ("queued", "downloading", "done"):
            return
        task.state = "queued"
        if reset_error:
            task.error = ""
        self._store.update(task)
        self._emit(task, force=True)
        await self._pump()

    async def _delete(self, task_id: int) -> None:
        task = self._live.pop(task_id, None)
        if task is None:
            return
        job = self._jobs.pop(task_id, None)
        if job is not None:
            job.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await job
        self._unlink_part(task)
        self._rt.pop(task_id, None)
        self._store.delete(task_id)
        self.taskRemoved.emit(task_id)

    async def _shutdown(self) -> None:
        self._closing = True
        jobs = list(self._jobs.items())
        for task_id, _job in jobs:
            task = self._live.get(task_id)
            if task is not None and task.state == "downloading":
                task.state = "queued"          # 下次启动自动续传
                task.bytes_done = self._part_size(task)
                task.speed = 0.0
                self._store.update(task)
        for _task_id, job in jobs:
            job.cancel()
        for _task_id, job in jobs:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await job
        self._jobs.clear()

        if self._client is not None and self._owns_client:
            with contextlib.suppress(Exception):
                await self._client.aclose()
            self._client = None
        self._store.close()

    # ------------------------------------------------------------------ #
    # 工具
    # ------------------------------------------------------------------ #
    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": USER_AGENT, "Referer": REFERER},
                follow_redirects=True,
            )
        return self._client

    def _finalize(self, task: DownloadTask) -> None:
        final = Path(task.file_path)
        part = part_path(final)
        try:
            os.replace(part, final)
        except OSError as exc:
            self._fail(task, f"文件落盘失败：{exc}")
            return

        task.state = "done"
        task.speed = 0.0
        task.error = ""
        task.bytes_total = task.bytes_total or task.bytes_done
        self._store.update(task)
        self._emit(task, force=True)
        self.taskFinished.emit(replace(task))

    def _fail(self, task: DownloadTask, message: str) -> None:
        task.state = "failed"
        task.speed = 0.0
        task.error = message
        task.bytes_done = self._part_size(task)
        self._store.update(task)
        self._emit(task, force=True)

    def _part_size(self, task: DownloadTask) -> int:
        if not task.file_path:
            return 0
        part = part_path(Path(task.file_path))
        try:
            return part.stat().st_size if part.exists() else task.bytes_done
        except OSError:
            return task.bytes_done

    def _unlink_part(self, task: DownloadTask) -> None:
        if not task.file_path:
            return
        with contextlib.suppress(OSError):
            part_path(Path(task.file_path)).unlink(missing_ok=True)

    def _runtime(self, task: DownloadTask) -> _Runtime:
        rt = self._rt.get(task.id)
        if rt is None:
            rt = _Runtime(last_t=time.monotonic(), last_bytes=task.bytes_done)
            self._rt[task.id] = rt
        return rt

    def _emit(self, task: DownloadTask, *, force: bool = False) -> None:
        now = time.monotonic()
        rt = self._runtime(task)
        if not force and now - rt.last_emit < EMIT_INTERVAL:
            return
        rt.last_emit = now
        task.speed = self._speed(task, rt, now)
        self.taskChanged.emit(
            DownloadEvent(
                task_id=task.id,
                state=task.state,
                bytes_done=task.bytes_done,
                bytes_total=task.bytes_total,
                speed=task.speed,
                error=task.error,
                file_path=task.file_path,
            )
        )

    def _speed(self, task: DownloadTask, rt: _Runtime, now: float) -> float:
        """EWMA 速度，避免数字乱跳；不落库。"""
        delta_t = max(1e-3, now - rt.last_t)
        instant = max(0.0, (task.bytes_done - rt.last_bytes) / delta_t / 1_000_000)
        rt.speed = rt.speed * 0.7 + instant * 0.3
        rt.last_t, rt.last_bytes = now, task.bytes_done
        return round(rt.speed, 2)

    # ------------------------------------------------------------------ #
    # 主线程：镜像同步
    # ------------------------------------------------------------------ #
    def _on_task_added(self, task: DownloadTask) -> None:
        self._mirror[task.id] = task

    def _on_task_changed(self, event: DownloadEvent) -> None:
        task = self._mirror.get(event.task_id)
        if task is not None:
            self.apply(task, event)

    def _on_task_removed(self, task_id: int) -> None:
        self._mirror.pop(task_id, None)

    #: 供主线程把事件应用到自己的副本上（页面直接调用）
    @staticmethod
    def apply(task: DownloadTask, event: DownloadEvent) -> None:
        task.state = event.state
        task.bytes_done = event.bytes_done
        task.bytes_total = event.bytes_total
        task.speed = event.speed
        task.error = event.error
        task.file_path = event.file_path
