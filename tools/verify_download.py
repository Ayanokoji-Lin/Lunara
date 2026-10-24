"""真实下载端到端验收：加两首进队列 → 等落盘 → 校验文件头 → 截图。

会真的往下载目录写文件（默认 D:\\Music\\Lunara），跑之前想清楚。

    .venv/Scripts/python.exe tools/verify_download.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from lunara.main_window import MainWindow  # noqa: E402
from lunara.theme import qss  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
os.makedirs(OUT, exist_ok=True)

PLAYLIST_ID = 3778678        # 热歌榜
TAKE = 2                     # 只下两首，够验证就行


def spin(app: QApplication, predicate, timeout: float = 180.0, label: str = "") -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    print(f"!! 等待超时：{label}")
    return False


def magic(path: Path) -> str:
    try:
        head = path.read_bytes()[:4]
    except OSError:
        return "?"
    if head[:4] == b"fLaC":
        return "FLAC"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "MP3"
    if head[4:8] == b"ftyp":
        return "M4A"
    return head.hex()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(qss())
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
    font.setPixelSize(12)
    app.setFont(font)

    win = MainWindow()
    # 想验证到临时目录就设 LUNARA_VERIFY_DIR，别动真实音乐目录
    if os.environ.get("LUNARA_VERIFY_DIR"):
        target = Path(os.environ["LUNARA_VERIFY_DIR"])
        target.mkdir(parents=True, exist_ok=True)
        win._downloads._dir_of = lambda: target
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1280, 820)
    win.show()

    win.open_playlist(PLAYLIST_ID)
    spin(app, lambda: win.playlist_page._playlist.id == PLAYLIST_ID
         and bool(win.playlist_page._tracks), label="歌单曲目")

    tracks = win.playlist_page._tracks[:TAKE]
    print(f"下载目录：{win._settings.download_dir}")
    print(f"加入 {len(tracks)} 首：" + "、".join(t.title for t in tracks))
    win._enqueue_downloads(tracks)

    def finished() -> bool:
        tasks = win.download_page._tasks
        return bool(tasks) and all(t.state in ("done", "failed") for t in tasks)

    ok = spin(app, finished, timeout=180, label="下载完成")
    time.sleep(0.3)
    app.processEvents()

    for task in win.download_page._tasks:
        path = Path(task.file_path)
        exists = path.exists()
        size = path.stat().st_size / 1_000_000 if exists else 0
        print(f"  [{task.state}] {task.track.title} · {size:.1f} MB · "
              f"{magic(path) if exists else '-'} · {path.name}")
        if task.error:
            print(f"        错误：{task.error}")

    win.grab().save(os.path.join(OUT, "20_download_live.png"))
    print("saved shots/20_download_live.png")

    win.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
