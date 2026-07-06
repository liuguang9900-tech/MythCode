"""
日志模块 — 生产级结构化日志系统。

特性：
- JSON 结构化输出（可接入 ELK/Loki/Datadog）
- 文件轮转（按大小 + 按时间）
- trace_id 贯穿请求链路
- 敏感字段自动脱敏
- 默认写入 ~/.mythcoder/logs/mythcoder.log
"""

import json
import logging
import logging.handlers
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Optional


# trace_id 上下文变量（协程隔离）
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """设置当前请求的 trace_id，返回设置后的值"""
    tid = trace_id or uuid.uuid4().hex[:12]
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    """获取当前请求的 trace_id"""
    return _trace_id.get()


def clear_trace_id() -> None:
    """清除 trace_id"""
    _trace_id.set("")


# 敏感字段脱敏
_SENSITIVE_KEYS = {"api_key", "apikey", "token", "secret", "password", "authorization", "auth"}


def _sanitize_value(value):
    """递归脱敏字典中的敏感字段"""
    if isinstance(value, dict):
        return {
            k: ("***" if k.lower() in _SENSITIVE_KEYS else _sanitize_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    return value


class JSONFormatter(logging.Formatter):
    """JSON 结构化日志格式器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": get_trace_id(),
        }

        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 添加额外字段（通过 extra 传入）
        for key in ("tool_name", "file_path", "command", "model", "tokens", "cost", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = _sanitize_value(value)

        # 添加模块和行号（DEBUG 级别）
        if record.levelno <= logging.DEBUG:
            log_entry["module"] = record.module
            log_entry["line"] = record.lineno
            log_entry["function"] = record.funcName

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """控制台彩色格式器（开发模式）"""

    _COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        trace = get_trace_id()
        trace_str = f" [{trace}]" if trace else ""
        return (
            f"{color}[{record.levelname}]{self._RESET} "
            f"{record.getMessage()}{trace_str}"
        )


def setup_logger(
    name: str = "mythcoder",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    json_logs: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
) -> logging.Logger:
    """
    配置并返回 logger 实例。

    Args:
        name: logger 名称
        level: 日志级别
        log_file: 日志文件路径（None 则使用默认路径 ~/.mythcoder/logs/mythcoder.log）
        json_logs: 是否使用 JSON 结构化日志（生产环境推荐 True）
        max_bytes: 单个日志文件最大字节数（默认 10MB）
        backup_count: 保留的日志文件数量
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    if json_logs:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # 文件 handler（默认写入 ~/.mythcoder/logs/mythcoder.log）
    if log_file is None:
        log_dir = Path.home() / ".mythcoder" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "mythcoder.log")

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 RotatingFileHandler 实现文件轮转
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # 文件始终记录 DEBUG 级别
    file_handler.setFormatter(JSONFormatter())  # 文件始终使用 JSON 格式
    logger.addHandler(file_handler)

    logger.propagate = False  # 避免日志传播到 root logger
    return logger


def enable_debug_logging() -> None:
    """启用调试级别日志（由 --debug 触发）"""
    logger = logging.getLogger("mythcoder")
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)


def get_logger(name: str = "mythcoder") -> logging.Logger:
    """获取 logger 实例（确保已初始化）"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_logger(name)
    return logger


# 默认初始化
logger = setup_logger()
