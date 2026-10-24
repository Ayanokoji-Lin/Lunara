"""封面图服务：异步下载 + 磁盘/内存缓存。

空态约定（与设计一致）：
- **拿不到图**（无 URL / 还在下载 / 下载失败）→ 控件回落到 ``assets.cover_pixmap``
  的程序化「月牙」封面，看起来就是空态；
- **拿到图** → 解码成 QPixmap，发 ``ready(seed)``，控件重绘成真实封面。

磁盘缓存放在 ``%APPDATA%/Lunara/covers/<sha1(url)>.img``，二次启动直接命中，
不重复下载。图片解码必须在 GUI 线程做，所以下载线程只回传 bytes，
由主线程的 ``_on_bytes`` 负责 ``QPixmap.loadFromData``。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtCore import QBuffer, QByteArray, Qt
from PyQt6.QtGui import QImageReader, QPixmap

from .async_bridge import BackgroundLoop, get_loop

CACHE_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "Lunara" / "covers"

#: 单张封面上限，超过就当失败（防止误下大文件）
MAX_BYTES = 8 * 1024 * 1024

#: 内存里最多留多少张（约 300 × 512px ≈ 300MB 上限，实际远小于此）
MAX_SIDE = 512      # 封面解码上限（显示最大约 400）
MAX_PIXMAPS = 300

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
REFERER = "https://music.163.com/"


def _decode(data: bytes) -> QPixmap | None:
    """按 512px 上限解码：封面最大也就显示 400 出头，原图动辄 1000+。

    ``QImageReader.setScaledSize`` 让解码器直接出小图，比「先解原图再缩放」
    省一大半时间——列表里几十张封面首次出现时的卡顿主要来自这里。
    """
    # 注意：QBuffer 必须自己持有数据副本。写成 QBuffer(QByteArray(data)) 时
    # 那个临时 QByteArray 会立刻析构，reader 读到的是野指针 —— 直接进程消失。
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QBuffer.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > MAX_SIDE:
        reader.setScaledSize(size.scaled(MAX_SIDE, MAX_SIDE,
                                         Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        return None
    return QPixmap.fromImage(image)


class CoverService(QObject):
    """按 ``seed`` 索引封面；同一个 seed 只下载一次。"""

    #: 封面已就绪（参数是 seed），控件据此重绘
    ready = pyqtSignal("qint64")      # seed 就是歌曲 id，可能是 10 位数
    #: 内部用：loop 线程 → 主线程传 bytes
    _bytes_ready = pyqtSignal(int, object)

    def __init__(
        self,
        loop: BackgroundLoop | None = None,
        *,
        cache_dir: Path = CACHE_DIR,
        timeout: float = 10.0,
    ) -> None:
        super().__init__()
        self._loop = loop or get_loop()
        self._dir = Path(cache_dir)
        self._timeout = timeout
        self._pixmaps: dict[int, QPixmap] = {}
        self._pending: set[int] = set()
        self._client: httpx.AsyncClient | None = None
        self._bytes_ready.connect(self._on_bytes)

    # ------------------------------------------------------------------ #
    def pixmap(self, seed: int, url: str) -> QPixmap | None:
        """同步取封面；没有就返回 ``None`` 并顺手发起一次下载。"""
        if not url:
            return None

        cached = self._pixmaps.get(seed)
        if cached is not None:
            return cached

        if seed in self._pending:
            return None

        data = self._read_disk(url)
        if data is not None:
            pixmap = _decode(data)
            if pixmap is not None:
                self._remember(seed, pixmap)
                return pixmap

        self._pending.add(seed)
        try:
            self._loop.submit(self._download(seed, url))
        except Exception:  # noqa: BLE001 - 下载调度失败就当没有封面
            self._pending.discard(seed)
        return None

    def request(self, seed: int, url: str) -> None:
        """只发起下载、不解码。

        列表里的卡片要滚到可视区才会 paint；不预热的话，屏幕外的封面永远不下载，
        滚过去时先看到空态月牙，再等一轮网络才换图。
        """
        if not url or seed in self._pixmaps or seed in self._pending:
            return
        if self._read_disk(url) is not None:
            return                      # 磁盘里有，等绘制时再解码
        self._pending.add(seed)
        try:
            self._loop.submit(self._download(seed, url))
        except Exception:  # noqa: BLE001
            self._pending.discard(seed)

    def cached(self, seed: int) -> QPixmap | None:
        return self._pixmaps.get(seed)

    # ------------------------------------------------------------------ #
    def _remember(self, seed: int, pixmap: QPixmap) -> None:
        if len(self._pixmaps) >= MAX_PIXMAPS:
            self._pixmaps.pop(next(iter(self._pixmaps)), None)
        self._pixmaps[seed] = pixmap

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode()).hexdigest()
        return self._dir / f"{digest}.img"

    def _read_disk(self, url: str) -> bytes | None:
        path = self._cache_path(url)
        try:
            return path.read_bytes() if path.exists() else None
        except OSError:
            return None

    def _write_disk(self, url: str, data: bytes) -> None:
        path = self._cache_path(url)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError:
            pass  # 缓存写不进去不影响显示

    # ------------------------------------------------------------------ #
    async def _download(self, seed: int, url: str) -> None:
        """在后台 loop 线程执行；结果通过信号回主线程解码。"""
        data: bytes | None = None
        try:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=self._timeout,
                    headers={"User-Agent": USER_AGENT, "Referer": REFERER},
                    follow_redirects=True,
                )
            response = await self._client.get(url)
            if response.status_code == 200 and 0 < len(response.content) <= MAX_BYTES:
                data = response.content
                self._write_disk(url, data)
        except Exception:  # noqa: BLE001 - 封面失败不该影响播放
            data = None
        self._bytes_ready.emit(seed, data)

    def _on_bytes(self, seed: int, data: object) -> None:
        """主线程：解码 + 通知控件。"""
        self._pending.discard(seed)
        if not isinstance(data, (bytes, bytearray)):
            return
        pixmap = _decode(bytes(data))
        if pixmap is not None:
            self._remember(seed, pixmap)
            self.ready.emit(seed)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_service: CoverService | None = None


def covers() -> CoverService:
    """进程级单例。"""
    global _service
    if _service is None:
        _service = CoverService()
    return _service


def reset_covers() -> None:
    """测试用：丢弃单例（不关连接池，调用方自己负责）。"""
    global _service
    _service = None
