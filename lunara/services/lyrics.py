"""LRC 解析。

`LyricView.set_lyrics()` 的入参是 ``list[tuple[int, str]]``（毫秒, 文本），
而接口给的是标准 LRC 文本，这里做一次转换。

支持的写法（都来自真实回包）：
    [00:18.466]今天我 寒夜里看雪飘
    [00:00.000] 作词 : 黄家驹
    [01:02]一句话（没有小数）
    [00:12.5]两位小数 = 厘秒
    一行多个时间标签：[00:10.00][01:20.00]副歌
"""
from __future__ import annotations

import re

from ..api.models.lyric import LyricResponse

_LINE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _fraction_to_ms(fraction: str | None) -> int:
    if not fraction:
        return 0
    digits = len(fraction)
    value = int(fraction)
    if digits == 1:  # 十分之一秒
        return value * 100
    if digits == 2:  # 厘秒
        return value * 10
    return value  # 毫秒


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """LRC → ``[(毫秒, 文本)]``，按时间升序，丢掉空行与重复行。

    解析不出任何时间标签时返回空列表（调用方回退演示歌词）。
    """
    if not text:
        return []

    lines: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    for raw in text.splitlines():
        stamps = list(_LINE.finditer(raw))
        if not stamps:
            continue
        content = _LINE.sub("", raw).strip()
        if not content:
            continue
        for stamp in stamps:
            minutes, seconds, fraction = stamp.groups()
            ms = int(minutes) * 60_000 + int(seconds) * 1000 + _fraction_to_ms(fraction)
            key = (ms, content)
            if key in seen:
                continue
            seen.add(key)
            lines.append(key)

    lines.sort(key=lambda item: item[0])
    return lines


def parse_lyric_response(response: LyricResponse) -> list[tuple[int, str]]:
    """接口响应 → 可直接喂给 ``LyricView`` 的列表。"""
    return parse_lrc(response.text)
