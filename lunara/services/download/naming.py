"""下载文件名与响应头解析（纯函数，方便单测）。

Windows 的文件名规则比 POSIX 严：非法字符、保留设备名、结尾的点与空格都要处理，
否则会在落盘那一刻才报 OSError——那时候已经下载了半天，很亏。
"""
from __future__ import annotations

import re
from pathlib import Path

from ...data import Track

#: Windows 文件名非法字符
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Windows 保留设备名（大小写不敏感）
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

#: 音频扩展名白名单
AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}

#: Content-Type → 扩展名
CONTENT_TYPE_EXT = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}

#: 文件名主干最大长度（给目录与 `.part` 后缀留余量）
MAX_STEM = 100

PART_SUFFIX = ".part"


def sanitize_filename(name: str, *, max_len: int = MAX_STEM) -> str:
    """把任意字符串清洗成 Windows 可用的文件名（不含扩展名）。"""
    cleaned = _INVALID.sub("_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        return "未命名"
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned = "_" + cleaned
    cleaned = cleaned[:max_len].rstrip(" .")
    return cleaned or "未命名"


def build_stem(track: Track) -> str:
    """`歌手 - 歌名`；没有歌手就只用歌名。"""
    title = sanitize_filename(track.title or "未命名")
    artist = (track.artist or "").strip()
    if artist and artist not in ("未知歌手", "未知艺术家"):
        return sanitize_filename(f"{artist} - {title}")
    return title


def guess_extension(url: str, content_type: str | None, quality: str) -> str:
    """扩展名：URL 后缀 > Content-Type > 档位兜底。"""
    suffix = Path(url.split("?")[0]).suffix.lower()
    if suffix in AUDIO_EXTS:
        return suffix

    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime in CONTENT_TYPE_EXT:
            return CONTENT_TYPE_EXT[mime]

    return ".flac" if quality in ("lossless", "hires", "jymaster") else ".mp3"


def part_path(final: Path) -> Path:
    return final.with_name(final.name + PART_SUFFIX)


def unique_path(directory: Path, stem: str, ext: str) -> Path:
    """给一个不冲突的最终路径；`.part` 也算占用，避免续传时撞名。"""
    candidate = directory / f"{stem}{ext}"
    index = 2
    while candidate.exists() or part_path(candidate).exists():
        candidate = directory / f"{stem} ({index}){ext}"
        index += 1
    return candidate


def parse_content_range(value: str | None) -> tuple[int, int, int] | None:
    """解析 ``Content-Range``。

    - ``bytes 100-199/200`` → ``(100, 199, 200)``
    - ``bytes */200`` → ``(-1, -1, 200)``（416 时用来判断是否已下完）
    - 其它 → ``None``
    """
    if not value:
        return None
    text = value.strip()
    if not text.lower().startswith("bytes"):
        return None
    body = text[5:].strip()
    if "/" not in body:
        return None
    span, _, total_text = body.partition("/")
    try:
        total = int(total_text)
    except ValueError:
        return None

    span = span.strip()
    if span == "*":
        return (-1, -1, total)
    start_text, _, end_text = span.partition("-")
    try:
        return (int(start_text), int(end_text), total)
    except ValueError:
        return None


def format_size(num_bytes: int) -> str:
    """给 UI 用的可读大小。"""
    if num_bytes <= 0:
        return "0 MB"
    mb = num_bytes / 1_000_000
    if mb >= 1000:
        return f"{mb / 1000:.2f} GB"
    return f"{mb:.1f} MB"
