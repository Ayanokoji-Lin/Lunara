"""最近播放（本地记录）。

存在 `%APPDATA%/Lunara/recent.json`：新记录插到最前，按 `id` 去重，最多 100 首。
只存卡片需要的字段，不存整份接口数据——离线也能把列表画出来。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..data import Track
from .paths import APP_DIR

MAX_ITEMS = 100
RECENT_FILE = APP_DIR / "recent.json"


class RecentStore:
    def __init__(self, path: Path = RECENT_FILE, *, max_items: int = MAX_ITEMS) -> None:
        self.path = Path(path)
        self.max_items = max_items
        self._items: list[dict] | None = None

    # ------------------------------------------------------------------ #
    def load(self) -> list[Track]:
        return [_to_track(item) for item in self._ensure_loaded()]

    def add(self, track: Track) -> None:
        if track.id <= 0:
            return
        items = [item for item in self._ensure_loaded() if item.get("id") != track.id]
        items.insert(0, _to_dict(track))
        self._items = items[: self.max_items]
        self._save()

    def clear(self) -> None:
        self._items = []
        self._save()

    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> list[dict]:
        if self._items is not None:
            return self._items
        raw = _read(self.path)
        self._items = [item for item in raw if isinstance(item, dict) and item.get("id")]
        return self._items

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self._items or [], ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass


def _read(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _to_dict(track: Track) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration": track.duration,
        "hue": track.hue,
        "cover_url": track.cover_url,
    }


def _to_track(item: dict) -> Track:
    return Track(
        id=int(item.get("id", 0)),
        title=str(item.get("title", "")),
        artist=str(item.get("artist", "")),
        album=str(item.get("album", "")),
        duration=int(item.get("duration", 0)),
        hue=int(item.get("hue", 0)),
        cover_url=str(item.get("cover_url", "")),
        remote=True,
    )
