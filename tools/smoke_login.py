"""登录窗口冒烟：确认内嵌浏览器能起来、能加载登录页（不真的登录）。

    .venv/Scripts/python.exe tools/smoke_login.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

from main import configure_webengine_proxy  # noqa: E402

configure_webengine_proxy()
print("Chromium flags:", os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "(未设置)"))


def main() -> int:
    from lunara.services import login_browser

    print("WebEngine 可用:", login_browser.WEBENGINE_AVAILABLE)
    if not login_browser.WEBENGINE_AVAILABLE:
        print("!! 没装 PyQt6-WebEngine，登录会退化为提示页")
        return 1

    app = QApplication(sys.argv)
    dialog = login_browser.LoginDialog()
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.show()

    deadline = time.time() + 20
    loaded = False
    while time.time() < deadline:
        app.processEvents()
        title = dialog.view.page().title()
        if title:
            print(f"页面标题: {title}")
            loaded = True
            break
        time.sleep(0.05)

    print("加载成功" if loaded else "!! 20 秒内没拿到页面标题")

    # Cookie 是在页面脚本跑起来之后才陆续写入的，再等一会儿
    end = time.time() + 8
    while time.time() < end and not dialog.cookies:
        app.processEvents()
        time.sleep(0.05)

    names = sorted(dialog.cookies)
    print(f"已收到 Cookie {len(names)} 个: {', '.join(names[:8])}")
    print("（登录成功后会出现 MUSIC_U，窗口会自动关闭）")
    dialog.close()
    return 0 if loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
