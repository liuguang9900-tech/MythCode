"""
Diff 工具测试 — 测试 utils/diff_utils.py
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGenerateUnifiedDiff:
    """unified diff 生成测试"""

    def test_no_changes(self):
        from utils.diff_utils import generate_unified_diff
        content = "line1\nline2\nline3\n"
        diff = generate_unified_diff(content, content, "test.py")
        assert diff == ""

    def test_add_line(self):
        from utils.diff_utils import generate_unified_diff
        original = "line1\nline2\n"
        new = "line1\nline2\nline3\n"
        diff = generate_unified_diff(original, new, "test.py")

        assert "+line3" in diff
        assert "test.py" in diff

    def test_remove_line(self):
        from utils.diff_utils import generate_unified_diff
        original = "line1\nline2\nline3\n"
        new = "line1\nline3\n"
        diff = generate_unified_diff(original, new, "test.py")

        assert "-line2" in diff

    def test_modify_line(self):
        from utils.diff_utils import generate_unified_diff
        original = "def foo():\n    pass\n"
        new = "def foo():\n    return 42\n"
        diff = generate_unified_diff(original, new, "test.py")

        assert "-    pass" in diff
        assert "+    return 42" in diff

    def test_new_file(self):
        from utils.diff_utils import generate_unified_diff
        diff = generate_unified_diff("", "new content\n", "new.py")

        assert "+new content" in diff
        assert "/dev/null" in diff  # 新文件的 fromfile

    def test_diff_header(self):
        from utils.diff_utils import generate_unified_diff
        diff = generate_unified_diff("a\n", "b\n", "src/main.py")

        assert "a/src/main.py" in diff
        assert "b/src/main.py" in diff


class TestCountDiffChanges:
    """diff 变更统计测试"""

    def test_count_added_removed(self):
        from utils.diff_utils import generate_unified_diff, count_diff_changes
        original = "line1\nline2\nline3\n"
        new = "line1\nmodified\nline3\nline4\n"
        diff = generate_unified_diff(original, new, "test.py")

        changes = count_diff_changes(diff)
        assert changes["added"] == 2  # modified + line4
        assert changes["removed"] == 1  # line2

    def test_count_empty_diff(self):
        from utils.diff_utils import count_diff_changes
        changes = count_diff_changes("")
        assert changes["added"] == 0
        assert changes["removed"] == 0

    def test_count_ignores_headers(self):
        """+++ 和 --- 头部行不应被计入"""
        from utils.diff_utils import generate_unified_diff, count_diff_changes
        diff = generate_unified_diff("a\n", "b\n", "test.py")
        changes = count_diff_changes(diff)

        # 只有一行变更：a→b
        assert changes["added"] == 1
        assert changes["removed"] == 1


class TestReadFileSafe:
    """安全文件读取测试"""

    def test_read_existing_file(self, tmp_path):
        from utils.diff_utils import read_file_safe
        f = tmp_path / "test.txt"
        f.write_text("hello world")

        assert read_file_safe(f) == "hello world"

    def test_read_nonexistent_file(self, tmp_path):
        from utils.diff_utils import read_file_safe
        assert read_file_safe(tmp_path / "nonexistent.txt") == ""

    def test_read_binary_file(self, tmp_path):
        from utils.diff_utils import read_file_safe
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\x82")

        assert read_file_safe(f) == ""


class TestFormatDiffForDisplay:
    """diff 格式化显示测试"""

    def test_empty_diff(self):
        from utils.diff_utils import format_diff_for_display
        result = format_diff_for_display("")
        assert "无变更" in result

    def test_format_with_colors(self):
        from utils.diff_utils import generate_unified_diff, format_diff_for_display
        diff = generate_unified_diff("a\n", "b\n", "test.py")
        formatted = format_diff_for_display(diff)

        assert "[green]" in formatted  # 添加行绿色
        assert "[red]" in formatted  # 删除行红色
        assert "[cyan]" in formatted  # @@ 行青色
