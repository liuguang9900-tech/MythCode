"""
基础测试 — 验证核心模块可正常导入和初始化。
"""

import os

import pytest
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))


def _reset_singletons(tmp_path):
    """重置所有模块级单例，确保测试隔离"""
    import config
    import tools.sandbox as sandbox_mod

    config._config = None
    sandbox_mod._sandbox = None

    from config import init_config
    init_config()
    cfg = config.get_config()
    cfg.safety.project_root = str(tmp_path)
    return cfg


class TestConfig:
    """配置模块测试"""

    def test_load_config(self):
        from config import load_config
        config = load_config()
        assert config.model.provider == "openai"
        assert config.agent.max_iterations == 30
        assert config.safety.require_approval is True

    def test_env_var_resolution(self):
        import os
        os.environ["TEST_VAR"] = "test_value"
        from config import _resolve_env_var
        result = _resolve_env_var("prefix_${TEST_VAR}_suffix")
        assert result == "prefix_test_value_suffix"


class TestToolRegistry:
    """工具注册中心测试"""

    def test_register_and_get(self):
        from tools.registry import ToolRegistry
        from tools.base import BaseTool, ToolResult

        registry = ToolRegistry()
        registry._tools.clear()

        class MockTool(BaseTool):
            name = "mock_tool"
            description = "A mock tool"
            parameters = {
                "arg1": {"type": "string", "description": "test arg", "required": True},
            }

            async def execute(self, **kwargs):
                return ToolResult(success=True, output="mock result")

        tool = MockTool()
        registry.register(tool)

        assert registry.get("mock_tool") is tool
        assert len(registry.list_tools()) == 1

        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "mock_tool"

    def test_duplicate_register_raises(self):
        from tools.registry import ToolRegistry
        from tools.base import BaseTool, ToolResult

        registry = ToolRegistry()
        registry._tools.clear()

        class MockTool(BaseTool):
            name = "dup_tool"
            description = "test"
            parameters = {}
            async def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        registry.register(MockTool())
        with pytest.raises(ValueError, match="已注册"):
            registry.register(MockTool())


class TestSandbox:
    """沙箱安全测试"""

    def test_resolve_path_in_project(self, tmp_path):
        from tools.sandbox import Sandbox
        sandbox = Sandbox(project_root=str(tmp_path))

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        resolved = sandbox.resolve_path("test.txt")
        assert resolved == test_file

    def test_resolve_path_outside_project(self, tmp_path):
        from tools.sandbox import Sandbox
        sandbox = Sandbox(project_root=str(tmp_path))

        with pytest.raises(PermissionError, match="不在允许的目录"):
            sandbox.resolve_path("/etc/passwd")

    def test_dangerous_command_detection(self, tmp_path):
        from tools.sandbox import Sandbox
        sandbox = Sandbox(project_root=str(tmp_path))

        is_safe, reason = sandbox.check_command("rm -rf /")
        assert not is_safe
        assert "危险" in reason

    def test_allowed_command(self, tmp_path):
        from tools.sandbox import Sandbox
        sandbox = Sandbox(project_root=str(tmp_path))

        is_safe, _ = sandbox.check_command("ls -la")
        assert is_safe


class TestFileOps:
    """文件操作工具测试"""

    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        _reset_singletons(tmp_path)
        from tools.file_ops import ReadFileTool

        test_file = tmp_path / "hello.py"
        test_file.write_text("line1\nline2\nline3\n")

        tool = ReadFileTool()
        result = await tool.execute(file_path="hello.py")
        assert result.success
        assert "line1" in result.output
        assert "line2" in result.output

    @pytest.mark.asyncio
    async def test_read_file_with_range(self, tmp_path):
        _reset_singletons(tmp_path)
        from tools.file_ops import ReadFileTool

        test_file = tmp_path / "data.txt"
        test_file.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")

        tool = ReadFileTool()
        result = await tool.execute(file_path="data.txt", offset=3, limit=2)
        assert result.success
        assert result.metadata["shown_lines"] == 2

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        _reset_singletons(tmp_path)
        from tools.file_ops import WriteFileTool

        tool = WriteFileTool()
        result = await tool.execute(file_path="new_file.py", content="print('hello')")
        assert result.success
        assert (tmp_path / "new_file.py").read_text() == "print('hello')"

    @pytest.mark.asyncio
    async def test_edit_file(self, tmp_path):
        _reset_singletons(tmp_path)
        from tools.file_ops import EditFileTool

        test_file = tmp_path / "edit_me.py"
        test_file.write_text("old_value = 1\nkeep_this = 2\n")

        tool = EditFileTool()
        result = await tool.execute(
            file_path="edit_me.py",
            old_string="old_value = 1",
            new_string="new_value = 42",
        )
        assert result.success
        content = test_file.read_text()
        assert "new_value = 42" in content
        assert "old_value = 1" not in content


