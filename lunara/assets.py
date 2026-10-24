"""Lunara · 图像资源层

项目不依赖任何外部图片素材：封面全部由 QPainter 程序化生成
（渐变 + 星尘 + 月牙 + 暗角），并用 QPixmapCache 做多级缓存，
保证列表滚动时不会反复解码/绘制。
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
)

MASTER = 640
_HUE_POOL = (258, 268, 280, 244, 214, 196, 292, 322)

_master_cache: dict[tuple[int, int | None], QPixmap] = {}
_scaled_cache: dict[tuple, QPixmap] = {}


def hsl(h: int, s: int, l: int, a: int = 255) -> QColor:
    return QColor.fromHsl(int(h) % 360, max(0, min(255, int(s))),
                          max(0, min(255, int(l))), max(0, min(255, int(a))))


# --------------------------------------------------------------------------
# 封面生成
# --------------------------------------------------------------------------
def cover_master(seed: int, hue: int | None = None) -> QPixmap:
    """生成 640×640 的封面母版（带缓存）。"""
    key = (seed, hue)
    cached = _master_cache.get(key)
    if cached is not None:
        return cached

    rnd = random.Random(seed * 7919 + 17)
    h = hue if hue is not None else _HUE_POOL[seed % len(_HUE_POOL)]
    s = MASTER

    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # 1) 底色：深空渐变
    g = QLinearGradient(0, 0, s * 0.75, s)
    g.setColorAt(0.0, hsl(h, 118, 40))
    g.setColorAt(0.45, hsl((h + 22) % 360, 110, 22))
    g.setColorAt(1.0, hsl((h + 44) % 360, 120, 9))
    p.fillRect(0, 0, s, s, g)

    # 2) 主光晕（模拟星云）
    cx, cy = s * rnd.uniform(0.30, 0.72), s * rnd.uniform(0.18, 0.52)
    rg = QRadialGradient(QPointF(cx, cy), s * 0.78)
    rg.setColorAt(0.0, hsl(h + 8, 170, 66, 120))
    rg.setColorAt(0.35, hsl(h + 8, 170, 58, 46))
    rg.setColorAt(1.0, hsl(h, 160, 40, 0))
    p.setBrush(rg)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), s * 0.78, s * 0.78)

    # 3) 副光斑
    rg2 = QRadialGradient(QPointF(s * rnd.uniform(0.1, 0.9), s * 0.88), s * 0.5)
    rg2.setColorAt(0.0, hsl((h - 46) % 360, 200, 70, 58))
    rg2.setColorAt(1.0, hsl((h - 46) % 360, 200, 60, 0))
    p.setBrush(rg2)
    p.drawEllipse(QPointF(s * 0.5, s * 0.88), s * 0.5, s * 0.5)

    # 4) 星轨弧线
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(4):
        r = s * (0.30 + i * 0.135)
        pen = QPen(QColor(255, 255, 255, 12 + i * 3))
        pen.setWidthF(1.4)
        p.setPen(pen)
        start = rnd.randint(-40, 40)
        p.drawArc(QRectF(s / 2 - r, s / 2 - r, r * 2, r * 2), start * 16, 200 * 16)

    # 5) 星尘
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(78):
        x, y = rnd.uniform(0, s), rnd.uniform(0, s)
        rr = rnd.uniform(0.6, 2.1)
        a = rnd.randint(28, 168)
        p.setBrush(QColor(255, 255, 255, a))
        p.drawEllipse(QPointF(x, y), rr, rr)
    # 少量亮星带光晕
    for _ in range(5):
        x, y = rnd.uniform(s * 0.05, s * 0.95), rnd.uniform(s * 0.05, s * 0.95)
        rr = rnd.uniform(1.8, 2.6)
        halo = QRadialGradient(QPointF(x, y), rr * 7)
        halo.setColorAt(0.0, QColor(255, 255, 255, 120))
        halo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(halo)
        p.drawEllipse(QPointF(x, y), rr * 7, rr * 7)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(QPointF(x, y), rr, rr)

    # 6) 主体元素：月牙 / 星团 / 行星弧，让每张封面有辨识度
    kind = rnd.random()
    if kind < 0.52:
        _crescent(p, s * rnd.uniform(0.32, 0.68), s * rnd.uniform(0.26, 0.48),
                  s * rnd.uniform(0.10, 0.17), QColor(248, 250, 252, 236))
    elif kind < 0.78:
        _star_cluster(p, s, rnd)
    else:
        _planet_arc(p, s, rnd, h)

    # 7) 暗角，让封面在任何背景上都有“沉下去”的体积感
    vig = QRadialGradient(QPointF(s / 2, s / 2), s * 0.72)
    vig.setColorAt(0.0, QColor(0, 0, 0, 0))
    vig.setColorAt(0.62, QColor(0, 0, 0, 18))
    vig.setColorAt(1.0, QColor(0, 0, 0, 118))
    p.setBrush(vig)
    p.drawRect(0, 0, s, s)

    p.end()
    _master_cache[key] = pm
    return pm


def _crescent(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
    """用两个椭圆的布尔差画一弯新月。"""
    glow = QRadialGradient(QPointF(cx, cy), r * 3.2)
    glow.setColorAt(0.0, QColor(226, 232, 240, 70))
    glow.setColorAt(1.0, QColor(226, 232, 240, 0))
    p.setBrush(glow)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r * 3.2, r * 3.2)

    outer = QPainterPath()
    outer.addEllipse(QPointF(cx, cy), r, r)
    inner = QPainterPath()
    inner.addEllipse(QPointF(cx + r * 0.46, cy - r * 0.20), r * 0.94, r * 0.94)
    p.setBrush(color)
    p.drawPath(outer.subtracted(inner))


def _star_cluster(p: QPainter, s: int, rnd: random.Random) -> None:
    """星团：一小片密集的亮星，作为没有月亮的封面主体。"""
    cx = s * rnd.uniform(0.28, 0.72)
    cy = s * rnd.uniform(0.26, 0.58)
    spread = s * rnd.uniform(0.09, 0.17)

    pen = QPen(QColor(255, 255, 255, 26))
    pen.setWidthF(1.2)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(cx - spread * 2.1, cy + spread * 0.7),
               QPointF(cx + spread * 2.1, cy - spread * 0.5))

    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(16):
        x = cx + rnd.gauss(0, spread)
        y = cy + rnd.gauss(0, spread)
        r = rnd.uniform(0.8, 2.3)
        halo = QRadialGradient(QPointF(x, y), r * 8)
        halo.setColorAt(0.0, QColor(226, 232, 240, 95))
        halo.setColorAt(1.0, QColor(226, 232, 240, 0))
        p.setBrush(halo)
        p.drawEllipse(QPointF(x, y), r * 8, r * 8)
        p.setBrush(QColor(255, 255, 255, rnd.randint(170, 248)))
        p.drawEllipse(QPointF(x, y), r, r)


def _planet_arc(p: QPainter, s: int, rnd: random.Random, h: int) -> None:
    """行星弧：一颗巨大行星从画面底部升起，只露出边缘。"""
    r = s * rnd.uniform(0.60, 0.95)
    cx = s * rnd.uniform(0.15, 0.85)
    cy = s * (1.02 + rnd.uniform(0.0, 0.22))

    body = QRadialGradient(QPointF(cx - r * 0.30, cy - r * 0.92), r * 1.55)
    body.setColorAt(0.0, hsl(h + 34, 60, 48, 235))
    body.setColorAt(0.45, hsl(h + 12, 70, 24, 245))
    body.setColorAt(1.0, hsl(h, 80, 11, 250))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(body)
    p.drawEllipse(QPointF(cx, cy), r, r)

    rim = QPen(QColor(226, 232, 240, 110))
    rim.setWidthF(2.0)
    p.setPen(rim)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r - 1, r - 1)


# --------------------------------------------------------------------------
# 缩放 / 裁切 / 模糊
# --------------------------------------------------------------------------
def cover_pixmap(seed: int, size: int, hue: int | None = None,
                 radius: float = 0) -> QPixmap:
    key = (seed, size, hue, round(radius, 2))
    cached = _scaled_cache.get(key)
    if cached is not None:
        return cached
    pm = cover_master(seed, hue).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if radius > 0:
        pm = rounded(pm, radius)
    _scaled_cache[key] = pm
    return pm


def rounded(pm: QPixmap, radius: float) -> QPixmap:
    """圆角遮罩（含 devicePixelRatio 兼容）。"""
    if pm.isNull():
        return pm
    dpr = pm.devicePixelRatio() or 1.0
    out = QPixmap(pm.size())
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    r = radius * dpr
    path.addRoundedRect(QRectF(0, 0, pm.width(), pm.height()), r, r)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def circular(pm: QPixmap, size: int) -> QPixmap:
    src = pm.scaled(size * 2, size * 2,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
    src = src.copy((src.width() - size * 2) // 2, (src.height() - size * 2) // 2,
                   size * 2, size * 2)
    src.setDevicePixelRatio(2.0)
    return rounded(src, size / 2.0 * 2)


def crop_fill(pm: QPixmap, w: int, h: int) -> QPixmap:
    scaled = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                       Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    return scaled.copy(x, y, w, h)


def blur_pixmap(pm: QPixmap, radius: float = 48,
                downscale: float = 0.32) -> QPixmap:
    """用 QGraphicsBlurEffect + QGraphicsScene 离线渲染高斯模糊。

    先缩小再模糊，最后由调用方放大使用：既保留柔和的弥散感，
    又把 CPU 开销压到 1/10（模糊半径按比例缩小）。
    """
    if pm.isNull():
        return pm
    small = pm.scaled(max(1, int(pm.width() * downscale)),
                      max(1, int(pm.height() * downscale)),
                      Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)

    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, small.width(), small.height()))
    item = QGraphicsPixmapItem(small)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(max(1.0, radius * downscale))
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    out = QImage(small.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scene.render(painter, QRectF(out.rect()), scene.sceneRect())
    painter.end()
    scene.clear()
    return QPixmap.fromImage(out)


def blurred_background(seed: int, w: int, h: int, hue: int | None = None,
                       radius: float = 56) -> QPixmap:
    """播放页背景：模糊封面放大到画布尺寸（略过扫，避免边缘透出）。"""
    base = cover_master(seed, hue)
    blur = blur_pixmap(base, radius=radius, downscale=0.30)
    target_w, target_h = int(w * 1.18), int(h * 1.18)
    out = blur.scaled(target_w, target_h,
                      Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                      Qt.TransformationMode.SmoothTransformation)
    return out
