"""生成应用图标：`assets/icon.png`（1024）+ `assets/icon.ico`（多尺寸）。

    .venv/Scripts/python.exe tools/make_icon.py

画法与侧栏的 `LogoMark` 同源：深空底 + 弯月。区别是图标要能缩到 16px 还看得清，
所以加了圆角底板、月光渐变和两颗小星，并逐级降采样。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import (  # noqa: E402
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _sparkle(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
    """四角星：四条向内的弧线，比圆点更像「星」。"""
    path = QPainterPath(QPointF(cx, cy - r))
    path.quadTo(cx + r * 0.14, cy - r * 0.14, cx + r, cy)
    path.quadTo(cx + r * 0.14, cy + r * 0.14, cx, cy + r)
    path.quadTo(cx - r * 0.14, cy + r * 0.14, cx - r, cy)
    path.quadTo(cx - r * 0.14, cy - r * 0.14, cx, cy - r)
    p.fillPath(path, color)


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    s = float(size)
    radius = s * 0.225

    # 底板：深空渐变
    board = QPainterPath()
    board.addRoundedRect(QRectF(0, 0, s, s), radius, radius)
    bg = QLinearGradient(0, 0, s, s)
    bg.setColorAt(0.0, QColor("#2B1B5A"))
    bg.setColorAt(0.55, QColor("#1B1440"))
    bg.setColorAt(1.0, QColor("#0B1020"))
    p.fillPath(board, bg)

    # 左上角柔光，避免大面积死黑
    glow = QRadialGradient(QPointF(s * 0.30, s * 0.22), s * 0.62)
    glow.setColorAt(0.0, QColor(139, 92, 246, 110))
    glow.setColorAt(1.0, QColor(139, 92, 246, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(s * 0.30, s * 0.22), s * 0.62, s * 0.62)

    # 圆角描边：一圈很淡的月光
    rim = QPainterPath()
    rim.addRoundedRect(QRectF(1.0, 1.0, s - 2.0, s - 2.0), radius, radius)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QColor(196, 181, 253, 46))
    p.drawPath(rim)

    # 弯月：大圆减去偏移圆（略偏左，右侧留给星）
    d = s * 0.54                       # 月亮直径
    x = s * 0.19
    y = (s - d) / 2
    outer = QPainterPath()
    outer.addEllipse(QRectF(x, y, d, d))
    inner = QPainterPath()
    inner.addEllipse(QRectF(x + d * 0.40, y - d * 0.15, d, d))
    moon = outer.subtracted(inner)

    # 月亮外圈的柔光，避免纯色块显得平
    halo = QRadialGradient(QPointF(x + d * 0.42, y + d * 0.5), d * 0.78)
    halo.setColorAt(0.0, QColor(226, 232, 240, 70))
    halo.setColorAt(1.0, QColor(226, 232, 240, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(halo)
    p.drawEllipse(QPointF(x + d * 0.42, y + d * 0.5), d * 0.78, d * 0.78)

    moon_fill = QLinearGradient(x, y, x + d, y + d)
    moon_fill.setColorAt(0.0, QColor("#FFFFFF"))
    moon_fill.setColorAt(0.55, QColor("#EDE9FE"))
    moon_fill.setColorAt(1.0, QColor("#C4B5FD"))
    p.setPen(Qt.PenStyle.NoPen)
    p.fillPath(moon, moon_fill)

    # 两颗四角星（位置避开月亮）
    for cx, cy, r, alpha in (
        (s * 0.760, s * 0.255, s * 0.055, 240),
        (s * 0.715, s * 0.560, s * 0.028, 180),
    ):
        _sparkle(p, cx, cy, r, QColor(237, 233, 254, alpha))

    p.end()
    return image


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 - QImage 需要
    ASSETS.mkdir(parents=True, exist_ok=True)

    master = draw(SIZE)
    png = ASSETS / "icon.png"
    if not master.save(str(png), "PNG"):
        print("!! PNG 保存失败")
        return 1

    # ICO：多尺寸，16px 也不糊
    from PIL import Image

    ico = ASSETS / "icon.ico"
    Image.open(png).save(ico, sizes=[(n, n) for n in ICO_SIZES])

    print(f"生成完成：{png.name}（{SIZE}px）、{ico.name}（{len(ICO_SIZES)} 个尺寸）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
