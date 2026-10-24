"""Lunara · 播放内核

两种引擎，对外契约完全一致（6 个信号 + 同一套方法），页面不需要知道用的是哪个：

- ``media``：``QMediaPlayer`` + ``QAudioOutput``，真实出声；
- ``clock``：虚拟时钟，用于演示曲目（``Track.remote=False``）、无音频设备、单元测试。

直链是异步解析的，但 ``play_track`` 是同步方法，所以这里不做网络：
``play()`` 只发 ``urlRequested(seq, track)``，由上层（``MainWindow``）解析完再回调
``set_source(seq, url, trial)``。``seq`` 单调递增，迟到的结果会被丢弃——快速切歌不串台。
"""
from __future__ import annotations

import random

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal

from ..data import Track

try:  # 没有 QtMultimedia 时整体降级为虚拟时钟
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

    MEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - 取决于环境
    QAudioOutput = None  # type: ignore[assignment]
    QMediaPlayer = None  # type: ignore[assignment]
    MEDIA_AVAILABLE = False

MODE_LOOP = "loop"      # 列表循环
MODE_SINGLE = "single"  # 单曲循环
MODE_RANDOM = "random"  # 随机播放

MODE_TEXT = {MODE_LOOP: "列表循环", MODE_SINGLE: "单曲循环", MODE_RANDOM: "随机播放"}
MODE_ICON = {MODE_LOOP: "fa5s.redo", MODE_SINGLE: "fa5s.redo-alt",
             MODE_RANDOM: "fa5s.random"}

ENGINE_MEDIA = "media"
ENGINE_CLOCK = "clock"


