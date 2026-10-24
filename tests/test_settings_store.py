"""设置存储：默认值、往返、原子写、损坏容错、类型钳制。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lunara.services.player_url.types import QualityLevel
from lunara.services.settings_store import (
    QUALITY_OPTIONS,
    SettingsStore,
    quality_at,
    quality_index,
)


def make_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(tmp_path / "settings.json")


def test_defaults(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.max_concurrent_downloads == 3
    assert store.notify_on_complete is True
    assert store.play_quality is QualityLevel.EXHIGH
    assert store.download_quality is QualityLevel.LOSSLESS
    assert store.first_run_notice_seen is False
    assert store.download_dir.name == "Lunara"


def test_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.set("max_concurrent_downloads", 5)
    store.set("play_quality", "lossless")
    store.set("first_run_notice_seen", True)

    again = make_store(tmp_path)

    assert again.max_concurrent_downloads == 5
    assert again.play_quality is QualityLevel.LOSSLESS
    assert again.first_run_notice_seen is True


def test_atomic_write_leaves_no_tmp(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.set("notify_on_complete", False)

    assert not (tmp_path / "settings.tmp").exists()
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))[
        "notify_on_complete"] is False


def test_corrupt_json_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")

    store = SettingsStore(path)

    assert store.max_concurrent_downloads == 3
    assert store.play_quality is QualityLevel.EXHIGH


def test_wrong_type_only_resets_that_field(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "max_concurrent_downloads": "五个",     # 类型错
        "notify_on_complete": False,           # 正常
    }), encoding="utf-8")

    store = SettingsStore(path)

    assert store.max_concurrent_downloads == 3
    assert store.notify_on_complete is False


@pytest.mark.parametrize(("raw", "expected"), [(0, 1), (99, 8), (5, 5)])
def test_concurrency_is_clamped(tmp_path: Path, raw: int, expected: int) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"max_concurrent_downloads": raw}), encoding="utf-8")

    assert SettingsStore(path).max_concurrent_downloads == expected


def test_unknown_quality_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"play_quality": "ultra-max"}), encoding="utf-8")

    assert SettingsStore(path).play_quality is QualityLevel.EXHIGH


def test_changed_signal(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seen: list[tuple[str, object]] = []
    store.changed.connect(lambda key, value: seen.append((key, value)))

    store.set("notify_on_complete", False)
    store.set("notify_on_complete", False)   # 同值不重复发

    assert seen == [("notify_on_complete", False)]


def test_quality_options_map_both_ways() -> None:
    for index, (_, level) in enumerate(QUALITY_OPTIONS):
        assert quality_index(level) == index
        assert quality_at(index) is level
    # hires / jymaster 折叠到「无损」
    assert quality_index(QualityLevel.HIRES) == len(QUALITY_OPTIONS) - 1
    assert quality_index(QualityLevel.JYMASTER) == len(QUALITY_OPTIONS) - 1
