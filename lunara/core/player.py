"""Lunara · 播放内核

当前用「虚拟时钟」驱动 UI（无音频解码依赖，方便先做界面）。
接入真实音频时，只需把 _tick 换成 QMediaPlayer.positionChanged，
并把 toggle/seek 转发到 QMediaPlayer，界面层不需要改动。
"""
from __future__ import annotations

import random

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..data import Track

MODE_LOOP = "loop"      # 列表循环
MODE_SINGLE = "single"  # 单曲循环
MODE_RANDOM = "random"  # 随机播放

MODE_TEXT = {MODE_LOOP: "列表循环", MODE_SINGLE: "单曲循环", MODE_RANDOM: "随机播放"}
MODE_ICON = {MODE_LOOP: "fa5s.redo", MODE_SINGLE: "fa5s.redo-alt",
             MODE_RANDOM: "fa5s.random"}


class Player(QObject):
    trackChanged = pyqtSignal(object)      # Track
    positionChanged = pyqtSignal(int, int)  # position_ms, duration_ms
    playingChanged = pyqtSignal(bool)
    modeChanged = pyqtSignal(str)
    volumeChanged = pyqtSignal(int)
    likeChanged = pyqtSignal(int, bool)     # track_id, liked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue: list[Track] = []
        self.index = -1
        self.mode = MODE_LOOP
        self.volume = 72
        self._pos = 0
        self._playing = False
        self._liked: set[int] = set()

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)

    # ---------------- 队列 ----------------
    @property
    def current(self) -> Track | None:
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def set_queue(self, tracks: list[Track], index: int = 0,
                  autoplay: bool = True) -> None:
        self.queue = list(tracks)
        if not self.queue:
            self.index = -1
            return
        self.index = max(0, min(index, len(self.queue) - 1))
        self._pos = 0
        self.trackChanged.emit(self.current)
        if autoplay:
            self.play()

    def play_track(self, track: Track, queue: list[Track] | None = None) -> None:
        if queue is not None:
            self.queue = list(queue)
        idx = next((i for i, t in enumerate(self.queue) if t.id == track.id), -1)
        if idx < 0:
            self.queue.append(track)
            idx = len(self.queue) - 1
        self.index = idx
        self._pos = 0
        self.trackChanged.emit(self.current)
        self.play()

    # ---------------- 传输控制 ----------------
    def play(self) -> None:
        if self.current is None:
            return
        if not self._playing:
            self._playing = True
            self._timer.start()
            self.playingChanged.emit(True)

    def pause(self) -> None:
        if self._playing:
            self._playing = False
            self._timer.stop()
            self.playingChanged.emit(False)

    def toggle(self) -> None:
        self.pause() if self._playing else self.play()

    def next_track(self) -> None:
        if not self.queue:
            return
        if self.mode == MODE_RANDOM and len(self.queue) > 1:
            idx = self.index
            while idx == self.index:
                idx = random.randrange(len(self.queue))
        else:
            idx = (self.index + 1) % len(self.queue)
        self.index = idx
        self._pos = 0
        self.trackChanged.emit(self.current)
        self.positionChanged.emit(0, self.current.duration_ms if self.current else 0)
        if self._playing:
            self._timer.start()

    def prev_track(self) -> None:
        if not self.queue:
            return
        if self._pos > 4000:          # 超过 4 秒则回到本曲开头
            self.seek(0)
            return
        self.index = (self.index - 1) % len(self.queue)
        self._pos = 0
        self.trackChanged.emit(self.current)
        self.positionChanged.emit(0, self.current.duration_ms if self.current else 0)

    def seek(self, ms: int) -> None:
        track = self.current
        if track is None:
            return
        self._pos = max(0, min(ms, track.duration_ms))
        self.positionChanged.emit(self._pos, track.duration_ms)

    def cycle_mode(self) -> None:
        order = [MODE_LOOP, MODE_SINGLE, MODE_RANDOM]
        self.mode = order[(order.index(self.mode) + 1) % len(order)]
        self.modeChanged.emit(self.mode)

    def set_volume(self, v: int) -> None:
        self.volume = max(0, min(100, v))
        self.volumeChanged.emit(self.volume)

    # ---------------- 喜欢 ----------------
    def is_liked(self, track_id: int) -> bool:
        return track_id in self._liked

    def toggle_like(self, track_id: int) -> bool:
        if track_id in self._liked:
            self._liked.discard(track_id)
            liked = False
        else:
            self._liked.add(track_id)
            liked = True
        self.likeChanged.emit(track_id, liked)
        return liked

    # ---------------- 时钟 ----------------
    def _tick(self) -> None:
        track = self.current
        if track is None or not self._playing:
            return
        self._pos += self._timer.interval()
        if self._pos >= track.duration_ms:
            if self.mode == MODE_SINGLE:
                self._pos = 0
            else:
                self.next_track()
                return
        self.positionChanged.emit(self._pos, track.duration_ms)

    @property
    def position(self) -> int:
        return self._pos

    @property
    def is_playing(self) -> bool:
        return self._playing
