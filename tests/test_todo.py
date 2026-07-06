"""
TODO 管理器测试 — 测试 agent/todo.py 和 tools/todo_ops.py
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTodoManager:
    """TodoManager 状态管理器测试"""

    def test_empty_todos(self):
        from agent.todo import TodoManager
        mgr = TodoManager()

        assert not mgr.has_todos()
        assert mgr.get_todos() == []
        assert mgr.get_context_for_prompt() == ""
        assert mgr.get_progress_summary() == "无任务"

    def test_update_todos(self):
        from agent.todo import TodoManager, TodoItem, TodoStatus
        mgr = TodoManager()

        todos = [
            TodoItem(content="任务1", status=TodoStatus.PENDING),
            TodoItem(content="任务2", status=TodoStatus.IN_PROGRESS, active_form="正在执行任务2"),
            TodoItem(content="任务3", status=TodoStatus.COMPLETED),
        ]
        mgr.update_todos(todos)

        assert mgr.has_todos()
        assert len(mgr.get_todos()) == 3

    def test_context_for_prompt(self):
        from agent.todo import TodoManager, TodoItem, TodoStatus
        mgr = TodoManager()

        todos = [
            TodoItem(content="待办任务", status=TodoStatus.PENDING),
            TodoItem(content="进行中任务", status=TodoStatus.IN_PROGRESS, active_form="正在处理"),
            TodoItem(content="已完成任务", status=TodoStatus.COMPLETED),
        ]
        mgr.update_todos(todos)

        context = mgr.get_context_for_prompt()
        assert "当前任务清单" in context
        assert "待办任务" in context
        assert "正在处理" in context  # active_form 优先
        assert "已完成任务" in context
        assert "○" in context  # pending icon
        assert "◐" in context  # in_progress icon
        assert "●" in context  # completed icon

    def test_progress_summary(self):
        from agent.todo import TodoManager, TodoItem, TodoStatus
        mgr = TodoManager()

        todos = [
            TodoItem(content="任务1", status=TodoStatus.PENDING),
            TodoItem(content="任务2", status=TodoStatus.IN_PROGRESS),
            TodoItem(content="任务3", status=TodoStatus.COMPLETED),
            TodoItem(content="任务4", status=TodoStatus.COMPLETED),
        ]
        mgr.update_todos(todos)

        summary = mgr.get_progress_summary()
        assert "2/4 完成" in summary
        assert "1 进行中" in summary

    def test_clear(self):
        from agent.todo import TodoManager, TodoItem, TodoStatus
        mgr = TodoManager()
        mgr.update_todos([TodoItem(content="任务", status=TodoStatus.PENDING)])

        mgr.clear()
        assert not mgr.has_todos()

    def test_get_todos_returns_copy(self):
        """确保 get_todos 返回副本，修改不影响内部状态"""
        from agent.todo import TodoManager, TodoItem, TodoStatus
        mgr = TodoManager()
        mgr.update_todos([TodoItem(content="任务", status=TodoStatus.PENDING)])

        todos = mgr.get_todos()
        todos.clear()

        assert mgr.has_todos()  # 内部状态未受影响


class TestTodoWriteTool:
    """TodoWriteTool 工具测试"""

    def _setup_todo_manager(self):
        """设置全局 TodoManager"""
        from agent.todo import TodoManager
        from tools.todo_ops import set_todo_manager

        mgr = TodoManager()
        set_todo_manager(mgr)
        return mgr

    @pytest.mark.asyncio
    async def test_write_todos(self):
        mgr = self._setup_todo_manager()

        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()

        todos_input = [
            {"content": "任务1", "status": "pending"},
            {"content": "任务2", "status": "in_progress", "activeForm": "正在执行任务2"},
            {"content": "任务3", "status": "completed"},
        ]
        result = await tool.execute(todos=todos_input)

        assert result.success
        assert result.metadata["count"] == 3
        assert mgr.has_todos()
        assert len(mgr.get_todos()) == 3

    @pytest.mark.asyncio
    async def test_write_empty_todos(self):
        mgr = self._setup_todo_manager()
        mgr.update_todos([])

        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()

        result = await tool.execute(todos=[])
        assert result.success
        assert "清空" in result.output

    @pytest.mark.asyncio
    async def test_invalid_status(self):
        self._setup_todo_manager()

        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()

        result = await tool.execute(todos=[{"content": "任务", "status": "invalid"}])
        assert not result.success
        assert "无效的 status" in result.error

    @pytest.mark.asyncio
    async def test_empty_content(self):
        self._setup_todo_manager()

        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()

        result = await tool.execute(todos=[{"content": "", "status": "pending"}])
        assert not result.success
        assert "content 不能为空" in result.error

    @pytest.mark.asyncio
    async def test_no_manager_initialized(self):
        """未初始化 TodoManager 时应报错"""
        from tools.todo_ops import set_todo_manager
        set_todo_manager(None)

        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()

        result = await tool.execute(todos=[{"content": "任务", "status": "pending"}])
        assert not result.success
        assert "未初始化" in result.error

    @pytest.mark.asyncio
    async def test_schema(self):
        from tools.todo_ops import TodoWriteTool
        tool = TodoWriteTool()
        schema = tool.to_openai_schema()

        assert schema["function"]["name"] == "todo_write"
        assert "todos" in schema["function"]["parameters"]["properties"]
        assert "todos" in schema["function"]["parameters"]["required"]
