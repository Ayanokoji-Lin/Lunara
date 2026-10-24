"""Lunara 启动入口

python main.py
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lunara.main_window import MainWindow
from lunara.theme import qss


def main() -> int:
    # 高分屏：不取整缩放，避免 125% 下的模糊
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

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
