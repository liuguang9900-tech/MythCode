"""
审计日志 — 记录安全相关事件，用于合规与追溯。

记录事件：
- 权限拒绝
- 危险命令拦截
- bypass/auto 模式启用
- 敏感文件访问
- 配置变更

存储路径：~/.mythcoder/audit.log
"""

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional


class AuditLogger:
    """审计日志记录器（单例）"""

    _instance: Optional["AuditLogger"] = None

    def __new__(cls) -> "AuditLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 审计日志独立文件
        log_dir = Path.home() / ".mythcoder"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "audit.log"

        self._logger = logging.getLogger("mythcoder.audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # 不传播到主 logger

        if not self._logger.handlers:
            handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=20,  # 保留 20 份
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def log_permission_denied(self, tool: str, reason: str, args: dict) -> None:
        """记录权限拒绝事件"""
        self._log("PERMISSION_DENIED", tool=tool, reason=reason, args=args)

    def log_dangerous_command(self, command: str, pattern: str) -> None:
        """记录危险命令拦截"""
        self._log("DANGEROUS_COMMAND_BLOCKED", command=command, pattern=pattern)

    def log_bypass_enabled(self, mode: str) -> None:
        """记录 bypass/auto 模式启用"""
        self._log("BYPASS_MODE_ENABLED", mode=mode)

    def log_protected_path_access(self, path: str, tool: str) -> None:
        """记录受保护路径访问尝试"""
        self._log("PROTECTED_PATH_ACCESS", path=path, tool=tool)

    def log_config_change(self, key: str, old_value: str, new_value: str) -> None:
        """记录配置变更"""
        self._log("CONFIG_CHANGED", key=key, old_value=old_value, new_value=new_value)

    def log_tool_execution(self, tool: str, success: bool, duration_ms: float, args: dict) -> None:
        """记录工具执行（用于审计追溯）"""
        self._log(
            "TOOL_EXECUTED",
            tool=tool,
            success=success,
            duration_ms=duration_ms,
            args=args,
        )

    def _log(self, event: str, **kwargs) -> None:
        """写入审计日志（JSON 格式）"""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **kwargs,
        }
        self._logger.info(json.dumps(entry, ensure_ascii=False, default=str))


# 全局实例
audit_logger = AuditLogger()
