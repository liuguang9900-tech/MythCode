"""
上下文管理器测试 — 测试 agent/context.py 的系统提示词增强
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_config(tmp_path):
    """初始化配置"""
    import config
    config._config = None
    from config import init_config
    init_config()
    cfg = config.get_config()
    cfg.safety.project_root = str(tmp_path)
    return cfg


class TestSystemPrompt:
    """系统提示词内容测试"""

    def test_prompt_contains_identity(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        assert "自主 AI 编程智能体" in prompt
        assert "工作原则" in prompt

    def test_prompt_contains_tool_guidelines(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        # 工具使用规范
        assert "工具使用" in prompt
        assert "glob" in prompt
        assert "search_code" in prompt
        assert "edit_file" in prompt
        assert "write_file" in prompt
        assert "read_file" in prompt
        assert "todo_write" in prompt

    def test_prompt_contains_code_style(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        assert "代码风格" in prompt
        assert "类型注解" in prompt

    def test_prompt_contains_git_workflow(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        assert "Git" in prompt
        assert "feat" in prompt
        assert "fix" in prompt

    def test_prompt_contains_environment(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        assert "工作目录" in prompt
        assert str(tmp_path) in prompt
        assert "操作系统" in prompt
        assert "当前时间" in prompt

    def test_prompt_contains_output_rules(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        assert "输出" in prompt
        assert "Markdown" in prompt
        assert "path:line" in prompt

    def test_prompt_contains_error_handling(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()

        # 精简版提示词中工作原则包含安全相关内容
        assert "工作原则" in prompt
        assert "安全" in prompt


class TestTodoInjection:
    """TODO 状态注入测试"""

    def test_no_todo_injection(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager
        from agent.todo import TodoManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        todo_mgr = TodoManager()
        ctx.set_todo(todo_mgr)

        prompt = ctx.build_system_prompt()
        assert "当前任务清单" not in prompt

    def test_todo_injection(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager
        from agent.todo import TodoManager, TodoItem, TodoStatus

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        todo_mgr = TodoManager()
        todo_mgr.update_todos([
            TodoItem(content="重构模块", status=TodoStatus.IN_PROGRESS, active_form="正在重构"),
            TodoItem(content="编写测试", status=TodoStatus.PENDING),
        ])
        ctx.set_todo(todo_mgr)

        prompt = ctx.build_system_prompt()
        assert "当前任务清单" in prompt
        assert "正在重构" in prompt
        assert "编写测试" in prompt


class TestBuildMessages:
    """build_messages 方法测试"""

    def test_build_messages_structure(self, tmp_path):
        _setup_config(tmp_path)
        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        messages = ctx.build_messages("帮我查看代码")

        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "帮我查看代码"
