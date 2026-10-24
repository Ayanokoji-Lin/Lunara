"""真实播放验收：解析直链 → 出声 → 进度前进 → seek → 截图。

    .venv/Scripts/python.exe tools/verify_playback.py

只判断「播放器在动」与「时长/进度合理」，不校验声音大小（那得靠耳朵）。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.main_window import MainWindow  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)

PLAYLIST_ID = 3778678        # 热歌榜


def spin(app: QApplication, predicate, timeout: float = 60.0, label: str = "") -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    print(f"!! 等待超时：{label}")
    return False


def settle(app: QApplication, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(qss())
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
    font.setPixelSize(12)
    app.setFont(font)

    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1280, 820)
    win.show()

    player = win.player
    print(f"引擎：{player.engine} | 有音频输出：{player.has_audio}")
    if not player.has_audio:
        print("!! 没有 QMediaPlayer，本轮只能验证虚拟时钟")
        win.close()
        return 1

    win.open_playlist(PLAYLIST_ID)
    spin(app, lambda: win.playlist_page._playlist.id == PLAYLIST_ID
         and bool(win.playlist_page._tracks), label="歌单曲目")

    track = win.playlist_page._tracks[0]
    print(f"播放：{track.title} — {track.artist}（id={track.id}）")
    player.play_track(track, win.playlist_page._tracks)

    started = spin(app, lambda: player.position > 1200, timeout=40, label="开始出声")
    if not started:
        print(f"!! 位置没有前进：playing={player.is_playing} pos={player.position}")

    print(f"真实时长：{player.duration_ms / 1000:.1f}s "
          f"（接口给的是 {track.duration}s）| 试听：{player.is_trial}")
    print(f"3 秒后位置：{player.position} ms")

    # seek 到 50%
    target = player.duration_ms // 2
    player.seek(target)
    settle(app, 1.0)
    print(f"seek 到 {target} ms → 实际 {player.position} ms")

    win.open_now_playing()
    settle(app, 1.2)
    win.grab().save(os.path.join(OUT, "21_playing_live.png"))
    print("saved shots/21_playing_live.png")

    player.pause()
    settle(app, 0.3)
    print(f"暂停后 playing={player.is_playing} pos={player.position}")

    win.close()
    return 0 if started else 1


if __name__ == "__main__":
    raise SystemExit(main())
