"""
glob 工具测试 — 测试 utils/glob_utils.py 和 tools/glob_ops.py
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGlobToRegex:
    """glob 模式转正则测试"""

    def test_simple_match(self):
        from utils.glob_utils import match_glob
        assert match_glob("foo.py", "foo.py")
        assert not match_glob("foo.py", "bar.py")

    def test_star_match(self):
        from utils.glob_utils import match_glob
        assert match_glob("foo.py", "*.py")
        assert match_glob("bar.py", "*.py")
        assert not match_glob("foo.txt", "*.py")

    def test_double_star_recursive(self):
        from utils.glob_utils import match_glob
        assert match_glob("src/main.py", "**/*.py")
        assert match_glob("src/utils/helper.py", "**/*.py")
        assert match_glob("main.py", "**/*.py")

    def test_double_star_middle(self):
        from utils.glob_utils import match_glob
        assert match_glob("src/foo/bar.py", "src/**/*.py")
        assert match_glob("src/bar.py", "src/**/*.py")

    def test_question_mark(self):
        from utils.glob_utils import match_glob
        # ? 匹配单个字符（不含路径分隔符）
        assert match_glob("foo1.py", "foo?.py")
        assert match_glob("fooX.py", "foo?.py")
        assert not match_glob("foo.py", "foo?.py")  # ? 要求恰好一个字符
        assert not match_glob("foo12.py", "foo?.py")  # ? 只匹配一个字符

    def test_path_separator_not_matched_by_star(self):
        from utils.glob_utils import match_glob
        # * 不匹配路径分隔符
        assert not match_glob("src/main.py", "*.py")


class TestFindFiles:
    """find_files 函数测试"""

    def test_find_python_files(self, tmp_path):
        from utils.glob_utils import find_files

        # 创建测试文件结构
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "utils").mkdir()
        (tmp_path / "utils" / "helper.py").write_text("# helper")
        (tmp_path / "README.md").write_text("# readme")

        results = find_files(tmp_path, "**/*.py")
        assert "main.py" in results
        assert "utils/helper.py" in results
        assert "README.md" not in results

    def test_find_with_limit(self, tmp_path):
        from utils.glob_utils import find_files

        for i in range(10):
            (tmp_path / f"file_{i}.py").write_text(f"# file {i}")

        results = find_files(tmp_path, "*.py", limit=5)
        assert len(results) == 5

    def test_find_nonexistent_pattern(self, tmp_path):
        from utils.glob_utils import find_files

        (tmp_path / "foo.py").write_text("# foo")

        results = find_files(tmp_path, "*.txt")
        assert results == []

    def test_find_respects_ignore(self, tmp_path):
        from utils.glob_utils import find_files

        (tmp_path / "foo.py").write_text("# foo")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.js").write_text("// lib")

        # 模拟 ignore manager
        class MockIgnore:
            def is_ignored(self, path, root):
                return "node_modules" in str(path)

        results = find_files(tmp_path, "**/*", ignore_manager=MockIgnore())
        assert "foo.py" in results
        assert not any("node_modules" in r for r in results)


class TestGlobTool:
    """GlobTool 工具测试"""

    def _setup_sandbox(self, tmp_path):
        """设置沙箱"""
        import config
        import tools.sandbox as sandbox_mod

        config._config = None
        sandbox_mod._sandbox = None

        from config import init_config
        init_config()
        cfg = config.get_config()
        cfg.safety.project_root = str(tmp_path)
        return cfg

    @pytest.mark.asyncio
    async def test_glob_tool_basic(self, tmp_path):
        self._setup_sandbox(tmp_path)

        (tmp_path / "foo.py").write_text("# foo")
        (tmp_path / "bar.py").write_text("# bar")
        (tmp_path / "readme.md").write_text("# readme")

        from tools.glob_ops import GlobTool
        tool = GlobTool()
        result = await tool.execute(pattern="*.py")

        assert result.success
        assert result.metadata["count"] == 2
        assert "foo.py" in result.metadata["results"]
        assert "bar.py" in result.metadata["results"]

    @pytest.mark.asyncio
    async def test_glob_tool_recursive(self, tmp_path):
        self._setup_sandbox(tmp_path)

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helper.py").write_text("# helper")

        from tools.glob_ops import GlobTool
        tool = GlobTool()
        result = await tool.execute(pattern="src/**/*.py")

        assert result.success
        assert result.metadata["count"] == 2

    @pytest.mark.asyncio
    async def test_glob_tool_no_match(self, tmp_path):
        self._setup_sandbox(tmp_path)

        (tmp_path / "foo.py").write_text("# foo")

        from tools.glob_ops import GlobTool
        tool = GlobTool()
        result = await tool.execute(pattern="*.txt")

        assert result.success
        assert result.metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_glob_tool_nonexistent_dir(self, tmp_path):
        self._setup_sandbox(tmp_path)

        from tools.glob_ops import GlobTool
        tool = GlobTool()
        result = await tool.execute(pattern="*.py", path=str(tmp_path / "nonexistent"))

        assert not result.success
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_glob_tool_schema(self):
        from tools.glob_ops import GlobTool
        tool = GlobTool()
        schema = tool.to_openai_schema()

        assert schema["function"]["name"] == "glob"
        assert "pattern" in schema["function"]["parameters"]["properties"]
        assert "pattern" in schema["function"]["parameters"]["required"]