class TestDirectoryOps:
    """目录操作工具测试"""

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        _reset_singletons(tmp_path)
        from tools.directory_ops import ListDirectoryTool

        # 创建测试目录结构
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("")
        (tmp_path / "tests").mkdir()
        (tmp_path / "README.md").write_text("")

        tool = ListDirectoryTool()
        result = await tool.execute(path=".", depth=2)
        assert result.success
        assert "src" in result.output
        assert "main.py" in result.output


class TestMemory:
    """对话记忆测试"""

    def test_add_and_retrieve(self):
        from agent.memory import ConversationMemory
        memory = ConversationMemory()
        memory.add_message("user", "hello")
        memory.add_message("assistant", "hi there")

        msgs = memory.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["content"] == "hello"

    def test_clear(self):
        from agent.memory import ConversationMemory
        memory = ConversationMemory()
        memory.add_message("user", "test")
        memory.clear()
        assert len(memory.get_messages()) == 0


class TestContext:
    """上下文管理器测试"""

    def test_build_system_prompt(self, tmp_path):
        import config
        config._config = None
        from config import init_config
        init_config()
        cfg = config.get_config()
        cfg.safety.project_root = str(tmp_path)

        from agent.memory import ConversationMemory
        from agent.context import ContextManager

        memory = ConversationMemory()
        ctx = ContextManager(memory, str(tmp_path))
        prompt = ctx.build_system_prompt()
        assert "自主 AI 编程智能体" in prompt
        assert str(tmp_path) in prompt


class TestTokenCounter:
    """Token 计数测试"""

    def test_count_text(self):
        from llm.token_counter import TokenCounter
        counter = TokenCounter("gpt-4o")
        count = counter.count("Hello, world!")
        assert count > 0

    def test_count_messages(self):
        from llm.token_counter import TokenCounter
        counter = TokenCounter("gpt-4o")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]
        count = counter.count_messages(messages)
        assert count > 0


class TestPathUtils:
    """路径工具测试"""

    def test_normalize_path(self):
        from utils.path_utils import normalize_path
        p = normalize_path("~/Documents")
        assert p.is_absolute()

    def test_is_subpath(self, tmp_path):
        from utils.path_utils import is_subpath
        child = tmp_path / "sub" / "file.txt"
        assert is_subpath(str(child), str(tmp_path))
        assert not is_subpath("/etc", str(tmp_path))


