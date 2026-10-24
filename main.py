"""Lunara 启动入口

python main.py
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lunara.main_window import MainWindow
from lunara.theme import qss


def configure_webengine_proxy() -> None:
    """把环境变量里的代理转给 Chromium。

    Windows 上 Chromium 读系统代理，不读 ``HTTPS_PROXY``；但终端/沙箱里跑的时候
    往往只有环境变量（httpx 认，Chromium 不认），内嵌登录页就会一直加载不出来。
    这里做一个桥接：有环境变量就转成 ``--proxy-server``，没有就什么都不做。
    """
    if os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS"):
        return
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(key)
        if value:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"--proxy-server={value}"
            return


def main() -> int:
    # 高分屏：不取整缩放，避免 125% 下的模糊
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # 登录用的内嵌浏览器（QtWebEngine）要求这个属性在 QApplication 之前设置；
    # 先设好，登录窗口就可以按需再 import，不拖慢启动。
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    configure_webengine_proxy()

    app = QApplication(sys.argv)
    app.setApplicationName("Lunara")
    app.setApplicationDisplayName("Lunara")
    app.setStyle("Fusion")          # Fusion 才能让 QSS 完全接管控件外观
    app.setStyleSheet(qss())

    f = QFont()
    f.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei",
                   "Segoe UI", "SF Pro Display"])
    f.setPixelSize(12)
    app.setFont(f)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
