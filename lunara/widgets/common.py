"""Lunara · 通用小部件与绘制辅助"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QTextLayout, QTextOption
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme import THEME
from .icons import icon

FONT_UI = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SF Pro Display"'


def font(size: int, weight: int = 400) -> QFont:
    f = QFont()
    f.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SF Pro Display"])
    f.setPixelSize(size)
    f.setWeight(QFont.Weight(weight))
    return f


def draw_wrapped(p: QPainter, rect: QRectF, text: str, f: QFont,
                 color: QColor | str, max_lines: int = 2,
                 leading: int = 2) -> None:
    """两行截断的多行文本绘制（QSS 无法做多行省略，这里手绘）。"""
    p.save()
    p.setFont(f)
    p.setPen(QColor(color))
    layout = QTextLayout(text, f)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(opt)
    layout.beginLayout()
    y = 0.0
    count = 0
    while count < max_lines:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(rect.width())
        line.setPosition(QPointF(0, y))
        y += line.height() + leading
        count += 1
    layout.endLayout()
    p.setClipRect(rect)
    layout.draw(p, QPointF(rect.left(), rect.top()))
    p.restore()


class IconButton(QPushButton):
    """统一图标按钮：hover 背景来自 QSS，图标颜色由代码控制。"""

    def __init__(self, icon_name: str, color: str | None = None, size: int = 16,
                 button: int = 32, tooltip: str = "", obj: str = "IconBtn",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName(obj)
        self._name = icon_name
        self._size = size
        self._color = color or THEME["text_sub"]
        self.setIcon(icon(icon_name, self._color))
        self.setIconSize(QSize(size, size))
        self.setFixedSize(button, button)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if tooltip:
            self.setToolTip(tooltip)

    def set_color(self, color: str) -> None:
        self._color = color
        self.setIcon(icon(self._name, color))

    def set_icon_name(self, name: str) -> None:
        self._name = name
        self.setIcon(icon(name, self._color))


class SectionHeader(QWidget):
    moreClicked = pyqtSignal()

    def __init__(self, title: str, hint: str = "", more: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.title = QLabel(title)
        self.title.setObjectName("SectionTitle")
        lay.addWidget(self.title)
        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("SectionHint")
            lay.addWidget(self.hint, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addStretch(1)
        if more:
            btn = QPushButton(more)
            btn.setObjectName("LinkBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self.moreClicked)
            lay.addWidget(btn)


class Divider(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class Chip(QLabel):
    """小标签（“每日推荐”“助眠”等）。"""

    def __init__(self, text: str, color: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(text, parent)
        c = color or THEME["primary"]
        self.setStyleSheet(
            f"QLabel {{ color: {c}; background: rgba(139, 92, 246, 0.14);"
            f" border: 1px solid rgba(139, 92, 246, 0.28); border-radius: 9px;"
            f" padding: 1px 8px; font-size: 10px; }}"
        )
        self.setFixedHeight(20)


def _popup_qss() -> str:
    from ..theme import THEME

    return f"""
    QListView {{
        background-color: {THEME['bg_elev']};
        border: 1px solid {THEME['border']};
        border-radius: 10px;
        padding: 6px;
        outline: 0;
        color: {THEME['text_main']};
    }}
    QListView::item {{
        min-height: 30px;
        padding-left: 10px;
        border: none;
        border-radius: 6px;
        color: {THEME['text_main']};
    }}
    QListView::item:hover {{
        background-color: {THEME['bg_hover']};
    }}
    QListView::item:selected {{
        background-color: {THEME['primary_soft']};
        color: {THEME['text_main']};
        border: none;
    }}
    """


def round_popup(combo) -> None:
    """把下拉弹层做成圆角卡片。

    QComboBox 的弹层是**独立顶层窗口**，``QComboBox QAbstractItemView`` 这类
    后代选择器对它不生效（父子关系已断开），所以只能直接给 view 套样式，
    再把窗口设成半透明，圆角才看得见。
    """
    from PyQt6.QtCore import Qt

    view = combo.view()
    window = view.window()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setStyleSheet("background: transparent; border: none;")
    view.setStyleSheet(_popup_qss())
    view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    view.setFrameShape(view.Shape.NoFrame)


def style_combo(combo) -> None:
    """让下拉弹层也走 QSS 的圆角。

    QComboBox 的弹出列表是一个**独立顶层窗口**，默认不透明、无边框，
    所以 QSS 里的 border-radius 看起来不起作用（截图里就是一块方角深色板）。
    把它设成半透明 + 无边框的 Popup，圆角才真正生效。
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QListView

    view = combo.view()
    if isinstance(view, QListView):
        view.setSpacing(2)
        view.setUniformItemSizes(True)
    window = view.window()
    window.setWindowFlags(Qt.WindowType.Popup
                          | Qt.WindowType.FramelessWindowHint
                          | Qt.WindowType.NoDropShadowWindowHint)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class RoundedCombo(QComboBox):
    """弹层自动圆角的 QComboBox。"""

    def showPopup(self) -> None:          # noqa: N802 - Qt 命名
        super().showPopup()
        round_popup(self)
