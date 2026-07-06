"""
沙箱与安全拦截模块
- 路径校验：限制文件操作在 Project Root 内
- 命令检测：拦截危险命令模式
- 用户确认：高风险操作暂停请求授权
"""

import re
import os
from pathlib import Path
from typing import Optional

from config import get_config


class Sandbox:
    """安全沙箱 — 命令执行前的多层安全检查"""

    def __init__(self, project_root: Optional[str] = None):
        cfg = get_config()
        self.project_root = Path(project_root or cfg.safety.project_root).resolve()
        self.require_approval = cfg.safety.require_approval
        self.dangerous_patterns = cfg.safety.dangerous_commands
        self.protected_paths = cfg.safety.protected_paths
        self.allowed_patterns = cfg.safety.allowed_commands
        self.additional_roots: list[Path] = []

    def set_additional_roots(self, roots: list[str]) -> None:
        """设置额外的工作目录"""
        self.additional_roots = [Path(r).resolve() for r in roots]

    # ---- 路径安全 ----

    def resolve_path(self, path: str) -> Path:
        """将相对路径解析为绝对路径，并校验是否在允许的 root 内"""
        p = Path(path)
        if not p.is_absolute():
            p = (self.project_root / p).resolve()
        else:
            p = p.resolve()

        # 检查是否在任一允许的 root 内
        all_roots = [self.project_root] + self.additional_roots
        for root in all_roots:
            try:
                p.relative_to(root)
                return p
            except ValueError:
                continue

        raise PermissionError(
            f"安全限制：路径 '{path}' 不在允许的目录内"
        )

    def is_protected_path(self, path: str) -> bool:
        """检查路径是否属于受保护的系统路径"""
        expanded = Path(os.path.expanduser(path)).resolve()
        for protected in self.protected_paths:
            protected_expanded = Path(os.path.expanduser(protected)).resolve()
            try:
                expanded.relative_to(protected_expanded)
                return True
            except ValueError:
                pass
        return False

    # ---- 命令安全 ----

    def check_command(self, command: str) -> tuple[bool, str]:
        """
        检查命令是否安全。

        Returns:
            (is_safe, reason): is_safe=True 表示可以直接执行；
                              is_safe=False 表示需要用户确认或拒绝。
        """
        # 1. 白名单优先：匹配则直接放行
        for pattern in self.allowed_patterns:
            if re.search(pattern, command):
                return True, ""

        # 2. 黑名单检测：匹配则需要确认
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command):
                return False, f"检测到危险命令模式: {pattern}"

        # 3. 默认：不在白名单也不在黑名单，需要确认
        if self.require_approval:
            return False, "该命令不在白名单中，需要确认执行"

        return True, ""

    def needs_approval(self, command: str) -> bool:
        """判断命令是否需要用户确认"""
        is_safe, _ = self.check_command(command)
        return not is_safe

    def get_approval_message(self, command: str) -> str:
        """生成用户确认提示信息"""
        _, reason = self.check_command(command)
        return (
            f"\n[警告] {reason}\n"
            f"  命令: {command}\n"
            f"  工作目录: {self.project_root}\n"
            f"  是否执行? (y/n): "
        )


# 全局沙箱实例
_sandbox: Optional[Sandbox] = None


def get_sandbox() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox()
    return _sandbox
