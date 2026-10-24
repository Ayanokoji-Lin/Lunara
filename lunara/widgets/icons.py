"""Lunara · 图标层（qtawesome 封装 + 无依赖降级）"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    import qtawesome as qta
except Exception:                                    # pragma: no cover
    qta = None


def _fallback_pixmap(color: str, size: int) -> QPixmap:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2.0)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    p.end()
    return pm


def pixmap(name: str, color: str = "#F8FAFC", size: int = 16) -> QPixmap:
    """返回可直接 drawPixmap 的图标（2x 渲染，HiDPI 清晰）。"""
    if qta is not None:
        try:
            pm = qta.icon(name, color=color).pixmap(QSize(size * 2, size * 2))
            pm.setDevicePixelRatio(2.0)
            return pm
        except Exception:
            pass
    return _fallback_pixmap(color, size)


def icon(name: str, color: str = "#F8FAFC") -> QIcon:
    if qta is not None:
        try:
            return qta.icon(name, color=color)
        except Exception:
            pass
    return QIcon(_fallback_pixmap(color, 16))


def has_icons() -> bool:
    return qta is not None
