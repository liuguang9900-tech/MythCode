"""
Skills 系统 — 可复用提示模板。
从 .claude/skills/ 和 ~/.mythcoder/skills/ 加载。
"""

import time
from pathlib import Path
from typing import Optional
import yaml
import fnmatch

from dataclasses import dataclass, field


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    content: str
    paths: list[str] = field(default_factory=list)  # 适用文件路径 glob
    auto_activate: bool = False
    tags: list[str] = field(default_factory=list)
    file_path: str = ""


class SkillManager:
    """技能管理器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self._skills: list[Skill] = []
        self._active_skills: set[str] = set()
        self._loaded = False

    def load_all(self, force_reload: bool = False) -> list[Skill]:
        """加载所有技能"""
        if self._loaded and not force_reload:
            return self._skills

        self._skills = []

        # 项目级技能
        project_dir = self.workspace_root / ".claude" / "skills"
        self._load_from_dir(project_dir)

        # 用户级技能
        user_dir = Path.home() / ".mythcoder" / "skills"
        self._load_from_dir(user_dir)

        self._loaded = True

        # 自动激活
        for skill in self._skills:
            if skill.auto_activate:
                self._active_skills.add(skill.name)

        return self._skills

    def _load_from_dir(self, dir_path: Path) -> None:
        """从目录加载技能"""
        if not dir_path.exists():
            return

        for md_file in sorted(dir_path.glob("*.md")):
            skill = self._parse_skill_file(md_file)
            if skill:
                self._skills.append(skill)

    def _parse_skill_file(self, path: Path) -> Optional[Skill]:
        """解析技能文件"""
        try:
            text = path.read_text(encoding="utf-8")

            name = path.stem
            description = ""
            paths = []
            auto_activate = False
            tags = []
            content = text

            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        if isinstance(frontmatter, dict):
                            name = frontmatter.get("name", name)
                            description = frontmatter.get("description", "")
                            paths = frontmatter.get("paths", []) or []
                            auto_activate = frontmatter.get("auto_activate", False)
                            tags = frontmatter.get("tags", []) or []
                    except yaml.YAMLError:
                        pass
                    content = parts[2].strip()

            return Skill(
                name=name,
                description=description,
                content=content,
                paths=paths,
                auto_activate=auto_activate,
                tags=tags,
                file_path=str(path),
            )
        except (OSError, UnicodeDecodeError):
            return None

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定技能"""
        self.load_all()
        for skill in self._skills:
            if skill.name == name:
                return skill
        return None

    def activate(self, name: str) -> bool:
        """激活技能"""
        skill = self.get_skill(name)
        if skill:
            self._active_skills.add(name)
            return True
        return False

    def deactivate(self, name: str) -> None:
        """停用技能"""
        self._active_skills.discard(name)

    def get_active_skills(self) -> list[Skill]:
        """获取已激活的技能"""
        self.load_all()
        return [s for s in self._skills if s.name in self._active_skills]

    def auto_activate_for_path(self, file_path: str) -> list[str]:
        """根据文件路径自动激活技能"""
        activated = []
        for skill in self._skills:
            if not skill.paths:
                continue
            for pattern in skill.paths:
                if fnmatch.fnmatch(file_path, pattern):
                    if skill.name not in self._active_skills:
                        self._active_skills.add(skill.name)
                        activated.append(skill.name)
                    break
        return activated

    def get_context_for_prompt(self) -> str:
        """获取激活技能的上下文用于注入 system prompt（完整内容，仅用于 auto_activate 的技能）"""
        active = self.get_active_skills()
        if not active:
            return ""

        # 仅 auto_activate 的技能注入完整内容，其余通过 read_skill 工具按需加载
        full_skills = [s for s in active if s.auto_activate]
        if not full_skills:
            return ""

        lines = ["## 自动激活的技能 (Skills - 完整内容)", ""]
        for skill in full_skills:
            lines.append(f"### {skill.name}")
            lines.append(skill.content)
            lines.append("")

        return "\n".join(lines)

    def get_summary_for_prompt(self) -> str:
        """
        渐进式披露：仅注入所有可用技能的 name + description（约 100 tokens/个）。
        完整内容通过 read_skill 工具按需加载，避免 token 浪费。
        """
        all_skills = self.load_all()
        if not all_skills:
            return ""

        lines = ["## 可用技能 (Skills - 渐进式披露)", ""]
        lines.append("以下技能可用，需要时调用 `read_skill` 工具加载完整内容：")
        lines.append("")
        for skill in all_skills:
            desc = skill.description or "(无描述)"
            # 限制描述长度，避免过长
            if len(desc) > 200:
                desc = desc[:200] + "..."
            auto_tag = " [自动激活]" if skill.auto_activate else ""
            lines.append(f"- **{skill.name}**{auto_tag}: {desc}")
        lines.append("")

        # auto_activate 的技能附加完整内容
        auto_skills = [s for s in all_skills if s.auto_activate]
        if auto_skills:
            lines.append("## 自动激活技能的完整内容")
            lines.append("")
            for skill in auto_skills:
                lines.append(f"### {skill.name}")
                lines.append(skill.content)
                lines.append("")

        return "\n".join(lines)

    def get_skill_content(self, name: str) -> Optional[str]:
        """按需获取技能完整内容（供 read_skill 工具调用）"""
        skill = self.get_skill(name)
        if skill is None:
            return None
        return skill.content

    def list_available_skills(self) -> list[dict]:
        """列出所有可用技能的摘要信息（供工具调用返回）"""
        all_skills = self.load_all()
        return [
            {
                "name": s.name,
                "description": s.description,
                "auto_activate": s.auto_activate,
                "tags": s.tags,
                "paths": s.paths,
            }
            for s in all_skills
        ]
