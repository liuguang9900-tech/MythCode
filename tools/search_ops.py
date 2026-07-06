"""
代码搜索工具：Search_Code（基于 ripgrep 的全局搜索）
"""

import asyncio
import os
import platform
from pathlib import Path
from typing import Optional

from tools.base import BaseTool, ToolResult
from tools.sandbox import get_sandbox
from config import get_config
from utils.agentignore import get_ignore_manager


class SearchCodeTool(BaseTool):
    """在项目中进行代码搜索（优先使用 ripgrep，回退到 Python 实现）"""

    name = "search_code"
    description = "在项目代码中搜索文本或正则，返回匹配文件和行内容（默认最多 50 条，支持正则）。"
    parameters = {
        "pattern": {
            "type": "string",
            "description": "搜索模式，支持正则",
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "搜索目录，默认项目根",
            "required": False,
        },
        "file_types": {
            "type": "string",
            "description": "文件类型过滤，如 '*.py'",
            "required": False,
        },
        "context_lines": {
            "type": "integer",
            "description": "上下文行数，默认 2",
            "required": False,
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "是否区分大小写，默认 false",
            "required": False,
        },
        "output_mode": {
            "type": "string",
            "description": "输出模式: content/files_with_matches/count",
            "required": False,
        },
    }

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        file_types: Optional[str] = None,
        context_lines: int = 2,
        case_sensitive: bool = False,
        output_mode: str = "content",
    ) -> ToolResult:
        sandbox = get_sandbox()
        cfg = get_config()

        try:
            search_root = sandbox.resolve_path(path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if not search_root.exists():
            return ToolResult(success=False, output="", error=f"路径不存在: {path}")

        # 优先尝试 ripgrep
        if await self._has_ripgrep():
            return await self._search_with_rg(
                pattern, search_root, file_types, context_lines,
                case_sensitive, output_mode, cfg
            )
        else:
            return await self._search_with_python(
                pattern, search_root, file_types, context_lines,
                case_sensitive, output_mode, cfg
            )

    async def _has_ripgrep(self) -> bool:
        """检查系统是否安装了 ripgrep"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rg", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def _search_with_rg(
        self, pattern: str, root: Path, file_types: Optional[str],
        context_lines: int, case_sensitive: bool, output_mode: str,
        cfg,
    ) -> ToolResult:
        """使用 ripgrep 搜索"""
        cmd = ["rg", "--no-heading", "--with-filename", "--line-number"]

        if not case_sensitive:
            cmd.append("--ignore-case")

        if output_mode == "files_with_matches":
            cmd.append("--files-with-matches")
        elif output_mode == "count":
            cmd.append("--count")
        else:
            cmd.extend(["-C", str(context_lines)])

        # 使用 .agentignore / .gitignore 作为忽略文件
        ignore_mgr = get_ignore_manager(str(root), cfg.tools.search_respect_gitignore)
        ignore_file = ignore_mgr.get_ignore_file_path()
        if ignore_file and ignore_file.exists():
            cmd.extend(["--ignore-file", str(ignore_file)])

        # 文件类型过滤
        if file_types:
            for ft in file_types.split(","):
                ft = ft.strip()
                if ft.startswith("*."):
                    cmd.extend(["--type-add", f"custom:*{ft}"])
                    cmd.extend(["-t", "custom"])
                elif ft.startswith("."):
                    cmd.extend(["-g", f"*{ft}"])

        # 限制结果数
        cmd.extend(["-m", str(cfg.tools.search_max_results)])

        cmd.append(pattern)
        cmd.append(str(root))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=30
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error="搜索超时")
        except FileNotFoundError:
            return ToolResult(success=False, output="", error="ripgrep 不可用")

        output = stdout.decode("utf-8", errors="replace")
        if not output:
            output = f"未找到匹配 '{pattern}' 的结果"

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "engine": "ripgrep",
                "pattern": pattern,
                "path": str(root),
            },
        )

    async def _search_with_python(
        self, pattern: str, root: Path, file_types: Optional[str],
        context_lines: int, case_sensitive: bool, output_mode: str,
        cfg,
    ) -> ToolResult:
        """Python 回退搜索实现"""
        import re
        import fnmatch

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"无效的正则表达式: {e}")

        # 解析文件类型过滤
        type_patterns = None
        if file_types:
            type_patterns = [
                ft.strip() if ft.startswith("*") else f"*{ft.strip()}"
                for ft in file_types.split(",")
            ]

        results = []
        file_count = 0
        match_count = 0

        ignore_mgr = get_ignore_manager(str(root), cfg.tools.search_respect_gitignore)

        for dirpath, dirnames, filenames in os.walk(str(root)):
            # 使用 .agentignore / .gitignore 规则过滤目录
            dirnames[:] = [
                d for d in dirnames
                if not ignore_mgr.is_ignored(Path(dirpath) / d, root)
            ]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                if ignore_mgr.is_ignored(filepath, root):
                    continue
                if type_patterns and not any(
                    fnmatch.fnmatch(filename, p) for p in type_patterns
                ):
                    continue

                filepath_str = str(filepath)
                try:
                    with open(filepath_str, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except (OSError, UnicodeDecodeError):
                    continue

                file_matches = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        file_matches.append(i)
                        match_count += 1

                if file_matches:
                    file_count += 1
                    rel_path = os.path.relpath(filepath_str, str(root))

                    if output_mode == "files_with_matches":
                        results.append(rel_path)
                    elif output_mode == "count":
                        results.append(f"{rel_path}: {len(file_matches)}")
                    else:
                        for line_no in file_matches:
                            start = max(0, line_no - context_lines)
                            end = min(len(lines), line_no + context_lines + 1)
                            for ctx_i in range(start, end):
                                prefix = ">" if ctx_i == line_no else " "
                                results.append(
                                    f"{rel_path}:{ctx_i + 1}:{prefix}{lines[ctx_i].rstrip()}"
                                )
                            results.append("--")

                if match_count >= cfg.tools.search_max_results:
                    results.append(f"... (结果截断，共找到 {match_count}+ 处匹配)")
                    break

            if match_count >= cfg.tools.search_max_results:
                break

        output = "\n".join(results) if results else f"未找到匹配 '{pattern}' 的结果"

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "engine": "python",
                "pattern": pattern,
                "path": str(root),
                "files_matched": file_count,
                "total_matches": match_count,
            },
        )
