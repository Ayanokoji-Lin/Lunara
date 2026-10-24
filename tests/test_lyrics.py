"""LRC 解析：真实歌词 + 各种边角写法。"""
from __future__ import annotations

import json
from pathlib import Path

from lunara.api.models.lyric import LyricResponse
from lunara.services.lyrics import parse_lrc, parse_lyric_response

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_real_lyric() -> None:
    payload = json.loads((FIXTURES / "lyric.json").read_text(encoding="utf-8"))
    lines = parse_lyric_response(LyricResponse.model_validate(payload))

    assert len(lines) > 10
    assert lines[0][0] == 0
    assert isinstance(lines[0][1], str) and lines[0][1]
    # 时间必须单调不减
    assert all(a[0] <= b[0] for a, b in zip(lines, lines[1:]))
    # 元信息行（作词/作曲）也在里面，这是正常的，LyricView 会照常显示
    assert any("作词" in text for _, text in lines)


def test_centiseconds_and_milliseconds() -> None:
    assert parse_lrc("[00:01.5]a") == [(1500, "a")]
    assert parse_lrc("[00:01.50]b") == [(1500, "b")]
    assert parse_lrc("[00:01.500]c") == [(1500, "c")]
    assert parse_lrc("[01:02]d") == [(62_000, "d")]


def test_multiple_tags_on_one_line() -> None:
    assert parse_lrc("[00:10.00][01:20.00]副歌") == [(10_000, "副歌"), (80_000, "副歌")]


def test_skips_blank_and_untimed_lines() -> None:
    text = "\n".join(
        [
            "[ti:歌名]",          # 元信息，无 mm:ss 形式
            "[ar:歌手]",
            "[00:05.00]",         # 只有时间没有文本
            "[00:06.00]   ",
            "[00:07.00]有效",
            "没有时间标签的行",
        ]
    )
    assert parse_lrc(text) == [(7000, "有效")]


def test_dedupes_identical_lines() -> None:
    assert parse_lrc("[00:03.00]重复\n[00:03.00]重复") == [(3000, "重复")]


def test_sorts_out_of_order_input() -> None:
    assert parse_lrc("[00:09.00]后\n[00:02.00]前") == [(2000, "前"), (9000, "后")]


def test_empty_input() -> None:
    assert parse_lrc("") == []
    assert parse_lrc("   \n  ") == []


def test_empty_response_falls_back_cleanly() -> None:
    assert parse_lyric_response(LyricResponse.model_validate({"lrc": {"lyric": ""}})) == []
