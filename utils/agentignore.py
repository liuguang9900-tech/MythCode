"""
.agentignore 解析器 — 类似 .gitignore 的文件忽略规则。

优先级：
  1. 项目根目录的 .agentignore（如果存在）
  2. 回退到 .gitignore（如果 search_respect_gitignore 配置为 true）
  3. 如果都不存在，使用内置默认忽略列表

使用 pathspec 库解析 gitignore 格式的规则。
"""

import os
from pathlib import Path
from typing import Optional

import pathspec


# 内置默认忽略模式（当没有 .agentignore 和 .gitignore 时使用）
DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "node_modules/",
    ".venv/",
    "venv/",
    ".idea/",
    ".vscode/",
    "*.egg-info/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".agent_snapshots/",
    ".mythcoder/",
    "dist/",
    "build/",
    ".next/",
    "target/",
]


class IgnoreSpecManager:
    """管理 .agentignore / .gitignore 规则，提供路径过滤能力。"""

    def __init__(
        self,
        project_root: str = ".",
        respect_gitignore: bool = True,
    ):
        self.project_root = Path(project_root).resolve()
        self.respect_gitignore = respect_gitignore
        self._spec: Optional[pathspec.PathSpec] = None
        self._source: str = "default"  # "agentignore", "gitignore", "default"
        self._load()

    def _load(self) -> None:
        """加载忽略规则：.agentignore > .gitignore > 默认"""
        # 1. 尝试加载 .agentignore
        agentignore_path = self.project_root / ".agentignore"
        if agentignore_path.exists():
            patterns = self._read_patterns(agentignore_path)
            self._spec = pathspec.PathSpec.from_lines("gitignore", patterns)
            self._source = "agentignore"
            return

        # 2. 回退到 .gitignore
        if self.respect_gitignore:
            gitignore_path = self.project_root / ".gitignore"
            if gitignore_path.exists():
                patterns = self._read_patterns(gitignore_path)
                self._spec = pathspec.PathSpec.from_lines("gitignore", patterns)
                self._source = "gitignore"
                return

        # 3. 使用内置默认
        self._spec = pathspec.PathSpec.from_lines("gitignore", DEFAULT_IGNORE_PATTERNS)
        self._source = "default"

    @staticmethod
    def _read_patterns(filepath: Path) -> list[str]:
        """读取忽略文件中的模式行，跳过空行和注释"""
        patterns = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns

    def should_ignore(self, relative_path: str) -> bool:
        """检查相对路径是否应被忽略。"""
        if self._spec is None:
            return False
        return self._spec.match_file(relative_path)

    def is_ignored(self, entry: Path, root: Optional[Path] = None) -> bool:
        """
        检查文件系统条目是否应被忽略。

        Args:
            entry: 要检查的 Path 对象
            root: 项目根目录（默认使用 self.project_root）

        Returns:
            True 表示应忽略
        """
        root = root or self.project_root
        try:
            rel = entry.resolve().relative_to(root)
            return self.should_ignore(str(rel))
        except (ValueError, OSError):
            return False

    def get_ignore_file_path(self) -> Optional[Path]:
        """返回当前使用的忽略文件路径（用于传递给 ripgrep 等外部工具）。"""
        if self._source == "agentignore":
            return self.project_root / ".agentignore"
        elif self._source == "gitignore":
            return self.project_root / ".gitignore"
        return None

    @property
    def source(self) -> str:
        """返回当前使用的规则来源"""
        return self._source


# 全局单例
_ignore_manager: Optional[IgnoreSpecManager] = None


def get_ignore_manager(
    project_root: str = ".",
    respect_gitignore: bool = True,
) -> IgnoreSpecManager:
    """获取全局 IgnoreSpecManager 单例"""
    global _ignore_manager
    if _ignore_manager is None:
        _ignore_manager = IgnoreSpecManager(project_root, respect_gitignore)
    return _ignore_manager


def reset_ignore_manager() -> None:
    """重置全局单例（用于测试）"""
    global _ignore_manager
    _ignore_manager = None
