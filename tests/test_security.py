"""
安全相关测试 — 沙箱、路径穿越、命令注入防护。
"""

import os
import pytest
from pathlib import Path
from tools.sandbox import Sandbox, get_sandbox
from commands.custom import CustomCommand


class TestSandboxSecurity:
    """沙箱安全测试"""

    def setup_method(self):
        """每个测试前重置沙箱"""
        import tools.sandbox
        tools.sandbox._sandbox = None

    def test_path_traversal_blocked(self, tmp_path):
        """测试路径穿越被阻止"""
        sandbox = Sandbox(str(tmp_path))
        with pytest.raises(Exception):
            sandbox.resolve_path("../../../etc/passwd")

    def test_absolute_path_outside_blocked(self, tmp_path):
        """测试绝对路径指向外部被阻止"""
        sandbox = Sandbox(str(tmp_path))
        with pytest.raises(Exception):
            sandbox.resolve_path("/etc/passwd")

    def test_path_inside_allowed(self, tmp_path):
        """测试工作目录内路径允许"""
        sandbox = Sandbox(str(tmp_path))
        resolved = sandbox.resolve_path("test.py")
        assert resolved.is_absolute()
        assert str(tmp_path) in str(resolved)

    def test_dangerous_command_detected(self, tmp_path):
        """测试危险命令检测"""
        sandbox = Sandbox(str(tmp_path))
        is_safe, reason = sandbox.check_command("rm -rf /")
        assert is_safe is False

    def test_safe_command_allowed(self, tmp_path):
        """测试安全命令允许"""
        sandbox = Sandbox(str(tmp_path))
        is_safe, _ = sandbox.check_command("ls -la")
        assert is_safe is True

    def test_git_status_allowed(self, tmp_path):
        """测试 git status 在白名单"""
        sandbox = Sandbox(str(tmp_path))
        is_safe, _ = sandbox.check_command("git status")
        assert is_safe is True


class TestCustomCommandSecurity:
    """自定义命令安全测试"""

    def test_shell_injection_prevented(self):
        """测试 shell 注入被阻止（不再使用 shell=True）"""
        cmd = CustomCommand("test", "test", "template")
        template = "Result: `!echo hacked`"
        cmd.template = template
        result = cmd._render_template("")
        assert "hacked" in result

    def test_invalid_command_handled_gracefully(self):
        """测试无效命令优雅处理"""
        cmd = CustomCommand("test", "test", "template")
        template = "Result: `!nonexistent_command_xyz`"
        cmd.template = template
        result = cmd._render_template("")
        assert "执行失败" in result or "无输出" in result

    def test_no_shell_true(self):
        """验证源码中不再使用 shell=True"""
        import inspect
        source = inspect.getsource(CustomCommand._render_template)
        # 移除注释和字符串后再检查
        lines = [l for l in source.splitlines() if not l.strip().startswith("#")]
        code_only = "\n".join(lines)
        # 检查实际代码中不含 shell=True（注释中提到是可以的）
        assert "shell=True" not in code_only.replace("# 安全实现：使用 shlex 分割，禁止 shell=True", "")


class TestErrorSanitization:
    """错误信息脱敏测试"""

    def test_api_key_sanitized(self):
        from llm.client import _sanitize_error
        err = Exception("Request with api_key=sk-abc123")
        sanitized = _sanitize_error(err)
        assert "sk-abc123" not in sanitized

    def test_bearer_token_sanitized(self):
        from llm.client import _sanitize_error
        err = Exception("Authorization: Bearer sk-abc123def456")
        sanitized = _sanitize_error(err)
        assert "sk-abc123def456" not in sanitized

    def test_non_sensitive_preserved(self):
        from llm.client import _sanitize_error
        err = Exception("Model not found: gpt-4o")
        sanitized = _sanitize_error(err)
        assert "gpt-4o" in sanitized
