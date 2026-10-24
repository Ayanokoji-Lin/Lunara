"""设置持久化（`%APPDATA%/Lunara/settings.json`）。

设计要点：
- **原子写**：先写 `.tmp` 再 `os.replace`，断电不会留下半个 JSON。
- **损坏不崩**：读不出来就整份回默认值，单个字段类型不对就只回该字段。
- **强类型出口**：页面只读 property，不直接碰 dict，避免「字符串 '3' 和整数 3」这类坑。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from .paths import SETTINGS_FILE, default_download_dir
from .player_url.types import QualityLevel

MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 8

#: 下拉里能选的四档（hires / jymaster 不暴露：GD 的 999 已把三档合并成同一文件）
QUALITY_OPTIONS: tuple[tuple[str, QualityLevel], ...] = (
    ("标准 128k", QualityLevel.STANDARD),
    ("较高 192k", QualityLevel.HIGHER),
    ("极高 320k", QualityLevel.EXHIGH),
    ("无损 FLAC", QualityLevel.LOSSLESS),
)


def _defaults() -> dict[str, Any]:
    return {
        "download_dir": str(default_download_dir()),
        "max_concurrent_downloads": 3,
        "notify_on_complete": True,
        "play_quality": QualityLevel.EXHIGH.value,
        "download_quality": QualityLevel.LOSSLESS.value,
        "first_run_notice_seen": False,
    }


class SettingsStore(QObject):
    """一个很小的键值设置仓库。"""

    changed = pyqtSignal(str, object)     # key, value

    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        super().__init__()
        self.path = Path(path)
        self._data: dict[str, Any] = {}
        self._loaded = False

    # ------------------------------------------------------------------ #
    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return self._data.get(key, _defaults().get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._ensure_loaded()
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()
        self.changed.emit(key, value)

    def as_dict(self) -> dict[str, Any]:
        self._ensure_loaded()
        return dict(self._data)

    # ------------------------------------------------------------------ #
    @property
    def download_dir(self) -> Path:
        raw = str(self.get("download_dir") or "")
        return Path(raw) if raw else default_download_dir()

    @property
    def max_concurrent_downloads(self) -> int:
        return _clamp_int(self.get("max_concurrent_downloads"),
                          MIN_CONCURRENCY, MAX_CONCURRENCY, 3)

    @property
    def notify_on_complete(self) -> bool:
        return bool(self.get("notify_on_complete", True))

    @property
    def play_quality(self) -> QualityLevel:
        return _parse_quality(self.get("play_quality"), QualityLevel.EXHIGH)

    @property
    def download_quality(self) -> QualityLevel:
        return _parse_quality(self.get("download_quality"), QualityLevel.LOSSLESS)

    @property
    def first_run_notice_seen(self) -> bool:
        return bool(self.get("first_run_notice_seen", False))

    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._data = _defaults()
        raw = _read_json(self.path)
        if not isinstance(raw, dict):
            return
        for key, default in _defaults().items():
            if key in raw and _same_type(raw[key], default):
                self._data[key] = raw[key]

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            # 设置写不进去不该影响使用，内存里照样生效
            pass


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _same_type(value: Any, default: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, type(default))


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def _parse_quality(value: Any, fallback: QualityLevel) -> QualityLevel:
    if isinstance(value, QualityLevel):
        return value
    try:
        return QualityLevel(str(value))
    except ValueError:
        return fallback


def quality_index(level: QualityLevel) -> int:
    """档位 → 下拉下标；hires / jymaster 折叠到「无损」。"""
    for index, (_, item) in enumerate(QUALITY_OPTIONS):
        if item is level:
            return index
    return len(QUALITY_OPTIONS) - 1


def quality_at(index: int) -> QualityLevel:
    if 0 <= index < len(QUALITY_OPTIONS):
        return QUALITY_OPTIONS[index][1]
    return QUALITY_OPTIONS[0][1]


__all__ = [
    "SettingsStore",
    "QUALITY_OPTIONS",
    "quality_index",
    "quality_at",
    "MAX_CONCURRENCY",
    "MIN_CONCURRENCY",
]
