"""结构化日志 + 脱敏。

一行一条 JSON，字段固定：requestId / route / upstream / status / latencyMs / cacheHit。
Cookie、MUSIC_U、params 等敏感字段一律打码，禁止原样落盘。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Mapping

LOGGER_NAME = "lunara.api"

#: 命中即打码的键（大小写不敏感，做子串匹配）
SENSITIVE_KEYS = ("cookie", "music_u", "musica", "__csrf", "token", "params", "password", "auth")

MASK = "***"
_MAX_DETAIL = 512


LOG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "Lunara" / "logs"
LOG_FILE = LOG_DIR / "lunara.log"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        # 同时落盘：出问题时用户能直接把日志发出来（1MB × 3 轮转）
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                LOG_FILE, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger.addHandler(file_handler)
        except OSError:
            pass                      # 目录不可写就只打控制台
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def configure(level: int = logging.INFO) -> None:
    """给宿主（main.py / 调试脚本）调，用来调级别。"""
    logger = get_logger()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


def redact(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """把敏感键的值替换成 ``***``，其余原样。"""
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        lowered = str(key).lower()
        out[key] = MASK if any(word in lowered for word in SENSITIVE_KEYS) else value
    return out


def truncate(text: str, limit: int = _MAX_DETAIL) -> str:
    return text if len(text) <= limit else f"{text[:limit]}…(+{len(text) - limit}B)"


def log_request(
    *,
    request_id: str,
    route: str,
    upstream: str,
    status: int | None,
    latency_ms: float,
    cache_hit: bool,
    error: str | None = None,
) -> None:
    """每次 api 调用结束都调一次。"""
    record: dict[str, Any] = {
        "requestId": request_id,
        "route": route,
        "upstream": upstream,
        "status": status,
        "latencyMs": round(latency_ms, 1),
        "cacheHit": cache_hit,
        "ts": int(time.time() * 1000),
    }
    if error:
        record["error"] = error
    get_logger().info(json.dumps(record, ensure_ascii=False))
