"""本地曲库：扫描目录、读标签，变成可以播放的 Track。

- 用 ``mutagen`` 读 flac / mp3 / m4a 的标题、歌手、专辑、时长；读不到就用文件名。
- ``Track.path`` 非空时播放器直接放本地文件，不走直链解析。
- id 取路径哈希的负数，和线上曲目（正数）天然不冲突。
"""
from __future__ import annotations

import zlib
from pathlib import Path

from ..data import Track
from ..services.catalog import hue_for

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".wav", ".ogg", ".ape"}


def scan(root: str | Path, *, limit: int = 500) -> list[Track]:
    """扫目录（不递归太深，最多两层），返回按文件名排序的曲目。"""
    base = Path(root)
    if not base.exists():
        return []

    files: list[Path] = []
    for path in sorted(base.rglob("*")):
        if len(files) >= limit:
            break
        if path.suffix.lower() in AUDIO_SUFFIXES and path.is_file():
            files.append(path)

    return [read_track(path) for path in files]


def read_track(path: Path) -> Track:
    title, artist, album, seconds = path.stem, "", "", 0
    try:
        from mutagen import File as MutagenFile  # 延迟导入，没装也能跑

        audio = MutagenFile(str(path), easy=True)
        if audio is not None:
            tags = audio.tags or {}
            title = _first(tags.get("title")) or title
            artist = _first(tags.get("artist"))
            album = _first(tags.get("album"))
            seconds = int(round(float(getattr(audio.info, "length", 0) or 0)))
    except Exception:  # noqa: BLE001 - 读标签失败不该影响列表
        pass

    # 文件名形如「歌手 - 歌名」时补一下歌手
    if not artist and " - " in title:
        head, _, tail = title.partition(" - ")
        artist, title = head.strip(), tail.strip()

    return Track(
        id=-_stable_id(path),
        title=title,
        artist=artist or "未知歌手",
        album=album or "本地文件",
        duration=seconds,
        hue=hue_for(zlib.crc32(str(path).encode("utf-8"))),
        remote=False,
        path=str(path),
    )


def _first(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value else ""


def _stable_id(path: Path) -> int:
    return zlib.crc32(str(path.resolve()).encode("utf-8")) % 1_000_000_000 + 1
