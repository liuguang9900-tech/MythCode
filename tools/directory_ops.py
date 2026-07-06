"""
目录操作工具：List_Directory（tree 结构输出）
"""

import os
from pathlib import Path
from typing import Optional

from tools.base import BaseTool, ToolResult
from tools.sandbox import get_sandbox
from utils.agentignore import get_ignore_manager


class ListDirectoryTool(BaseTool):
    """列出目录结构，支持 tree 风格输出"""

    name = "list_directory"
    description = "以 tree 风格列出目录结构（默认深度 2，遵循 .agentignore/.gitignore）。"
    parameters = {
        "path": {
            "type": "string",
            "description": "目录路径，默认项目根",
            "required": False,
        },
        "depth": {
            "type": "integer",
            "description": "递归深度，默认 2",
            "required": False,
        },
        "ignore": {
            "type": "array",
            "items": {"type": "string"},
            "description": "额外忽略的 glob 模式",
            "required": False,
        },
    }

    async def execute(
        self,
        path: str = ".",
        depth: int = 2,
        ignore: Optional[list[str]] = None,
    ) -> ToolResult:
        sandbox = get_sandbox()

        try:
            root = sandbox.resolve_path(path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if not root.exists():
            return ToolResult(success=False, output="", error=f"路径不存在: {path}")
        if not root.is_dir():
            return ToolResult(success=False, output="", error=f"路径不是目录: {path}")

        # 使用 .agentignore / .gitignore 规则 + 用户指定的额外忽略模式
        ignore_mgr = get_ignore_manager(str(sandbox.project_root))
        extra_patterns = set(ignore or [])

        lines = [str(root)]
        self._walk(root, depth, ignore_mgr, extra_patterns, lines, prefix="")
        output = "\n".join(lines)

        return ToolResult(
            success=True,
            output=output,
            metadata={"path": str(root), "depth": depth},
        )

    def _walk(
        self,
        directory: Path,
        max_depth: int,
        ignore_mgr,
        extra_patterns: set[str],
        lines: list[str],
        prefix: str,
        current_depth: int = 0,
    ) -> None:
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            lines.append(f"{prefix}[权限不足]")
            return

        # 过滤：先检查 agentignore 规则，再检查额外模式
        entries = [
            e for e in entries
            if not ignore_mgr.is_ignored(e) and not self._match_extra(e, extra_patterns)
        ]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk(
                    entry,
                    max_depth,
                    ignore_mgr,
                    extra_patterns,
                    lines,
                    prefix + extension,
                    current_depth + 1,
                )

    @staticmethod
    def _match_extra(entry: Path, patterns: set[str]) -> bool:
        """检查条目是否匹配用户指定的额外忽略模式"""
        import fnmatch
        name = entry.name
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False
