"""错误码 → 人话。

UI 只显示这一层文案：`ErrorCode` 是给日志和测试看的，用户不需要看到 `URL_UNAVAILABLE`。
"""
from __future__ import annotations

from ..api.errors import ApiError, ErrorCode

ERROR_TEXT: dict[ErrorCode, str] = {
    ErrorCode.NETWORK: "网络不可用，请检查连接",
    ErrorCode.AUTH_REQUIRED: "登录已失效，请重新登录",
    ErrorCode.VIP_REQUIRED: "该歌曲需要会员",
    ErrorCode.NO_COPYRIGHT: "该歌曲暂无版权",
    ErrorCode.URL_UNAVAILABLE: "暂时无法获取播放地址",
    ErrorCode.RATE_LIMITED: "请求过于频繁，请稍后再试",
    ErrorCode.UPSTREAM_5XX: "服务异常，请稍后再试",
    ErrorCode.PARSE_ERROR: "数据解析失败，请稍后再试",
}


def error_text(err: BaseException | ErrorCode | None, fallback: str = "操作失败") -> str:
    if err is None:
        return fallback
    if isinstance(err, ErrorCode):
        return ERROR_TEXT.get(err, fallback)
    if isinstance(err, ApiError):
        return ERROR_TEXT.get(err.code, fallback)
    message = str(err).strip()
    return message or fallback
