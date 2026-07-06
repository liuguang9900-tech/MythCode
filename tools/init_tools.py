"""
工具初始化 — 注册所有内置工具到全局注册中心。
在 Agent 启动时调用一次即可。
"""

from tools.registry import registry
from tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, ReadImageTool
from tools.directory_ops import ListDirectoryTool
from tools.command_ops import ExecuteCommandTool
from tools.search_ops import SearchCodeTool
from tools.glob_ops import GlobTool
from tools.todo_ops import TodoWriteTool
from tools.task_ops import TaskTool
from tools.web_ops import WebFetchTool, WebSearchTool


def register_all_tools() -> None:
    """注册所有内置工具"""
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirectoryTool())
    registry.register(ExecuteCommandTool())
    registry.register(SearchCodeTool())
    registry.register(GlobTool())
    registry.register(TodoWriteTool())
    registry.register(TaskTool())
    # Web 工具（可选，依赖 httpx）
    try:
        registry.register(WebFetchTool())
        registry.register(WebSearchTool())
    except Exception:
        pass
    # Notebook 工具（可选，依赖 nbformat）
    try:
        from tools.notebook_ops import NotebookEditTool
        registry.register(NotebookEditTool())
    except Exception:
        pass
    # 图片读取工具（多模态支持）
    try:
        registry.register(ReadImageTool())
    except Exception:
        pass
