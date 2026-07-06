"""
规则引擎 — 加载 .claude/rules/*.md 文件，支持路径作用域。

规则文件格式：
  ---
  paths:
    - "src/**/*.py"
    - "tests/**"
  ---
  # 规则内容 (Markdown)

当操作的文件匹配 paths 时，对应规则自动注入 system prompt。
"""

import re
from pathlib import Path
from typing import Optional

import yaml


def _glob_to_regex(pattern: str) -> re.Pattern:
    """将 glob 模式转换为正则表达式，支持 ** 递归匹配。"""
    parts = []
    i = 0
    while i < len(pattern):
        if pattern[i:i+2] == "**":
            # ** 匹配零个或多个目录
            # 如果后面是 /，则 **/ 作为一个整体
            if i + 2 < len(pattern) and pattern[i+2] == "/":
                parts.append(r"(?:.+/)*")
                i += 3  # skip **/
            else:
                parts.append(r".*")
                i += 2
        elif pattern[i] == "*":
            parts.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append(r"[^/]")
            i += 1
        elif pattern[i] in ".^${}()[]|+\\":
            parts.append("\\" + pattern[i])
            i += 1
        else:
            parts.append(pattern[i])
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def _match_glob(file_path: str, pattern: str) -> bool:
    """检查文件路径是否匹配 glob 模式（支持 **）。"""
    return bool(_glob_to_regex(pattern).match(file_path))


class RulesManager:
    """规则管理器 — 加载和作用域匹配"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.rules_dir = self.workspace_root / ".claude" / "rules"
        self._rules: list[dict] = []       # [{"paths": [...], "content": "...", "file": "..."}]
        self._cache_mtimes: dict[str, float] = {}
        self._loaded = False

    def load(self, force_reload: bool = False) -> list[dict]:
        """
        加载所有规则文件。

        Returns:
            规则列表，每个规则包含 paths、content、file 字段
        """
        if self._loaded and not force_reload:
            if not self._has_changed():
                return self._rules

        self._rules = []
        self._cache_mtimes = {}

        if not self.rules_dir.exists():
            self._loaded = True
            return self._rules

        for md_file in sorted(self.rules_dir.glob("*.md")):
            rule = self._parse_rule_file(md_file)
            if rule:
                self._rules.append(rule)
                self._cache_mtimes[str(md_file)] = md_file.stat().st_mtime

        self._loaded = True
        return self._rules

    def get_rules_for_path(self, file_path: str) -> list[dict]:
        """
        获取适用于指定文件路径的所有规则。

        Args:
            file_path: 相对于工作区的文件路径

        Returns:
            匹配的规则列表
        """
        self.load()
        matched = []

        for rule in self._rules:
            paths = rule.get("paths", [])
            # 没有 paths 的规则始终生效（全局规则）
            if not paths:
                matched.append(rule)
                continue

            # 使用自定义 glob 匹配器支持 ** 递归匹配
            for pattern in paths:
                if _match_glob(file_path, pattern):
                    matched.append(rule)
                    break

        return matched

    def get_context_for_prompt(self, file_path: Optional[str] = None) -> str:
        """
        获取用于注入 system prompt 的规则上下文。

        Args:
            file_path: 可选，当前操作的文件路径。为 None 时返回所有全局规则。

        Returns:
            格式化的规则文本
        """
        if file_path:
            rules = self.get_rules_for_path(file_path)
        else:
            self.load()
            rules = [r for r in self._rules if not r.get("paths")]

        if not rules:
            return ""

        lines = ["## 项目规则 (Rules)", ""]
        for rule in rules:
            source = rule.get("file", "unknown")
            content = rule.get("content", "")
            lines.append(f"<!-- 规则来源: {source} -->")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)

    def get_all_context_for_prompt(self) -> str:
        """获取所有规则（全局 + 路径作用域）的上下文"""
        self.load()
        if not self._rules:
            return ""

        lines = ["## 项目规则 (Rules)", ""]
        for rule in self._rules:
            source = rule.get("file", "unknown")
            paths = rule.get("paths", [])
            content = rule.get("content", "")

            header = f"<!-- 规则来源: {source}"
            if paths:
                header += f" | 作用域: {', '.join(paths)}"
            header += " -->"
            lines.append(header)
            lines.append(content)
            lines.append("")
        return "\n".join(lines)

    def _parse_rule_file(self, filepath: Path) -> Optional[dict]:
        """解析单个规则文件（YAML frontmatter + Markdown 内容）"""
        try:
            text = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        # 解析 YAML frontmatter
        paths = []
        content = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    if isinstance(frontmatter, dict):
                        paths = frontmatter.get("paths", [])
                        if isinstance(paths, str):
                            paths = [paths]
                except yaml.YAMLError:
                    pass
                content = parts[2].strip()

        if not content:
            return None

        try:
            rel_path = filepath.relative_to(self.workspace_root)
        except ValueError:
            rel_path = filepath

        return {
            "paths": paths,
            "content": content,
            "file": str(rel_path),
        }

    def _has_changed(self) -> bool:
        """检查已缓存的文件是否有修改"""
        for path_str, cached_mtime in self._cache_mtimes.items():
            path = Path(path_str)
            try:
                if path.exists() and path.stat().st_mtime > cached_mtime:
                    return True
                if not path.exists():
                    return True
            except OSError:
                return True
        # 检查是否有新文件
        if self.rules_dir.exists():
            current_files = set(str(p) for p in self.rules_dir.glob("*.md"))
            cached_files = set(self._cache_mtimes.keys())
            if current_files != cached_files:
                return True
        return False

    def clear_cache(self) -> None:
        """清除缓存"""
        self._rules = []
        self._cache_mtimes = {}
        self._loaded = False
