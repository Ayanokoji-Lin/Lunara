"""播放内核的纯逻辑：时钟引擎、切歌、seek 钳制、直链序号竞态。

不碰声卡、不联网：``engine="clock"`` 用虚拟时钟；直链流程用一个假的 media 对象，
只记录 ``setSource/play/pause/stop/setPosition`` 调用。
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("PyQt6.QtCore")

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from lunara.core.player import ENGINE_CLOCK, ENGINE_MEDIA, MODE_SINGLE, Player  # noqa: E402
from lunara.data import Track  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class FakeMedia:
    """只记录调用，不做任何解码。"""

    def __init__(self) -> None:
        self.source = ""
        self.played = 0
        self.paused = 0
        self.stopped = 0
        self.position = 0

    def setSource(self, url: Any) -> None:  # noqa: N802 - 对齐 Qt 命名
        self.source = url.toString()

    def play(self) -> None:
        self.played += 1

    def pause(self) -> None:
        self.paused += 1

    def stop(self) -> None:
        self.stopped += 1

    def setPosition(self, ms: int) -> None:  # noqa: N802
        self.position = ms


def make_track(song_id: int = 1, *, remote: bool = False, duration: int = 200) -> Track:
    return Track(id=song_id, title=f"歌{song_id}", artist="人", album="专辑",
                 duration=duration, hue=10, remote=remote)


def clock_player() -> Player:
    return Player(engine="clock")


def media_player() -> tuple[Player, FakeMedia]:
    player = Player(engine="clock")
    fake = FakeMedia()
    player._engine = ENGINE_MEDIA
    player._media = fake
    return player, fake


# --------------------------------------------------------------------------- #
def test_engine_clock_explicit() -> None:
    assert clock_player().engine == ENGINE_CLOCK


def test_play_pause_emits() -> None:
    player = clock_player()
    seen: list[bool] = []
    player.playingChanged.connect(seen.append)
    player.set_queue([make_track()], autoplay=False)

    player.play()
    player.pause()

    assert seen == [True, False]


def test_clock_tick_advances() -> None:
    player = clock_player()
    positions: list[tuple[int, int]] = []
    player.positionChanged.connect(lambda pos, dur: positions.append((pos, dur)))
    player.set_queue([make_track(duration=200)], autoplay=False)
    player.play()

    player._tick()
    player._tick()

    assert player.position == 200
    assert positions[-1] == (200, 200_000)


def test_clock_tick_does_not_run_when_paused() -> None:
    player = clock_player()
    player.set_queue([make_track()], autoplay=False)
    player.play()
    player.pause()

    player._tick()

    assert player.position == 0


def test_next_track_wraps_around() -> None:
    player = clock_player()
    player.set_queue([make_track(1), make_track(2)], autoplay=False)

    player.next_track()

    assert player.current is not None and player.current.id == 2
    player.next_track()
    assert player.current.id == 1


def test_prev_track_restarts_when_past_4s() -> None:
    player = clock_player()
    player.set_queue([make_track(1), make_track(2)], index=1, autoplay=False)
    player.seek(5000)

    player.prev_track()

    assert player.current.id == 2      # 没换歌
    assert player.position == 0        # 只是回到开头


def test_prev_track_goes_back_when_early() -> None:
    player = clock_player()
    player.set_queue([make_track(1), make_track(2)], index=1, autoplay=False)
    player.seek(1000)

    player.prev_track()

    assert player.current.id == 1


def test_seek_is_clamped_to_duration() -> None:
    player = clock_player()
    player.set_queue([make_track(duration=200)], autoplay=False)

    player.seek(999_999)
    assert player.position == 200_000

    player.seek(-5)
    assert player.position == 0


def test_duration_falls_back_to_track() -> None:
    player = clock_player()
    player.set_queue([make_track(duration=123)], autoplay=False)

    assert player.duration_ms == 123_000


def test_demo_track_never_requests_url() -> None:
    player, fake = media_player()
    seen: list[int] = []
    player.urlRequested.connect(lambda seq, track: seen.append(seq))

    player.set_queue([make_track(remote=False)], autoplay=True)

    assert seen == []
    assert fake.source == ""


def test_remote_track_requests_url_then_plays() -> None:
    player, fake = media_player()
    seen: list[int] = []
    player.urlRequested.connect(lambda seq, track: seen.append(seq))

    player.set_queue([make_track(remote=True)], autoplay=True)

    assert seen == [1]
    player.set_source(1, "https://cdn.example.com/a.flac", False)
    assert fake.source == "https://cdn.example.com/a.flac"
    assert fake.played == 1


def test_stale_resolution_is_dropped() -> None:
    player, fake = media_player()
    tracks = [make_track(1, remote=True), make_track(2, remote=True)]
    player.set_queue(tracks, autoplay=True)

    player.next_track()                     # seq 2
    player.set_source(1, "https://cdn.example.com/old.flac", False)

    assert fake.source == ""                # 迟到的旧结果被丢弃
    player.set_source(2, "https://cdn.example.com/new.flac", False)
    assert fake.source == "https://cdn.example.com/new.flac"


def test_resolve_failure_stops_playback() -> None:
    player, _ = media_player()
    errors: list[str] = []
    player.errorOccurred.connect(errors.append)
    playing: list[bool] = []
    player.playingChanged.connect(playing.append)

    player.set_queue([make_track(remote=True)], autoplay=True)
    player.resolve_failed(1, "该歌曲需要会员")

    assert player.is_playing is False
    assert errors == ["该歌曲需要会员"]
    assert playing[-1] is False


def test_trial_flag_emits_once() -> None:
    player, _ = media_player()
    seen: list[bool] = []
    player.trialModeChanged.connect(seen.append)

    player.set_queue([make_track(remote=True)], autoplay=True)
    player.set_source(1, "https://cdn.example.com/trial.mp3", True)
    player.set_source(1, "https://cdn.example.com/trial.mp3", True)

    assert seen == [True]
    assert player.is_trial is True


def test_single_mode_restarts_instead_of_next() -> None:
    player = clock_player()
    player.set_queue([make_track(1, duration=1), make_track(2)], autoplay=False)
    player.cycle_mode()
    player.cycle_mode()
    player.cycle_mode()          # 回到 loop
    player.cycle_mode()          # single
    assert player.mode == MODE_SINGLE

    player.play()
    player.seek(950)
    player._tick()               # 越过结尾 → 单曲循环回到 0

    assert player.current.id == 1
    assert player.position == 0
