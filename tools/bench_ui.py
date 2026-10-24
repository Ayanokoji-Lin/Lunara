"""UI 性能基准：封面解码、黑胶/星空重绘、页面切换。

用法：``.venv/Scripts/python.exe tools/bench_ui.py``
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from lunara.services.covers import CACHE_DIR, _decode  # noqa: E402
from lunara.theme import qss  # noqa: E402
from lunara.widgets.starfield import StarField  # noqa: E402
from lunara.widgets.vinyl import VinylDisc  # noqa: E402

app.setStyleSheet(qss())


def bench(label: str, fn, rounds: int = 30) -> None:
    samples = []
    for _ in range(rounds):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    print(f"{label:<28} 中位 {statistics.median(samples):6.2f} ms | "
          f"最快 {min(samples):6.2f} | 最慢 {max(samples):6.2f}")


def cover_bench() -> None:
    files = sorted(CACHE_DIR.glob("*.img"))[:8]
    if not files:
        print("封面缓存为空，跳过解码基准")
        return
    blobs = [path.read_bytes() for path in files]

    def old_way() -> None:
        for data in blobs:
            pm = QPixmap()
            pm.loadFromData(data)

    def new_way() -> None:
        for data in blobs:
            _decode(data)

    bench("封面解码（原图）", old_way, 10)
    bench("封面解码（512 上限）", new_way, 10)


def paint_bench() -> None:
    disc = VinylDisc(320)
    disc.resize(320, 320)
    disc.set_track(1, 200, "")
    disc.grab()

    disc_target = QPixmap(320, 320)

    def paint_disc() -> None:
        disc_target.fill(Qt.GlobalColor.transparent)
        disc.render(disc_target)

    field = StarField()
    field.resize(800, 520)
    field.grab()

    target = QPixmap(800, 520)

    def paint_stars() -> None:
        target.fill(Qt.GlobalColor.transparent)
        field.render(target)

    bench("黑胶重绘（缓存盘体）", paint_disc, 30)

    def paint_disc_old() -> None:
        disc._render_disc()          # 旧做法：每帧重画阴影+盘体+26 圈纹路

    bench("黑胶重绘（旧：每帧全画）", paint_disc_old, 30)
    bench("星空重绘（缓存柔光）", paint_stars, 30)

    from PyQt6.QtCore import QPointF, Qt as _Qt
    from PyQt6.QtGui import QColor, QPainter, QPixmap as _PM, QRadialGradient
    import math

    def stars_old() -> None:
        pm = _PM(800, 520)
        pm.fill(_Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        glow = QRadialGradient(QPointF(400, 260), 336)
        glow.setColorAt(0.0, QColor(139, 92, 246, 46))
        glow.setColorAt(0.55, QColor(139, 92, 246, 12))
        glow.setColorAt(1.0, QColor(139, 92, 246, 0))
        p.setPen(_Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawRect(pm.rect())
        for x, y, r, phase, speed in field._stars:
            a = 40 + 150 * (0.5 + 0.5 * math.sin(field._t * speed + phase))
            p.setBrush(QColor(226, 232, 240, int(a)))
            p.drawEllipse(QPointF(x * 800, y * 520), r, r)
        p.end()

    bench("星空重绘（旧：每帧重建渐变）", stars_old, 30)


def page_bench() -> None:
    from lunara.main_window import P_HOME, P_PLAYLIST, MainWindow

    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1280, 820)
    win.show()

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.005)

    pump(1.5)

    def switch() -> None:
        win._show(P_PLAYLIST)
        pump(0.18)
        win._show(P_HOME)
        pump(0.18)

    bench("两次页面切换（含 160ms 淡入）", switch, 8)
    win._close_to_tray = False
    win.close()


if __name__ == "__main__":
    cover_bench()
    paint_bench()
    page_bench()
