"""api 层出口。

UI 只允许从这里拿 :class:`ApiClient` 与各模块函数，
不允许 import ``lunara.api.core.crypto``（密钥与组包细节留在内层）。
"""
from __future__ import annotations

from threading import Lock

from .client import ApiClient
from .errors import ApiError, ErrorCode

__all__ = ["ApiClient", "ApiError", "ErrorCode", "aclose_client", "get_client"]

_client: ApiClient | None = None
_lock = Lock()


def get_client() -> ApiClient:
    """进程内单例。首次调用才建连接池，import 本包不会碰网络。

    注意：单例绑定第一次使用它的事件循环，后台桥接层（``services.async_bridge``）
    保证所有请求都跑在同一个 loop 上。
    """
    global _client
    with _lock:
        if _client is None:
            _client = ApiClient()
        return _client


async def aclose_client() -> None:
    """退出时关掉连接池。"""
    global _client
    with _lock:
        client, _client = _client, None
    if client is not None:
        await client.aclose()
