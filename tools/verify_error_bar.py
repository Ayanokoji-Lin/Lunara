"""错误提示条验收：制造一次失败，确认只出现顶部细条、不弹窗、不白屏。

    .venv/Scripts/python.exe tools/verify_error_bar.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.api.errors import ApiError, ErrorCode  # noqa: E402
from lunara.main_window import MainWindow  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)


def pump(app: QApplication, seconds: float) -> None:
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
    pump(app, 1.5)

    # 1) 首页失败 → 顶部细条 + 3 秒后自动重试一次
    async def boom():
        raise ApiError(ErrorCode.NETWORK, "模拟断网")

    win._fetch_home = boom            # type: ignore[assignment]
    win._load_home()
    pump(app, 1.0)

    visible = win.banner.isVisible()
    print(f"提示条可见：{visible} | 文案：{win.banner.text}")
    win.grab().save(os.path.join(OUT, "22_error_bar.png"))
    print("saved shots/22_error_bar.png")

    # 2) 一次播放只解析一次（回归：连接被重复挂过）
    win.banner.clear()
    win.open_playlist(3778678)
    pump(app, 2.5)
    tracks = win.playlist_page._tracks
    if tracks:
        seqs: list[int] = []
        win.player.urlRequested.connect(lambda seq, t: seqs.append(seq))
        win.player.play_track(tracks[0], tracks)
        pump(app, 2.5)
        print(f"一次播放的解析次数：{len(seqs)}（应为 1）")

    # 3) 演示歌单（101 起）不发请求、不出错误条
    win.banner.clear()
    win.open_playlist(101)
    pump(app, 0.8)
    page = win.playlist_page
    print(f"演示歌单：{page._playlist.title} | 曲目 {len(page._tracks)} | "
          f"提示条 {win.banner.isVisible()}")
    win.grab().save(os.path.join(OUT, "23_demo_playlist.png"))
    print("saved shots/23_demo_playlist.png")

    win.close()
    return 0 if visible else 1


if __name__ == "__main__":
    raise SystemExit(main())
