"""统一样式的提示框。

Qt 自带的 ``QMessageBox`` 在深色主题下会露出一块系统灰，和整体风格完全不搭。
这里用一个自绘 QDialog 顶掉它，颜色全部走 QSS 变量，切换主题自动跟随。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: 不同级别对应的强调色（和信息条一致）
LEVEL_COLOR = {
    "info": "#8B5CF6",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
}


class MessageDialog(QDialog):
    """统一提示框：标题 + 正文 + 可选勾选框 + 按钮。"""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        text: str,
        *,
        level: str = "info",
        ok_text: str = "知道了",
        cancel_text: str | None = None,
        checkbox: str | None = None,
        checkbox_checked: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LunaraDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumWidth(380)
        self.setMaximumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {LEVEL_COLOR.get(level, LEVEL_COLOR['info'])};"
                          " font-size: 12px;")
        head.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        head.addWidget(title_label, 1)
        root.addLayout(head)

        body = QLabel(text)
        body.setObjectName("DialogBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(body)

        self.checkbox: QCheckBox | None = None
        if checkbox:
            self.checkbox = QCheckBox(checkbox)
            self.checkbox.setChecked(checkbox_checked)
            root.addWidget(self.checkbox)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        if cancel_text:
            cancel = QPushButton(cancel_text)
            cancel.setObjectName("GhostPill")
            cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)
        ok = QPushButton(ok_text)
        ok.setObjectName("PrimaryPill")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        root.addLayout(buttons)

    def is_checked(self) -> bool:
        return bool(self.checkbox and self.checkbox.isChecked())


def alert(parent, title: str, text: str, *, level: str = "info",
          ok_text: str = "知道了") -> None:
    MessageDialog(parent, title, text, level=level, ok_text=ok_text).exec()


def confirm(parent, title: str, text: str, *, level: str = "warning",
            ok_text: str = "确定", cancel_text: str = "取消",
            checkbox: str | None = None, checkbox_checked: bool = True) -> tuple[bool, bool]:
    """返回 (是否确认, 勾选框是否选中)。没有勾选框时第二项恒为 False。"""
    dialog = MessageDialog(parent, title, text, level=level, ok_text=ok_text,
                           cancel_text=cancel_text, checkbox=checkbox,
                           checkbox_checked=checkbox_checked)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return accepted, dialog.is_checked()
