"""统一错误码与异常类型。

码表与重试策略是前后端（这里是「UI 层 ↔ api 层」）共用的契约，
任何模块都不许自造 code，一律从这里取。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """错误码。字符串值直接进日志与 UI 文案映射表。"""

    NETWORK = "NETWORK"  # 连接失败 / 超时
    UPSTREAM_5XX = "UPSTREAM_5XX"  # 上游 5xx
    AUTH_REQUIRED = "AUTH_REQUIRED"  # 未登录 / 登录态失效
    VIP_REQUIRED = "VIP_REQUIRED"  # 需要会员
    NO_COPYRIGHT = "NO_COPYRIGHT"  # 无版权
    URL_UNAVAILABLE = "URL_UNAVAILABLE"  # 所有直链 Provider 都失败
    RATE_LIMITED = "RATE_LIMITED"  # 429 / 风控
    PARSE_ERROR = "PARSE_ERROR"  # JSON / 模型校验失败


#: 每个错误码允许的「重试次数」（不含首次请求）
RETRY_LIMITS: dict[ErrorCode, int] = {
    ErrorCode.NETWORK: 2,
    ErrorCode.UPSTREAM_5XX: 1,
    ErrorCode.AUTH_REQUIRED: 0,
    ErrorCode.VIP_REQUIRED: 0,
    ErrorCode.NO_COPYRIGHT: 0,
    ErrorCode.URL_UNAVAILABLE: 0,
    ErrorCode.RATE_LIMITED: 0,
    ErrorCode.PARSE_ERROR: 0,
}


@dataclass
class ApiError(Exception):
    """所有对外抛出的错误都是它。

    Attributes:
        code: 错误码，见 :class:`ErrorCode`。
        message: 面向用户/日志的短描述。
        detail: 排障用的补充信息（已脱敏，长度受控）。
        request_id: 贯穿 UI → api → 上游的关联 id。
        status: 上游 HTTP 状态码（若有）。
    """

    code: ErrorCode
    message: str
    detail: str | None = None
    request_id: str | None = None
    status: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    @property
    def retryable(self) -> bool:
        return RETRY_LIMITS[self.code] > 0

    def to_dict(self) -> dict[str, Any]:
        """给 UI / 日志用的扁平结构。"""
        return {
            "code": self.code.value,
            "message": self.message,
            "detail": self.detail,
            "retryable": self.retryable,
            "requestId": self.request_id,
        }

    def __str__(self) -> str:  # pragma: no cover - 仅调试用
        tail = f" detail={self.detail}" if self.detail else ""
        return f"[{self.code.value}] {self.message}{tail}"
