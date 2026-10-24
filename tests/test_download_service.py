"""下载服务：全量、续传、忽略 Range、416、直链过期、重试、试听拒绝、并发上限。

全部用 httpx.MockTransport，不联网；把后台 loop 换成「直接在当前事件循环里跑」，
这样断言可以写成顺序代码。
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from lunara.api.errors import ErrorCode
from lunara.data import Track
from lunara.services.download import service as service_module
from lunara.services.download.service import DownloadService
from lunara.services.download.store import DownloadStore
from lunara.services.player_url.types import (
    QualityLevel,
    ResolvedUrl,
    ResolveOutcome,
    ResolveTrace,
    UrlSource,
)

PAYLOAD = bytes(range(256)) * 400        # 102_400 字节，够分几个 chunk
URL = "https://cdn.example.com/song.flac"


class DirectLoop:
    """把 submit 变成当前事件循环里的 create_task，测试里可以直接 await。"""

    def __init__(self) -> None:
        self.pending: list[asyncio.Task] = []

    def submit(self, coro: Any) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.pending.append(task)
        return task

    async def drain(self) -> None:
        while self.pending:
            batch, self.pending = self.pending, []
            await asyncio.gather(*batch)


class StubResolver:
    """假直链服务：按顺序返回预设结果。"""

    def __init__(self, urls: list[str] | None = None, *, trial: bool = False,
                 available: bool = True) -> None:
        self.urls = list(urls or [URL])
        self.trial = trial
        self.available = available
        self.calls = 0

    async def resolve(self, song_id: int, level: QualityLevel | None = None,
                      *, use_cache: bool = True) -> ResolveOutcome:
        self.calls += 1
        url = self.urls[min(self.calls - 1, len(self.urls) - 1)]
        resolved = ResolvedUrl(url=url, level=QualityLevel.LOSSLESS,
                               expires_at=time.time() + 600,
                               source=UrlSource.OFFICIAL, trial=self.trial)
        trace = ResolveTrace(song_id=song_id, level=QualityLevel.LOSSLESS,
                             tried_providers=("official",),
                             final_source=UrlSource.OFFICIAL if self.available else None,
                             latency_ms=1.0, fail_reason=None)
        if self.available:
            return ResolveOutcome(available=True, result=resolved, fallback=None,
                                  trace=trace, error=None)
        return ResolveOutcome(available=False, result=None,
                              fallback=resolved if self.trial else None,
                              trace=trace, error=ErrorCode.URL_UNAVAILABLE)


def make_track(song_id: int = 1) -> Track:
    return Track(id=song_id, title=f"歌{song_id}", artist="人", album="专辑",
                 duration=200, hue=10, cover_url="https://x/c.jpg")


def make_service(tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response],
                 resolver: Any = None, *, concurrency: int = 2,
                 download_dir: Path | None = None,
                 store: DownloadStore | None = None,
                 autostart: bool = False) -> tuple[DownloadService, DirectLoop, DownloadStore]:
    loop = DirectLoop()
    store = store or DownloadStore(tmp_path / "tasks.db")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = DownloadService(
        resolver or StubResolver(),
        store,
        download_dir=lambda: download_dir or (tmp_path / "out"),
        concurrency=concurrency,
        loop=loop,          # type: ignore[arg-type]
        client=client,
    )
    if autostart:
        service.start()
    return service, loop, store


def seed_task(store: DownloadStore, out: Path, *, song_id: int = 1,
              part_bytes: int = 0, state: str = "queued") -> Path:
    """模拟「上次留下的任务」：DB 里已有行，磁盘上已有 .part。"""
    from lunara.data import DownloadTask

    final = out / f"人 - 歌{song_id}.flac"
    if part_bytes:
        final.with_name(final.name + ".part").write_bytes(PAYLOAD[:part_bytes])
    store.insert(DownloadTask(track=make_track(song_id), state=state,
                              file_path=str(final), created_at=time.time()))
    return final


def full_handler(payload: bytes = PAYLOAD, status: int = 200) -> Callable[..., httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload,
                              headers={"Content-Type": "audio/flac"})
    return handler


async def run_until_idle(service: DownloadService, loop: DirectLoop) -> None:
    await loop.drain()
    # _pump 里 create_task 的任务在 jobs 里，等它们结束
    while service._jobs:
        await asyncio.gather(*list(service._jobs.values()), return_exceptions=True)
        await loop.drain()


# --------------------------------------------------------------------------- #
async def test_full_download(tmp_path: Path) -> None:
    service, loop, store = make_service(tmp_path, full_handler())
    service.enqueue(make_track(1))
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "done"
    assert task.bytes_total == len(PAYLOAD)
    assert task.bytes_done == len(PAYLOAD)
    final = Path(task.file_path)
    assert final.read_bytes() == PAYLOAD
    assert not final.with_name(final.name + ".part").exists()
    assert store.load_all()[0].state == "done"


async def test_resume_sends_range(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    store = DownloadStore(tmp_path / "tasks.db")
    final = seed_task(store, out, part_bytes=1000)

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["range"] = request.headers.get("range", "")
        start = int(seen["range"].split("=")[1].rstrip("-"))
        return httpx.Response(
            206,
            content=PAYLOAD[start:],
            headers={"Content-Range": f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"},
        )

    service, loop, _ = make_service(tmp_path, handler, download_dir=out,
                                    store=store, autostart=True)
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert seen["range"] == "bytes=1000-"
    assert task.state == "done"
    assert Path(task.file_path).read_bytes() == PAYLOAD


async def test_server_ignores_range_restarts(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    store = DownloadStore(tmp_path / "tasks.db")
    final = seed_task(store, out, part_bytes=999)

    service, loop, _ = make_service(tmp_path, full_handler(), download_dir=out,
                                    store=store, autostart=True)
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "done"
    assert Path(task.file_path).read_bytes() == PAYLOAD


async def test_416_when_already_complete(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    store = DownloadStore(tmp_path / "tasks.db")
    final = seed_task(store, out, part_bytes=len(PAYLOAD))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(416, headers={"Content-Range": f"bytes */{len(PAYLOAD)}"})

    service, loop, _ = make_service(tmp_path, handler, download_dir=out,
                                    store=store, autostart=True)
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "done"
    assert Path(task.file_path).read_bytes() == PAYLOAD


async def test_link_expired_resolves_again(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if str(request.url).endswith("expired"):
            return httpx.Response(403)
        return httpx.Response(200, content=PAYLOAD)

    resolver = StubResolver(["https://cdn.example.com/expired", URL])
    service, loop, _ = make_service(tmp_path, handler, resolver=resolver)
    service.enqueue(make_track(1))
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "done"
    assert resolver.calls == 2


async def test_retryable_5xx_then_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "RETRY_BACKOFF", (0.0, 0.0, 0.0))
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, content=PAYLOAD)

    service, loop, _ = make_service(tmp_path, handler)
    service.enqueue(make_track(1))
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "done"
    assert state["n"] == 3


async def test_trial_only_is_rejected(tmp_path: Path) -> None:
    resolver = StubResolver(available=False, trial=True)
    service, loop, _ = make_service(tmp_path, full_handler(), resolver=resolver)
    service.enqueue(make_track(1))
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "failed"
    assert "试听" in task.error
    assert not Path(task.file_path).exists()


async def test_concurrency_limit_and_raise(tmp_path: Path) -> None:
    active = {"now": 0, "max": 0}

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):  # type: ignore[override]
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
            try:
                for _ in range(3):
                    await asyncio.sleep(0.01)
                    yield b"x" * 1024
            finally:
                active["now"] -= 1

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream())

    service, loop, _ = make_service(tmp_path, handler, concurrency=2)
    for song_id in (1, 2, 3):
        service.enqueue(make_track(song_id))

    await asyncio.sleep(0.02)
    assert active["max"] == 2          # 第三个在排队

    service.set_concurrency(3)
    await run_until_idle(service, loop)

    assert active["max"] == 3
    assert all(task.state == "done" for task in service.tasks())


async def test_pause_keeps_part(tmp_path: Path) -> None:
    started = asyncio.Event()

    chunk = b"a" * service_module.CHUNK_SIZE      # 够一块，aiter_bytes 才会吐出来

    class BlockingStream(httpx.AsyncByteStream):
        async def __aiter__(self):  # type: ignore[override]
            yield chunk
            started.set()
            await asyncio.sleep(5)     # 卡住，等被取消
            yield chunk

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=BlockingStream(),
                              headers={"Content-Length": str(len(chunk) * 2)})

    service, loop, _ = make_service(tmp_path, handler)
    service.enqueue(make_track(1))
    await asyncio.sleep(0)
    await started.wait()

    task_id = service.tasks()[0].id
    service.pause(task_id)
    await run_until_idle(service, loop)

    task = service.tasks()[0]
    assert task.state == "paused"
    assert task.bytes_done == len(chunk)
    assert Path(task.file_path + ".part").stat().st_size == task.bytes_done


async def test_restart_resumes_queued(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    store = DownloadStore(tmp_path / "tasks.db")
    final = seed_task(store, out, part_bytes=500, state="downloading")

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.headers.get("range", "bytes=0-").split("=")[1].rstrip("-"))
        return httpx.Response(206, content=PAYLOAD[start:],
                              headers={"Content-Range":
                                       f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"})

    service, loop, _ = make_service(tmp_path, handler, download_dir=out,
                                    store=store, autostart=True)
    await run_until_idle(service, loop)

    assert service.tasks()[0].state == "done"
    assert final.read_bytes() == PAYLOAD
