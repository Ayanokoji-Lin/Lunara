"""单实例：第二个进程把「显示窗口」消息发给第一个，然后自己退出。"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "Lunara.SingleInstance"


class SingleInstance(QObject):
    """抢到名字的那个进程负责监听，其余进程发完消息就退出。"""

    activated = pyqtSignal()      # 又有人双击图标了

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server: QLocalServer | None = None

    # ------------------------------------------------------------------ #
    def try_lock(self, timeout_ms: int = 300) -> bool:
        """True = 我是第一个实例；False = 已有实例在跑（并且已通知它）。"""
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(timeout_ms):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(timeout_ms)
            socket.disconnectFromServer()
            return False

        QLocalServer.removeServer(SERVER_NAME)   # 上次崩溃残留的套接字
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        return self._server.listen(SERVER_NAME)

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is not None:
                socket.readyRead.connect(lambda s=socket: self._on_read(s))
                socket.disconnected.connect(socket.deleteLater)

    def _on_read(self, socket: QLocalSocket) -> None:
        if socket.readAll():
            self.activated.emit()