class TestAgentIgnore:
    """.agentignore 解析器测试"""

    def test_default_ignore_patterns(self, tmp_path):
        """测试默认忽略模式"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.source == "default"

        # 常见忽略目录
        assert mgr.is_ignored(tmp_path / ".git" / "config", tmp_path)
        assert mgr.is_ignored(tmp_path / "node_modules" / "pkg", tmp_path)
        assert mgr.is_ignored(tmp_path / "__pycache__" / "module.pyc", tmp_path)
        assert mgr.is_ignored(tmp_path / ".venv" / "bin" / "python", tmp_path)
        assert mgr.is_ignored(tmp_path / "dist" / "app.js", tmp_path)

        # 常见忽略文件
        assert mgr.is_ignored(tmp_path / "test.pyc", tmp_path)
        assert mgr.is_ignored(tmp_path / ".DS_Store", tmp_path)

        # 不应忽略的普通文件
        assert not mgr.is_ignored(tmp_path / "src" / "main.py", tmp_path)
        assert not mgr.is_ignored(tmp_path / "README.md", tmp_path)

    def test_agentignore_file(self, tmp_path):
        """测试 .agentignore 文件加载"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        # 创建 .agentignore 文件
        agentignore = tmp_path / ".agentignore"
        agentignore.write_text("# Custom ignores\nlogs/\n*.log\nbuild/\n")

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.source == "agentignore"

        # 自定义规则生效
        assert mgr.is_ignored(tmp_path / "logs" / "app.log", tmp_path)
        assert mgr.is_ignored(tmp_path / "error.log", tmp_path)
        assert mgr.is_ignored(tmp_path / "build" / "output", tmp_path)

        # 不在规则中的不应忽略
        assert not mgr.is_ignored(tmp_path / "src" / "main.py", tmp_path)

    def test_agentignore_priority_over_gitignore(self, tmp_path):
        """.agentignore 优先级高于 .gitignore"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        # 同时创建两个文件
        (tmp_path / ".gitignore").write_text("dist/\n")
        (tmp_path / ".agentignore").write_text("logs/\n")

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=True)
        # .agentignore 优先
        assert mgr.source == "agentignore"
        assert mgr.is_ignored(tmp_path / "logs" / "app.log", tmp_path)
        # .gitignore 的规则不应生效（因为被 .agentignore 覆盖）
        assert not mgr.is_ignored(tmp_path / "dist" / "app.js", tmp_path)

    def test_fallback_to_gitignore(self, tmp_path):
        """测试回退到 .gitignore"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        # 只创建 .gitignore
        (tmp_path / ".gitignore").write_text("dist/\n*.log\n")

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=True)
        assert mgr.source == "gitignore"

        assert mgr.is_ignored(tmp_path / "dist" / "app.js", tmp_path)
        assert mgr.is_ignored(tmp_path / "error.log", tmp_path)
        assert not mgr.is_ignored(tmp_path / "src" / "main.py", tmp_path)

    def test_respect_gitignore_disabled(self, tmp_path):
        """测试禁用 gitignore 回退"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        # 创建 .gitignore 但禁用回退
        (tmp_path / ".gitignore").write_text("dist/\n")

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        # 没有 .agentignore，也没有 gitignore 回退，使用默认
        assert mgr.source == "default"

    def test_should_ignore_relative_path(self, tmp_path):
        """测试 should_ignore 方法"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.should_ignore("node_modules/pkg/index.js")
        assert mgr.should_ignore("__pycache__/module.pyc")
        assert not mgr.should_ignore("src/main.py")

    def test_get_ignore_file_path(self, tmp_path):
        """测试获取忽略文件路径"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        # 默认模式：无文件
        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.get_ignore_file_path() is None

        # .agentignore 模式
        reset_ignore_manager()
        (tmp_path / ".agentignore").write_text("logs/\n")
        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.get_ignore_file_path() == (tmp_path / ".agentignore")

        # .gitignore 模式
        reset_ignore_manager()
        (tmp_path / ".agentignore").unlink()
        (tmp_path / ".gitignore").write_text("dist/\n")
        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=True)
        assert mgr.get_ignore_file_path() == (tmp_path / ".gitignore")

    def test_comment_and_empty_lines(self, tmp_path):
        """测试注释和空行被正确跳过"""
        from utils.agentignore import IgnoreSpecManager, reset_ignore_manager
        reset_ignore_manager()

        (tmp_path / ".agentignore").write_text(
            "# This is a comment\n\nlogs/\n\n# Another comment\n*.tmp\n\n"
        )

        mgr = IgnoreSpecManager(str(tmp_path), respect_gitignore=False)
        assert mgr.is_ignored(tmp_path / "logs" / "app.log", tmp_path)
        assert mgr.is_ignored(tmp_path / "test.tmp", tmp_path)
        assert not mgr.is_ignored(tmp_path / "src" / "main.py", tmp_path)


class TestAutoMemory:
    """自动记忆测试"""

    def test_add_and_get_all(self, tmp_path):
        from agent.auto_memory import AutoMemoryManager
        mgr = AutoMemoryManager(str(tmp_path))

        mgr.add("测试记忆", "这是一条测试记忆内容", tags=["test"])
        mgr.add("另一条记忆", "更多内容")

        memories = mgr.get_all()
        assert len(memories) == 2
        assert memories[0]["title"] == "另一条记忆"  # 倒序
        assert memories[1]["title"] == "测试记忆"

    def test_search(self, tmp_path):
        from agent.auto_memory import AutoMemoryManager
        mgr = AutoMemoryManager(str(tmp_path))

        mgr.add("Python 项目", "使用 Python 3.12", tags=["python", "setup"])
        mgr.add("部署配置", "Docker 部署到 AWS", tags=["docker", "aws"])

        results = mgr.search("python")
        assert len(results) == 1
        assert results[0]["title"] == "Python 项目"

        results = mgr.search("docker")
        assert len(results) == 1
        assert results[0]["title"] == "部署配置"

    def test_delete(self, tmp_path):
        from agent.auto_memory import AutoMemoryManager
        mgr = AutoMemoryManager(str(tmp_path))

        mem_id = mgr.add("待删除", "内容")
        assert len(mgr.get_all()) == 1

        assert mgr.delete(mem_id) is True
        assert len(mgr.get_all()) == 0

        assert mgr.delete("nonexistent") is False

    def test_get_context_for_prompt(self, tmp_path):
        from agent.auto_memory import AutoMemoryManager
        mgr = AutoMemoryManager(str(tmp_path))

        mgr.add("重要信息", "项目使用 FastAPI 框架")
        context = mgr.get_context_for_prompt()
        assert "自动记忆" in context
        assert "FastAPI" in context

    def test_clear(self, tmp_path):
        from agent.auto_memory import AutoMemoryManager
        mgr = AutoMemoryManager(str(tmp_path))

        mgr.add("记忆1", "内容1")
        mgr.add("记忆2", "内容2")
        assert len(mgr.get_all()) == 2

        mgr.clear()
        assert len(mgr.get_all()) == 0


class TestRules:
    """规则引擎测试"""

    def test_load_rules(self, tmp_path):
        from agent.rules import RulesManager

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        (rules_dir / "coding-style.md").write_text(
            "---\npaths:\n  - \"src/**/*.py\"\n---\n# 编码规范\n使用 4 空格缩进\n"
        )

        mgr = RulesManager(str(tmp_path))
        rules = mgr.load()
        assert len(rules) == 1
        assert rules[0]["paths"] == ["src/**/*.py"]
        assert "4 空格缩进" in rules[0]["content"]

    def test_global_rule_no_paths(self, tmp_path):
        from agent.rules import RulesManager

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        (rules_dir / "global.md").write_text("# 全局规则\n始终使用类型注解\n")

        mgr = RulesManager(str(tmp_path))
        rules = mgr.load()
        assert len(rules) == 1
        assert rules[0]["paths"] == []

    def test_get_rules_for_path(self, tmp_path):
        from agent.rules import RulesManager

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        (rules_dir / "python.md").write_text(
            "---\npaths:\n  - \"src/**/*.py\"\n---\n# Python 规则\n"
        )
        (rules_dir / "global.md").write_text("# 全局规则\n")

        mgr = RulesManager(str(tmp_path))
        matched = mgr.get_rules_for_path("src/main.py")
        assert len(matched) == 2  # 全局 + Python

        matched = mgr.get_rules_for_path("README.md")
        assert len(matched) == 1  # 仅全局

    def test_get_context_for_prompt(self, tmp_path):
        from agent.rules import RulesManager

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        (rules_dir / "style.md").write_text(
            "---\npaths:\n  - \"*.py\"\n---\n# 代码风格\n使用 Black 格式化\n"
        )

        mgr = RulesManager(str(tmp_path))
        context = mgr.get_context_for_prompt("app.py")
        assert "项目规则" in context
        assert "Black" in context

    def test_empty_rules_dir(self, tmp_path):
        from agent.rules import RulesManager
        mgr = RulesManager(str(tmp_path))
        rules = mgr.load()
        assert rules == []


class TestSettings:
    """多作用域设置测试"""

    def test_load_user_settings(self, tmp_path, monkeypatch):
        from config.settings import SettingsManager

        user_dir = tmp_path / "home" / ".mythcoder"
        user_dir.mkdir(parents=True)
        (user_dir / "settings.json").write_text(
            '{"model": {"temperature": 0.5}, "editor": "vim"}'
        )

        monkeypatch.setattr("config.settings.Path.home", lambda: tmp_path / "home")

        mgr = SettingsManager(str(tmp_path / "project"))
        settings = mgr.load()
        assert settings["model"]["temperature"] == 0.5
        assert settings["editor"] == "vim"

    def test_priority_local_over_project_over_user(self, tmp_path, monkeypatch):
        from config.settings import SettingsManager

        # User settings
        user_dir = tmp_path / "home" / ".mythcoder"
        user_dir.mkdir(parents=True)
        (user_dir / "settings.json").write_text('{"theme": "dark", "model": {"temperature": 0.5}}')

        # Project settings
        proj_dir = tmp_path / "project" / ".mythcoder"
        proj_dir.mkdir(parents=True)
        (proj_dir / "settings.json").write_text('{"theme": "light", "model": {"name": "gpt-4"}}')

        # Local settings
        (proj_dir / "settings.local.json").write_text('{"model": {"temperature": 0.1}}')

        monkeypatch.setattr("config.settings.Path.home", lambda: tmp_path / "home")

        mgr = SettingsManager(str(tmp_path / "project"))
        settings = mgr.load()

        # Local > Project > User
        assert settings["theme"] == "light"  # Project overrides User
        assert settings["model"]["name"] == "gpt-4"  # Project adds
        assert settings["model"]["temperature"] == 0.1  # Local overrides both

    def test_get_with_dot_key(self, tmp_path, monkeypatch):
        from config.settings import SettingsManager

        user_dir = tmp_path / "home" / ".mythcoder"
        user_dir.mkdir(parents=True)
        (user_dir / "settings.json").write_text(
            '{"model": {"name": "gpt-4o", "temperature": 0.7}}'
        )

        monkeypatch.setattr("config.settings.Path.home", lambda: tmp_path / "home")

        mgr = SettingsManager(str(tmp_path / "project"))
        assert mgr.get("model.name") == "gpt-4o"
        assert mgr.get("model.temperature") == 0.7
        assert mgr.get("nonexistent", "default") == "default"

    def test_deep_merge_arrays(self, tmp_path, monkeypatch):
        from config.settings import SettingsManager

        user_dir = tmp_path / "home" / ".mythcoder"
        user_dir.mkdir(parents=True)
        (user_dir / "settings.json").write_text(
            '{"allowed_commands": ["ls", "cat"]}'
        )

        proj_dir = tmp_path / "project" / ".mythcoder"
        proj_dir.mkdir(parents=True)
        (proj_dir / "settings.json").write_text(
            '{"allowed_commands": ["git", "cat"]}'
        )

        monkeypatch.setattr("config.settings.Path.home", lambda: tmp_path / "home")

        mgr = SettingsManager(str(tmp_path / "project"))
        settings = mgr.load()
        # 数组合并去重
        assert "ls" in settings["allowed_commands"]
        assert "cat" in settings["allowed_commands"]
        assert "git" in settings["allowed_commands"]
        assert len(settings["allowed_commands"]) == 3

    def test_save_and_update(self, tmp_path, monkeypatch):
        from config.settings import SettingsManager

        monkeypatch.setattr("config.settings.Path.home", lambda: tmp_path / "home")

        mgr = SettingsManager(str(tmp_path / "project"))
        mgr.save_user({"theme": "dark"})

        settings = mgr.load()
        assert settings["theme"] == "dark"

        mgr.update_user("model.temperature", 0.3)
        settings = mgr.load()
        assert settings["model"]["temperature"] == 0.3


class TestHooks:
    """钩子系统测试"""

    def test_init_and_disable(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        assert mgr._enabled is True

        mgr.disable()
        assert mgr._enabled is False

        mgr.enable()
        assert mgr._enabled is True

    def test_list_hooks_empty(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        assert mgr.list_hooks() == []

    def test_list_hooks(self, tmp_path):
        from agent.hooks import HookManager

        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "pre_tool_use.py").write_text("")
        (hooks_dir / "post_tool_use.sh").write_text("")
        (hooks_dir / "notification.py").write_text("")

        mgr = HookManager(str(tmp_path))
        hooks = mgr.list_hooks()
        assert "notification" in hooks
        assert "post_tool_use" in hooks
        assert "pre_tool_use" in hooks

    @pytest.mark.asyncio
    async def test_pre_tool_use_no_script(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        allowed, msg = await mgr.on_pre_tool_use("write_file", {"path": "test.py"})
        assert allowed is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_post_tool_use_no_script(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        # Should not raise
        await mgr.on_post_tool_use("write_file", {"path": "test.py"}, {"success": True})

    @pytest.mark.asyncio
    async def test_notification_no_script(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        # Should not raise
        await mgr.on_notification("session_start", {"workspace": "/tmp"})

    @pytest.mark.asyncio
    async def test_user_prompt_submit_no_script(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        result = await mgr.on_user_prompt_submit("hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_hooks_disabled_returns_none(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        mgr.disable()

        allowed, msg = await mgr.on_pre_tool_use("write_file", {})
        assert allowed is True
        assert msg is None

        result = await mgr.on_user_prompt_submit("hello")
        assert result is None

    def test_find_script_prefers_py(self, tmp_path):
        from agent.hooks import HookManager

        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "pre_tool_use.sh").write_text("#!/bin/bash\necho '{}'")
        (hooks_dir / "pre_tool_use.py").write_text("print('{}')")

        mgr = HookManager(str(tmp_path))
        script = mgr._find_script("pre_tool_use")
        assert script is not None
        assert script.suffix == ".py"

    def test_find_script_fallback_sh(self, tmp_path):
        from agent.hooks import HookManager

        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "notification.sh").write_text("#!/bin/bash\necho '{}'")
        os.chmod(hooks_dir / "notification.sh", 0o755)  # 确保可执行

        mgr = HookManager(str(tmp_path))
        script = mgr._find_script("notification")
        assert script is not None
        assert script.suffix == ".sh"

    def test_find_script_not_found(self, tmp_path):
        from agent.hooks import HookManager
        mgr = HookManager(str(tmp_path))
        assert mgr._find_script("nonexistent") is None