class Player(QObject):
    trackChanged = pyqtSignal(object)       # Track | None
    positionChanged = pyqtSignal(int, int)  # position_ms, duration_ms
    playingChanged = pyqtSignal(bool)
    modeChanged = pyqtSignal(str)
    volumeChanged = pyqtSignal(int)
    likeChanged = pyqtSignal(int, bool)     # track_id, liked
    errorOccurred = pyqtSignal(str)         # 给 UI 的短句
    trialModeChanged = pyqtSignal(bool)     # 当前是否在放试听片段
    urlRequested = pyqtSignal(int, object)  # seq, Track（上层去解析直链）

    def __init__(self, parent=None, *, engine: str = "auto"):
        super().__init__(parent)
        self.queue: list[Track] = []
        self.index = -1
        self.mode = MODE_LOOP
        self.volume = 72
        self._pos = 0
        self._playing = False
        self._liked: set[int] = set()

        # 真实时长（毫秒）：0 表示还没拿到，回落到 Track.duration_ms
        self._duration_ms = 0
        # 直链解析序号：只有最新一次的返回才算数
        self._seq = 0
        self._source_track_id: int | None = None
        self._pending_seek_ms: int | None = None
        self._trial = False

        self._media = None
        self._audio = None
        self._engine = ENGINE_CLOCK
        if engine in ("auto", ENGINE_MEDIA) and MEDIA_AVAILABLE:
            try:
                self._setup_media()
                self._engine = ENGINE_MEDIA
            except Exception:  # noqa: BLE001 - 建不起来就退时钟，不该影响启动
                self._media = None
                self._audio = None
                self._engine = ENGINE_CLOCK

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)

        # 淡入：切歌/开始播放时把音量从 0 拉到目标，300ms 分 6 步
        self._fade_enabled = True
        self._fade_step = 0
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(50)
        self._fade_timer.timeout.connect(self._on_fade_step)

    # ---------------- 引擎 ----------------
    def set_fade(self, enabled: bool) -> None:
        """淡入淡出开关（设置页控制）。"""
        self._fade_enabled = bool(enabled)
        if not enabled and self._audio is not None:
            self._audio.setVolume(self.volume / 100)

    def _fade_in(self) -> None:
        if not self._fade_enabled or self._audio is None:
            return
        self._fade_step = 0
        self._audio.setVolume(0.0)
        self._fade_timer.start()

    def _on_fade_step(self) -> None:
        if self._audio is None:
            self._fade_timer.stop()
            return
        self._fade_step += 1
        ratio = min(1.0, self._fade_step / 6)
        self._audio.setVolume(self.volume / 100 * ratio)
        if ratio >= 1.0:
            self._fade_timer.stop()

    def _setup_media(self) -> None:
        self._media = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._media.setAudioOutput(self._audio)
        self._audio.setVolume(self.volume / 100)

        self._media.positionChanged.connect(self._on_media_position)
        self._media.durationChanged.connect(self._on_media_duration)
        self._media.mediaStatusChanged.connect(self._on_media_status)
        self._media.errorOccurred.connect(self._on_media_error)

    @property
    def engine(self) -> str:
        return self._engine

    @property
    def has_audio(self) -> bool:
        return self._engine == ENGINE_MEDIA

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
            self.stop_source()
            return
        self.index = max(0, min(index, len(self.queue) - 1))
        self._pos = 0
        self._duration_ms = 0
        self.trackChanged.emit(self.current)
        if autoplay:
            self.play()
        else:
            self._load_current()

    def play_track(self, track: Track, queue: list[Track] | None = None) -> None:
        if queue is not None:
            self.queue = list(queue)
        idx = next((i for i, t in enumerate(self.queue) if t.id == track.id), -1)
        if idx < 0:
            self.queue.append(track)
            idx = len(self.queue) - 1
        self.index = idx
        self._pos = 0
        self._duration_ms = 0
        self.trackChanged.emit(self.current)
        self.play()

    # ---------------- 传输控制 ----------------
    def play(self) -> None:
        track = self.current
        if track is None:
            return

        if not self._playing:
            self._playing = True
            self.playingChanged.emit(True)

        if self._uses_media(track):
            if self._source_track_id != track.id:
                self._request_url(track)      # 等 set_source 回来再真正 play
            else:
                self._media.play()
            return

        # 虚拟时钟（演示曲目 / 无音频后端）
        self._timer.start()

    def pause(self) -> None:
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        if self._media is not None:
            self._media.pause()
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
        self._switch_to(idx)

    def prev_track(self) -> None:
        if not self.queue:
            return
        if self._pos > 4000:          # 超过 4 秒则回到本曲开头
            self.seek(0)
            return
        self._switch_to((self.index - 1) % len(self.queue))

    def _switch_to(self, index: int) -> None:
        self.index = index
        self._pos = 0
        self._duration_ms = 0
        self._pending_seek_ms = None
        self._trial = False
        self.trackChanged.emit(self.current)
        self.positionChanged.emit(0, self.duration_ms)
        self._load_current()
        if self._playing:
            self.play()

    def seek(self, ms: int) -> None:
        track = self.current
        if track is None:
            return
        total = self.duration_ms
        target = max(0, min(ms, total)) if total > 0 else max(0, ms)
        self._pos = target

        if self._uses_media(track) and self._source_track_id == track.id:
            self._media.setPosition(target)
        else:
            self._pending_seek_ms = target
        self.positionChanged.emit(target, total)

    def cycle_mode(self) -> None:
        order = [MODE_LOOP, MODE_SINGLE, MODE_RANDOM]
        self.mode = order[(order.index(self.mode) + 1) % len(order)]
        self.modeChanged.emit(self.mode)

    def set_volume(self, v: int) -> None:
        self.volume = max(0, min(100, v))
        if self._audio is not None:
            self._audio.setVolume(self.volume / 100)
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

    def set_liked(self, track_id: int, liked: bool) -> None:
        """直接设置状态（同步失败回滚用），会发 ``likeChanged`` 让界面刷新。"""
        if liked:
            self._liked.add(track_id)
        else:
            self._liked.discard(track_id)
        self.likeChanged.emit(track_id, liked)

    # ---------------- 直链注入 ----------------
    def _uses_media(self, track: Track | None) -> bool:
        return self._engine == ENGINE_MEDIA and bool(track and track.remote)

    def _request_url(self, track: Track) -> None:
        if track.path:
            # 本地文件：不走解析，直接喂给媒体后端
            self.play_file(track, track.path)
            return
        self._seq += 1
        self._source_track_id = None
        self.urlRequested.emit(self._seq, track)

    def set_resume_position(self, ms: int) -> None:
        """切歌后要恢复到的位置（记忆播放位置用）。"""
        if ms > 0:
            self._pending_seek_ms = ms

    def set_source(self, seq: int, url: str, trial: bool = False) -> None:
        """上层解析成功后调用；``seq`` 不是最新一次就丢弃。"""
        if seq != self._seq or self._media is None:
            return
        track = self.current
        if track is None:
            return

        self._source_track_id = track.id
        self._media.setSource(QUrl(url))
        if trial != self._trial:
            self._trial = trial
            self.trialModeChanged.emit(trial)

        if self._playing:
            self._fade_in()
            self._media.play()

    def resolve_failed(self, seq: int, message: str) -> None:
        if seq != self._seq:
            return
        self._playing = False
        self._timer.stop()
        self.playingChanged.emit(False)
        self.errorOccurred.emit(message or "无法播放这首歌")

    def stop_source(self) -> None:
        """清掉当前音源（切到演示曲目、退出时用）。"""
        self._source_track_id = None
        self._duration_ms = 0
        if self._media is not None:
            self._media.stop()
            self._media.setSource(QUrl())

    def play_file(self, track: Track, path: str) -> None:
        """直接播放本地文件（下载完成的任务用），不走直链解析。"""
        if self._engine != ENGINE_MEDIA:
            self.play_track(track)          # 没有媒体后端就退回时钟
            return

        idx = next((i for i, item in enumerate(self.queue) if item.id == track.id), -1)
        if idx < 0:
            self.queue.append(track)
            idx = len(self.queue) - 1
        self.index = idx
        self._pos = 0
        self._duration_ms = 0
        self._source_track_id = track.id
        self._trial = False
        self.trackChanged.emit(self.current)

        self._media.setSource(QUrl.fromLocalFile(path))
        self._playing = True
        self.playingChanged.emit(True)
        self._media.play()

    def _load_current(self) -> None:
        """切歌后清掉旧音源，不请求直链（请求统一由 play() 触发，避免重复解析）。"""
        track = self.current
        if self._media is not None:
            self._media.stop()
        self._source_track_id = None
        self._duration_ms = 0
        if track is None:
            return
        if not self._uses_media(track):
            self.stop_source()
            self._timer.stop()

    # ---------------- 媒体事件 ----------------
    def _on_media_position(self, pos: int) -> None:
        self._pos = pos
        self.positionChanged.emit(pos, self.duration_ms)

    def _on_media_duration(self, duration: int) -> None:
        if duration > 0:
            self._duration_ms = duration
            self.positionChanged.emit(self._pos, self.duration_ms)

    def _on_media_status(self, status) -> None:
        if self._media is None:
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if self._pending_seek_ms is not None:
                self._media.setPosition(self._pending_seek_ms)
                self._pending_seek_ms = None
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.mode == MODE_SINGLE:
                self._media.setPosition(0)
                self._media.play()
            else:
                self.next_track()

    def _on_media_error(self, error, message: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        self._playing = False
        self.playingChanged.emit(False)
        self.errorOccurred.emit(f"播放失败：{message or error.name}")

    # ---------------- 虚拟时钟 ----------------
    def _tick(self) -> None:
        track = self.current
        if track is None or not self._playing:
            return
        total = self.duration_ms
        if total <= 0:
            return
        self._pos += self._timer.interval()
        if self._pos >= total:
            if self.mode == MODE_SINGLE:
                self._pos = 0
            else:
                self.next_track()
                return
        self.positionChanged.emit(self._pos, total)

    # ---------------- 只读属性 ----------------
    @property
    def duration_ms(self) -> int:
        if self._duration_ms > 0:
            return self._duration_ms
        track = self.current
        return track.duration_ms if track else 0

    @property
    def position(self) -> int:
        return self._pos

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def is_trial(self) -> bool:
        return self._trial

    def shutdown(self) -> None:
        self._timer.stop()
        self._fade_timer.stop()
        self._playing = False
        if self._media is not None:
            self._media.stop()
            self._media.setSource(QUrl())
