"""浏览器登录：打开网易云登录页，登录成功后抓 Cookie。

为什么用内嵌 Chromium 而不是调系统浏览器：
系统浏览器的 Cookie 存在哪、怎么解，各浏览器不同，去读别人的 cookie 库既不可靠也不合适；
内嵌视图的 Cookie 由 Qt 自己的 cookieStore 暴露，登录完直接就能拿到，也不需要实现
任何登录加密协议（扫码 / 手机号那套 weapi 组包）。

只收 ``.music.163.com`` 域下的 Cookie，并且一旦出现 ``MUSIC_U`` 就认为登录成功，
立刻把收集到的值交给上层（上层负责加密落盘）。
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

try:  # 没装 PyQt6-WebEngine 时给出可读提示，而不是 ImportError 崩掉
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - 取决于环境
    QWebEngineView = None  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False

#: 网易云网页版登录页（登录成功后 cookieStore 里会出现 MUSIC_U）
LOGIN_URL = "https://music.163.com/#/login"
COOKIE_DOMAIN = "music.163.com"
#: 出现这个键就说明登录成功
REQUIRED_COOKIE = "MUSIC_U"

DIALOG_SIZE = (940, 700)


class LoginDialog(QDialog):
    """登录窗口。成功时发 ``cookiesCollected(dict)`` 并自动关闭。"""

    cookiesCollected = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None, *, url: str = LOGIN_URL) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录网易云音乐")
        self.resize(*DIALOG_SIZE)
        self._cookies: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not WEBENGINE_AVAILABLE or QWebEngineView is None:
            hint = QLabel(
                "缺少 PyQt6-WebEngine，无法内嵌登录。\n\n"
                "可以执行：\n"
                "    .venv/Scripts/python.exe -m pip install PyQt6-WebEngine\n\n"
                "或在设置里改用「粘贴 Cookie」。"
            )
            hint.setWordWrap(True)
            hint.setContentsMargins(28, 28, 28, 28)
            layout.addWidget(hint)
            return

        self.view = QWebEngineView(self)
        layout.addWidget(self.view, 1)

        # 加载失败时给一条可操作的提示（常见原因：无 GPU 环境 / 代理没通）
        self._hint = QLabel(
            "页面没能加载出来。可以试试：\n"
            "1) 确认网络能打开 music.163.com；\n"
            "2) 若使用了代理，设置环境变量 HTTPS_PROXY 后重启；\n"
            "3) 若窗口一片空白，设置 QT_OPENGL=software 后重启。"
        )
        self._hint.setWordWrap(True)
        self._hint.setContentsMargins(16, 10, 16, 10)
        self._hint.setVisible(False)
        layout.addWidget(self._hint)

        store = self.view.page().profile().cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)
        self.view.loadFinished.connect(self._on_load_finished)
        self.view.load(QUrl(url))

    def _on_load_finished(self, ok: bool) -> None:
        self._hint.setVisible(not ok)

    # ------------------------------------------------------------------ #
    def _on_cookie_added(self, cookie: Any) -> None:
        try:
            name = bytes(cookie.name()).decode("utf-8", "ignore")
            value = bytes(cookie.value()).decode("utf-8", "ignore")
            domain = cookie.domain() or ""
        except Exception:  # noqa: BLE001 - Cookie 结构异常不该影响登录
            return

        if COOKIE_DOMAIN not in domain:
            return
        if not name or not value:
            return

        self._cookies[name] = value
        if name == REQUIRED_COOKIE:
            self.cookiesCollected.emit(dict(self._cookies))
            self.accept()

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)


def collect_login_cookies(parent: QWidget | None = None) -> dict[str, str] | None:
    """打开登录窗口，返回收集到的 Cookie；取消或失败返回 ``None``。"""
    dialog = LoginDialog(parent)
    result: dict[str, str] = {}

    def on_collected(cookies: dict[str, str]) -> None:
        result.update(cookies)

    dialog.cookiesCollected.connect(on_collected)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return result if accepted and result else None
