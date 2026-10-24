"""歌手页 / 专辑页验收：搜索 → 点歌手 → 点专辑 → 截图。

    .venv/Scripts/python.exe tools/verify_artist_album.py
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


def spin(app: QApplication, predicate, timeout: float = 30.0, label: str = "") -> bool:
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
    settle(app, 0.8)

    win._on_search("周杰伦")
    spin(app, lambda: bool(win.search_page._tracks), label="单曲结果")
    # 歌手 / 专辑是切 Tab 时才补拉的
    win.search_page.set_tab(1)
    spin(app, lambda: bool(win.search_page._artists), label="歌手结果")
    win.search_page.set_tab(2)
    spin(app, lambda: bool(win.search_page._albums), label="专辑结果")
    settle(app, 0.5)

    artist = win.search_page._artists[0]
    print(f"歌手卡片：{artist.title}（id={artist.seed}）")
    win.open_artist(artist.seed)
    ok_artist = spin(app, lambda: win.playlist_page._playlist.id == artist.seed
                     and bool(win.playlist_page._tracks), label="歌手页")
    settle(app, 0.8)
    page = win.playlist_page
    print(f"歌手页：{page.lbl_title.text()} | {page.lbl_meta.text()} | "
          f"标签 {page.chip.text()} | {len(page._tracks)} 首")
    win.grab().save(os.path.join(OUT, "24_artist_page.png"))
    print("saved shots/24_artist_page.png")

    album = win.search_page._albums[0]
    print(f"专辑卡片：{album.title}（id={album.seed}）")
    win.open_album(album.seed)
    ok_album = spin(app, lambda: win.playlist_page._playlist.id == album.seed
                    and bool(win.playlist_page._tracks), label="专辑页")
    settle(app, 0.8)
    print(f"专辑页：{page.lbl_title.text()} | {page.lbl_meta.text()} | "
          f"标签 {page.chip.text()} | {len(page._tracks)} 首")
    for track in page._tracks[:3]:
        print(f"  {track.duration_text}  {track.title} — {track.artist}")
    win.grab().save(os.path.join(OUT, "25_album_page.png"))
    print("saved shots/25_album_page.png")

    win.close()
    return 0 if (ok_artist and ok_album) else 1


if __name__ == "__main__":
    raise SystemExit(main())
