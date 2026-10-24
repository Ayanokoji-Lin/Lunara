"""播放队列持久化：退出时存、启动时读。

只存「队列 + 当前索引」，不自动开播——用户没点播放就不该出声。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..data import Track
from .paths import APP_DIR

QUEUE_FILE = APP_DIR / "queue.json"
MAX_ITEMS = 200


def save(tracks: list[Track], index: int, path: Path = QUEUE_FILE) -> None:
    if not tracks:
        _write(path, {"index": 0, "tracks": []})
        return
    _write(path, {
        "index": max(0, min(index, len(tracks) - 1)),
        "tracks": [_to_dict(t) for t in tracks[:MAX_ITEMS]],
    })


def load(path: Path = QUEUE_FILE) -> tuple[list[Track], int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], 0
    if not isinstance(data, dict):
        return [], 0
    tracks = [_to_track(item) for item in data.get("tracks") or [] if isinstance(item, dict)]
    tracks = [t for t in tracks if t.id != 0]
    index = int(data.get("index") or 0)
    return tracks, max(0, min(index, max(0, len(tracks) - 1)))


def _write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _to_dict(track: Track) -> dict:
    return {
        "id": track.id, "title": track.title, "artist": track.artist,
        "album": track.album, "duration": track.duration, "hue": track.hue,
        "cover_url": track.cover_url, "path": track.path, "remote": track.remote,
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
        remote=bool(item.get("remote", True)),
        path=str(item.get("path", "")),
    )
