"""
工具注册中心 — 管理所有工具的注册、查找和 Schema 生成。
使用装饰器模式注册工具，自动生成 OpenAI Function Calling 格式。
支持工具分组：核心工具始终加载，扩展工具按需加载以节省 token。
线程安全：使用 threading.Lock 保护并发注册与查询。
"""

import threading
from typing import Optional

from tools.base import BaseTool


# 工具分组：核心工具始终加载，扩展工具按需加载
CORE_TOOLS = {
    "read_file", "write_file", "edit_file",
    "execute_command", "glob", "search_code", "list_directory",
}

# 扩展工具：仅在需要时加载
EXTENDED_TOOLS = {
    "todo_write", "task", "web_fetch", "web_search",
    "notebook_edit", "read_image",
    "read_skill", "list_skills", "task_team",
}


class ToolRegistry:
    """工具注册中心（单例模式，线程安全）"""

    _instance: Optional["ToolRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "ToolRegistry":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._tools: dict[str, BaseTool] = {}
                cls._instance._active_tools: Optional[set[str]] = None  # None=全部激活
                cls._instance._lock = threading.RLock()  # 可重入锁，保护 _tools 和 _active_tools
        return cls._instance

    def register(self, tool: BaseTool) -> BaseTool:
        """注册一个工具实例"""
        with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"工具 '{tool.name}' 已注册")
            self._tools[tool.name] = tool
            return tool

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具（无论是否激活）"""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """获取所有已注册工具"""
        with self._lock:
            return list(self._tools.values())

    def list_active_tools(self) -> list[BaseTool]:
        """获取当前激活的工具（用于 schema 生成）"""
        with self._lock:
            if self._active_tools is None:
                return list(self._tools.values())
            return [t for name, t in self._tools.items() if name in self._active_tools]

    def set_active_tools(self, tool_names: Optional[set[str]]) -> None:
        """
        设置当前激活的工具集合。
        None 表示全部激活；set 表示仅激活集合内的工具。
        """
        with self._lock:
            self._active_tools = tool_names

    def activate_tool(self, name: str) -> bool:
        """激活单个工具，返回是否成功"""
        with self._lock:
            if name not in self._tools:
                return False
            if self._active_tools is None:
                return True  # 已全部激活
            self._active_tools.add(name)
            return True

    def get_schemas(self) -> list[dict]:
        """获取当前激活工具的 OpenAI Function Calling Schema"""
        return [tool.to_openai_schema() for tool in self.list_active_tools()]

    def clear(self) -> None:
        """清空所有注册（主要用于测试）"""
        with self._lock:
            self._tools.clear()
            self._active_tools = None


# 全局注册中心实例
registry = ToolRegistry()


def register_tool(tool: BaseTool) -> BaseTool:
    """便捷注册函数"""
    return registry.register(tool)
