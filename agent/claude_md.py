"""
CLAUDE.md 加载器 — 加载项目上下文文件并注入到 system prompt。

加载顺序（后加载的追加到 system prompt）：
  1. ./CLAUDE.md          — 项目根目录（提交到 git）
  2. ./.claude/CLAUDE.md  — .claude 目录
  3. ./CLAUDE.local.md    — 本地覆盖（gitignore，不提交）
  4. ~/.mythcoder/CLAUDE.md — 全局用户配置
"""

import os
from pathlib import Path
from typing import Optional


class CLAUDEMdLoader:
    """CLAUDE.md 文件加载器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self._cache: Optional[str] = None
        self._cache_mtime: dict[str, float] = {}

    def load(self, force_reload: bool = False) -> Optional[str]:
        """
        加载所有 CLAUDE.md 文件，按优先级顺序拼接。

        Returns:
            拼接后的 CLAUDE.md 内容，如果没有文件则返回 None
        """
        if not force_reload and self._cache is not None:
            if not self._has_changed():
                return self._cache

        paths = [
            self.workspace_root / "CLAUDE.md",
            self.workspace_root / ".claude" / "CLAUDE.md",
            self.workspace_root / "CLAUDE.local.md",
            Path.home() / ".mythcoder" / "CLAUDE.md",
        ]

        sections = []
        for path in paths:
            content = self._read_file(path)
            if content:
                label = self._get_label(path)
                sections.append(f"<!-- {label} -->\n{content}")

        if sections:
            self._cache = "\n\n".join(sections)
            return self._cache

        self._cache = None
        return None

    def _read_file(self, path: Path) -> Optional[str]:
        """读取文件内容，记录 mtime 用于缓存失效"""
        try:
            if not path.exists():
                return None
            content = path.read_text(encoding="utf-8").strip()
            if content:
                self._cache_mtime[str(path)] = path.stat().st_mtime
                return content
        except (OSError, UnicodeDecodeError):
            pass
        return None

    def _has_changed(self) -> bool:
        """检查已缓存的文件是否有修改"""
        for path_str, cached_mtime in self._cache_mtime.items():
            path = Path(path_str)
            try:
                if path.exists() and path.stat().st_mtime > cached_mtime:
                    return True
            except OSError:
                return True
        return False

    def _get_label(self, path: Path) -> str:
        """生成文件来源标签"""
        home = Path.home()
        try:
            rel = path.relative_to(self.workspace_root)
            return f"来源: {rel}"
        except ValueError:
            try:
                rel = path.relative_to(home)
                return f"来源: ~/{rel}"
            except ValueError:
                return f"来源: {path}"

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache = None
        self._cache_mtime.clear()
