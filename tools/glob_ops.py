"""
文件名模式匹配工具：Glob — 按 glob 模式查找文件。
"""

from pathlib import Path
from typing import Optional

from tools.base import BaseTool, ToolResult
from tools.sandbox import get_sandbox
from config import get_config
from utils.agentignore import get_ignore_manager
from utils.glob_utils import find_files


class GlobTool(BaseTool):
    """按 glob 模式查找文件（支持 ** 递归匹配）"""

    name = "glob"
    description = "按 glob 模式查找文件路径，支持 ** 递归匹配（默认最多 100 个结果）。"
    parameters = {
        "pattern": {
            "type": "string",
            "description": "glob 模式，支持 **/*/?",
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "搜索根目录，默认项目根",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "最大返回数，默认 100",
            "required": False,
        },
    }

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        limit: int = 100,
    ) -> ToolResult:
        """执行 glob 模式匹配"""
        sandbox = get_sandbox()
        cfg = get_config()

        # 解析搜索根目录
        try:
            if path:
                search_root = sandbox.resolve_path(path)
            else:
                search_root = Path(sandbox.project_root)
        except PermissionError as e:
            return ToolResult(
                success=False, output="", error=f"路径权限不足: {e}"
            )

        if not search_root.exists():
            return ToolResult(
                success=False, output="", error=f"目录不存在: {search_root}"
            )
        if not search_root.is_dir():
            return ToolResult(
                success=False, output="", error=f"不是目录: {search_root}"
            )

        # 获取忽略规则管理器
        ignore_mgr = get_ignore_manager(
            str(sandbox.project_root), cfg.tools.search_respect_gitignore
        )

        # 执行查找
        try:
            results = find_files(
                root=search_root,
                pattern=pattern,
                ignore_manager=ignore_mgr,
                limit=limit,
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"glob 查找失败: {e}"
            )

        if not results:
            return ToolResult(
                success=True,
                output=f"未找到匹配 '{pattern}' 的文件",
                metadata={"pattern": pattern, "count": 0, "results": []},
            )

        # 格式化输出
        output_lines = [f"找到 {len(results)} 个匹配 '{pattern}' 的文件:"]
        output_lines.extend(f"  {r}" for r in results)

        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            metadata={
                "pattern": pattern,
                "count": len(results),
                "results": results,
            },
        )
