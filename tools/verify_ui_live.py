"""UI 接真数据后的端到端自检（离屏渲染 + 真实上游）。

    .venv/Scripts/python.exe tools/verify_ui_live.py

做三件事：
1. 等首页两屏数据回来，打印前 5 张歌单与前 3 首新歌；
2. 打开一个真实歌单，打印标题与曲目数；
3. 把两屏截图存到 shots/12_home_live.png、13_playlist_live.png。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.data import LYRICS, PLAYLISTS  # noqa: E402
from lunara.services.covers import covers  # noqa: E402
from lunara.main_window import MainWindow  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)

REAL_PLAYLIST = 3778678  # 热歌榜（实测有 200 首）


def spin(app: QApplication, predicate, timeout: float = 15.0, label: str = "") -> bool:
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


def first_card_height(page) -> int:
    """取第一张卡片的实际高度，用来等布局真正算完（不然截图是扁的）。"""
    layout = page._pl_layout
    if not layout.count():
        return 0
    wrap = layout.itemAt(0).widget()
    if wrap is None or wrap.layout() is None or not wrap.layout().count():
        return 0
    card = wrap.layout().itemAt(0).widget()
    return card.height() if card is not None else 0


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

    mock_titles = {pl.title for pl in PLAYLISTS}
    ok = spin(
        app,
        lambda: bool(win.home._playlists)
        and win.home._playlists[0].title not in mock_titles
        and first_card_height(win.home) > 100,
        label="首页真实歌单",
    )
    spin(app, lambda: len(win.home._new_songs) == 5, timeout=3, label="新歌速递")
    # 等真实封面下载+解码完成（拿不到就保持月牙空态，不算失败）
    spin(app, lambda: covers().cached(win.home._playlists[0].id) is not None,
         timeout=10, label="首页封面")
    settle(app, 0.6)  # 等父容器把高度传播完，否则截图会被裁成一条

    host = win.home._pl_host
    print(f"\n[布局] host={host.width()}x{host.height()} 首卡高={first_card_height(win.home)}")

    print(f"\n首页推荐歌单（{len(win.home._playlists)} 张）")
    for pl in win.home._playlists[:5]:
        print(f"  {pl.id:>12}  {pl.plays_text:>6}  {pl.title} — {pl.author}")
    print(f"\n新歌速递（{len(win.home._new_songs)} 首）")
    for track in win.home._new_songs[:3]:
        print(f"  {track.id:>12}  {track.duration_text}  {track.title} — {track.artist} / {track.album}")

    win.grab().save(os.path.join(OUT, "12_home_live.png"))
    print("\nsaved shots/12_home_live.png")

    win.open_playlist(REAL_PLAYLIST)
    spin(
        app,
        lambda: win.playlist_page._playlist.id == REAL_PLAYLIST
        and bool(win.playlist_page._tracks),
        label="歌单详情",
    )
    settle(app, 0.5)
    playlist = win.playlist_page._playlist
    print(f"\n歌单：{playlist.title}（{playlist.author}）曲目 {len(playlist.tracks)} 首")
    for track in playlist.tracks[:3]:
        print(f"  {track.duration_text}  {track.title} — {track.artist}")

    win.grab().save(os.path.join(OUT, "13_playlist_live.png"))
    print("saved shots/13_playlist_live.png")

    # ---------------- 搜索四类 ----------------
    win._on_search("周杰伦")
    spin(app, lambda: bool(win.search_page._tracks), label="搜索·单曲")
    settle(app, 0.4)
    print(f"\n搜索「周杰伦」单曲 {len(win.search_page._tracks)} 首")
    for track in win.search_page._tracks[:3]:
        print(f"  {track.duration_text}  {track.title} — {track.artist} / {track.album}")
    win.grab().save(os.path.join(OUT, "14_search_songs.png"))
    print("saved shots/14_search_songs.png")

    win.search_page.set_tab(1)
    spin(app, lambda: bool(win.search_page._artists), label="搜索·歌手")
    settle(app, 0.4)
    print(f"歌手 {len(win.search_page._artists)} 位："
          + "、".join(card.title for card in win.search_page._artists[:5]))
    win.grab().save(os.path.join(OUT, "15_search_artists.png"))
    print("saved shots/15_search_artists.png")

    win.search_page.set_tab(2)
    spin(app, lambda: bool(win.search_page._albums), label="搜索·专辑")
    settle(app, 0.3)
    print(f"专辑 {len(win.search_page._albums)} 张："
          + "、".join(f"{c.title}({c.subtitle})" for c in win.search_page._albums[:3]))

    win.search_page.set_tab(3)
    spin(app, lambda: bool(win.search_page._lists), label="搜索·歌单")
    settle(app, 0.3)
    print(f"歌单 {len(win.search_page._lists)} 张："
          + "、".join(f"{p.title}·{p.plays_text}" for p in win.search_page._lists[:3]))

    # ---------------- 歌词 ----------------
    tracks = win.playlist_page._tracks
    win.player.play_track(tracks[0], tracks)
    win.open_now_playing()
    spin(
        app,
        lambda: bool(win.now_playing._lyrics) and win.now_playing._lyrics != LYRICS,
        label="歌词",
    )
    settle(app, 0.6)
    lines = win.now_playing._lyrics
    print(f"歌词：{tracks[0].title} 共 {len(lines)} 行")
    for ms, text in lines[:3]:
        print(f"  [{ms // 1000:>3}s] {text}")
    win.grab().save(os.path.join(OUT, "16_now_playing_live.png"))
    print("saved shots/16_now_playing_live.png")

    # ---------------- 账号面板 ----------------
    win.navigate("settings")
    win.settings_page.switch(3)  # 账号
    settle(app, 0.5)
    print(f"\n账号面板：{win.settings_page.lbl_account.text()}"
          f" | 登录按钮可见={win.settings_page.btn_login.isVisible()}")
    win.grab().save(os.path.join(OUT, "17_settings_account.png"))
    print("saved shots/17_settings_account.png")

    win.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
