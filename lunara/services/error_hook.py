"""全局异常与 Qt 警告的兜底显示。

以前槽函数里抛异常，PyQt 只往控制台打一行，用户看到的却是「点了没反应」甚至进程消失。
这里统一收口：
- 未捕获异常 → 日志 + 弹窗（带「复制详情」入口）
- Qt 的 Warning / Critical 消息 → 走顶部信息条（弹窗太吵，同一条会刷屏）
"""
from __future__ import annotations

import sys
import traceback
import weakref

from PyQt6.QtCore import QObject, QTimer, qInstallMessageHandler

from ..api.core import logging as api_log

_seen: set[str] = set()          # 同一条 Qt 警告只提示一次


def install(window) -> None:
    """在 MainWindow 建好后调用一次。"""
    ref = weakref.ref(window)

    def excepthook(exc_type, exc, tb) -> None:
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
        api_log.get_logger().error("未捕获异常：%s", detail)
        target = ref()
        if target is None:
            return
        # 不能在异常传播路径里直接 exec 弹窗，挪到下一轮事件循环
        QTimer.singleShot(0, lambda: _show(target, exc_type, detail))

    sys.excepthook = excepthook

    def qt_handler(mode, context, message: str) -> None:
        text = str(message).strip()
        if not text:
            return
        if text in _seen:
            return
        _seen.add(text)
        api_log.get_logger().warning("Qt: %s", text)
        target = ref()
        if target is not None:
            QTimer.singleShot(0, lambda: target.show_notice(text))

    qInstallMessageHandler(qt_handler)


def _show(window, exc_type, detail: str) -> None:
    from ..widgets.dialog import alert

    name = getattr(exc_type, "__name__", "Error")
    head = detail.strip().splitlines()[-1][:200] if detail.strip() else name
    alert(window, "出了点问题", f"{head}\n\n详细信息已写入日志（设置 → 关于 → 打开日志目录）。",
          level="error")
