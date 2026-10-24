"""离屏渲染各页面截图，用于视觉走查（开发辅助脚本，不参与打包）。

注意：必须使用真实的 windows 平台插件（不能用 offscreen），
否则中文的字体回退会失效，截图里全是方框。
WA_DontShowOnScreen 让窗口完成布局但不真正显示在桌面上。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.data import TRACKS  # noqa: E402
from lunara.main_window import MainWindow  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)


def settle(ms: int = 450) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(qss())
    f = QFont()
    f.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei",
                   "Segoe UI", "SF Pro Display"])
    f.setPixelSize(12)
    app.setFont(f)

    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1280, 820)
    win.show()
    settle(800)

    def shot(name: str) -> None:
        settle(420)
        path = os.path.join(OUT, name + ".png")
        win.grab().save(path)
        print("saved", path)

    shot("01_home")

    win.open_playlist(101)
    shot("02_playlist")

    win.player.play_track(TRACKS[0], TRACKS)
    win.player.seek(28000)
    settle(300)
    win.open_now_playing()
    shot("03_now_playing_vinyl")

    win.now_playing.set_mode(1)
    shot("04_now_playing_lyric")

    win.now_playing.set_mode(2)
    shot("05_now_playing_cover")

    win.navigate("settings")
    shot("06_settings")

    win._on_search("月")
    shot("07_search")

    win.navigate("local")
    settle(900)
    shot("09_download")

    win.download_page.set_filter(2)
    shot("10_download_done")

    win.download_page.set_filter(3)
    shot("11_download_failed")

    win.navigate("home")
    win.resize(1056, 752)
    shot("08_home_min")


if __name__ == "__main__":
    main()
