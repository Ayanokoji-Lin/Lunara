"""登录态 UI 自检：侧栏「我的歌单」与「我喜欢的音乐」。

需要本机已登录（session.enc 存在），否则会直接退出。

    .venv/Scripts/python.exe tools/verify_account_ui.py
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
from lunara.services.account import AccountStore  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)


def spin(app: QApplication, predicate, timeout: float = 20.0, label: str = "") -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    print(f"!! 等待超时：{label}")
    return False


def settle(app: QApplication, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    if not AccountStore().logged_in:
        print("没有登录态：先在应用里登录一次")
        return 1

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

    ok = spin(app, lambda: win._liked_id is not None, label="我的歌单")
    settle(app, 0.8)

    keys = [k for k in win.sidebar._items if k.startswith("myplaylist:")]
    print(f"账号：{win.settings_page.lbl_account.text()}")
    print(f"侧栏歌单 {len(keys)} 个：")
    for key in keys[:8]:
        print(f"  {key}  {win.sidebar._items[key].text()}")
    print(f"我喜欢的音乐 id = {win._liked_id}")

    win.grab().save(os.path.join(OUT, "18_sidebar_mine.png"))
    print("saved shots/18_sidebar_mine.png")

    win.navigate("liked")
    spin(app, lambda: win.playlist_page._playlist.id == win._liked_id
         and bool(win.playlist_page._tracks), label="我喜欢的音乐")
    settle(app, 0.6)
    playlist = win.playlist_page._playlist
    print(f"\n我喜欢的音乐：{playlist.title} 共 {len(playlist.tracks)} 首（线上 {playlist.plays_text} 播放）")
    for track in playlist.tracks[:3]:
        print(f"  {track.duration_text}  {track.title} — {track.artist}")
    win.grab().save(os.path.join(OUT, "19_liked_playlist.png"))
    print("saved shots/19_liked_playlist.png")

    win.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
