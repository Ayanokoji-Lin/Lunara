"""文件名清洗、扩展名推断、Content-Range 解析。"""
from __future__ import annotations

from pathlib import Path

import pytest

from lunara.data import Track
from lunara.services.download.naming import (
    build_stem,
    format_size,
    guess_extension,
    parse_content_range,
    part_path,
    sanitize_filename,
    unique_path,
)


def make_track(title: str = "歌", artist: str = "人") -> Track:
    return Track(id=1, title=title, artist=artist, album="专辑", duration=200, hue=10)


@pytest.mark.parametrize("raw", ['a<b>c:d"e/f\\g|h?i*j', "a\x00b\x1fc"])
def test_illegal_chars_are_replaced(raw: str) -> None:
    cleaned = sanitize_filename(raw)

    assert not any(ch in cleaned for ch in '<>:"/\\|?*')
    assert "\x00" not in cleaned


def test_trailing_dots_and_spaces_are_stripped() -> None:
    assert sanitize_filename("  歌名...  ") == "歌名"
    assert sanitize_filename("歌名 . ") == "歌名"


def test_reserved_names_get_prefix() -> None:
    assert sanitize_filename("CON").startswith("_")
    assert sanitize_filename("nul").startswith("_")
    assert sanitize_filename("COM1").startswith("_")
    assert sanitize_filename("CONSOLE") == "CONSOLE"   # 只是前缀相同，不算保留名


def test_empty_becomes_placeholder() -> None:
    assert sanitize_filename("   ") == "未命名"
    assert sanitize_filename("...") == "未命名"


def test_long_name_is_truncated() -> None:
    assert len(sanitize_filename("长" * 300)) == 100


def test_build_stem_uses_artist_and_title() -> None:
    assert build_stem(make_track("晴天", "周杰伦")) == "周杰伦 - 晴天"
    assert build_stem(make_track("晴天", "未知歌手")) == "晴天"
    assert build_stem(make_track("晴天", "")) == "晴天"


def test_build_stem_sanitizes_artist() -> None:
    assert "/" not in build_stem(make_track("A/B", "C:D"))


@pytest.mark.parametrize(
    ("url", "content_type", "quality", "expected"),
    [
        ("https://x/a.flac", None, "standard", ".flac"),
        ("https://x/a.mp3?token=1", None, "lossless", ".mp3"),
        ("https://x/stream", "audio/flac", "standard", ".flac"),
        ("https://x/stream", "audio/mpeg; charset=binary", "standard", ".mp3"),
        ("https://x/stream", None, "lossless", ".flac"),
        ("https://x/stream", None, "exhigh", ".mp3"),
        ("https://x/stream", "application/octet-stream", "hires", ".flac"),
    ],
)
def test_guess_extension(url: str, content_type: str | None, quality: str, expected: str) -> None:
    assert guess_extension(url, content_type, quality) == expected


def test_part_path() -> None:
    assert part_path(Path("a/b.flac")).name == "b.flac.part"


def test_unique_path_avoids_existing(tmp_path: Path) -> None:
    (tmp_path / "人 - 歌.flac").write_bytes(b"x")
    (tmp_path / "人 - 歌 (2).flac.part").write_bytes(b"y")

    path = unique_path(tmp_path, "人 - 歌", ".flac")

    assert path.name == "人 - 歌 (3).flac"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("bytes 100-199/200", (100, 199, 200)),
        ("bytes 0-0/1", (0, 0, 1)),
        ("bytes */200", (-1, -1, 200)),
        ("bytes 5-9/*", None),
        ("items 1-2/3", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_content_range(raw: str | None, expected: tuple[int, int, int] | None) -> None:
    assert parse_content_range(raw) == expected


def test_format_size() -> None:
    assert format_size(0) == "0 MB"
    assert format_size(5_000_000) == "5.0 MB"
    assert format_size(1_500_000_000) == "1.50 GB"
