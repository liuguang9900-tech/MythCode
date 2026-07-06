"""
工具注册中心测试 — 线程安全、分组加载、Schema 生成。
"""

import threading
import pytest
from tools.registry import ToolRegistry, registry, CORE_TOOLS, EXTENDED_TOOLS
from tools.base import BaseTool, ToolResult


class MockTool(BaseTool):
    """测试用 mock 工具"""

    def __init__(self, name: str, description: str = "test"):
        self.name = name
        self.description = description
        self.parameters = {}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="ok")


class TestToolRegistry:
    """工具注册中心测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        registry.clear()

    def test_register_and_get(self):
        """测试注册和获取"""
        tool = MockTool("test_tool")
        registry.register(tool)
        assert registry.get("test_tool") is tool

    def test_get_nonexistent(self):
        """测试获取不存在的工具"""
        assert registry.get("nonexistent") is None

    def test_duplicate_register_raises(self):
        """测试重复注册抛出异常"""
        tool1 = MockTool("dup_tool")
        registry.register(tool1)
        tool2 = MockTool("dup_tool")
        with pytest.raises(ValueError, match="已注册"):
            registry.register(tool2)

    def test_list_tools(self):
        """测试列出所有工具"""
        registry.register(MockTool("tool_a"))
        registry.register(MockTool("tool_b"))
        tools = registry.list_tools()
        assert len(tools) == 2

    def test_set_active_tools(self):
        """测试设置激活工具集"""
        registry.register(MockTool("tool_a"))
        registry.register(MockTool("tool_b"))
        registry.register(MockTool("tool_c"))

        registry.set_active_tools({"tool_a", "tool_b"})
        active = registry.list_active_tools()
        assert len(active) == 2
        active_names = {t.name for t in active}
        assert active_names == {"tool_a", "tool_b"}

    def test_set_active_none_means_all(self):
        """测试 None 表示全部激活"""
        registry.register(MockTool("tool_a"))
        registry.register(MockTool("tool_b"))

        registry.set_active_tools(None)
        active = registry.list_active_tools()
        assert len(active) == 2

    def test_activate_tool(self):
        """测试激活单个工具"""
        registry.register(MockTool("tool_a"))
        registry.set_active_tools(set())

        assert registry.activate_tool("tool_a") is True
        active = registry.list_active_tools()
        assert len(active) == 1

    def test_activate_nonexistent(self):
        """测试激活不存在的工具"""
        assert registry.activate_tool("nonexistent") is False

    def test_activate_when_all_active(self):
        """测试全部激活时 activate_tool 返回 True"""
        registry.register(MockTool("tool_a"))
        registry.set_active_tools(None)
        assert registry.activate_tool("tool_a") is True

    def test_get_schemas(self):
        """测试 Schema 生成"""
        tool = MockTool("schema_tool", "test description")
        tool.parameters = {
            "param1": {"type": "string", "description": "test", "required": True}
        }
        registry.register(tool)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "schema_tool"

    def test_clear(self):
        """测试清空注册表"""
        registry.register(MockTool("tool_a"))
        registry.set_active_tools({"tool_a"})
        registry.clear()
        assert len(registry.list_tools()) == 0
        assert registry.list_active_tools() == []

    def test_singleton(self):
        """测试单例模式"""
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_concurrent_register(self):
        """测试并发注册安全性"""
        num_threads = 10
        tools_per_thread = 20
        barrier = threading.Barrier(num_threads)

        def register_tools(thread_id):
            barrier.wait()  # 所有线程同时开始
            for i in range(tools_per_thread):
                try:
                    registry.register(MockTool(f"tool_{thread_id}_{i}"))
                except ValueError:
                    pass  # 忽略重复注册

        threads = [threading.Thread(target=register_tools, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证没有数据损坏
        total = len(registry.list_tools())
        assert total == num_threads * tools_per_thread

    def test_core_tools_not_empty(self):
        """测试核心工具集合非空"""
        assert len(CORE_TOOLS) > 0
        assert "read_file" in CORE_TOOLS
        assert "write_file" in CORE_TOOLS

    def test_extended_tools_not_empty(self):
        """测试扩展工具集合非空"""
        assert len(EXTENDED_TOOLS) > 0

    def test_core_and_extended_no_overlap(self):
        """测试核心工具和扩展工具无重叠"""
        overlap = CORE_TOOLS & EXTENDED_TOOLS
        assert len(overlap) == 0
