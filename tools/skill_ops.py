"""
SkillOps 工具 — Skill 渐进式披露的按需加载入口。
提供 read_skill 和 list_skills 两个工具，让 LLM 自主决定加载哪些技能的完整内容。
"""

import json
from typing import Any
from tools.base import BaseTool, ToolResult


# 模块级技能管理器引用（由 AgentLoop 在初始化时注入）
_skills_manager = None


def set_skills_manager(mgr) -> None:
    """设置全局技能管理器引用"""
    global _skills_manager
    _skills_manager = mgr


class ReadSkillTool(BaseTool):
    """按需加载指定技能的完整内容（渐进式披露）"""

    name = "read_skill"
    description = (
        "加载指定技能的完整内容。系统启动时仅注入技能的名称和描述以节省 token，"
        "需要应用某个技能时调用此工具获取完整指令。"
    )
    parameters = {
        "name": {
            "type": "string",
            "description": "技能名称（与系统提示中列出的技能名一致）",
            "required": True,
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        if _skills_manager is None:
            return ToolResult(success=False, output="", error="技能管理器未初始化")

        skill_name = kwargs.get("name", "").strip()
        if not skill_name:
            return ToolResult(success=False, output="", error="技能名称不能为空")

        content = _skills_manager.get_skill_content(skill_name)
        if content is None:
            available = [s["name"] for s in _skills_manager.list_available_skills()]
            return ToolResult(
                success=False,
                output="",
                error=f"技能 '{skill_name}' 不存在。可用技能: {available}",
            )

        # 激活该技能（标记为已使用）
        _skills_manager.activate(skill_name)

        return ToolResult(
            success=True,
            output=f"# 技能: {skill_name}\n\n{content}",
            metadata={"skill_name": skill_name, "content_length": len(content)},
        )


class ListSkillsTool(BaseTool):
    """列出所有可用技能"""

    name = "list_skills"
    description = "列出当前工作区和用户目录下所有可用的技能及其描述。"
    parameters = {}  # 无参数

    async def execute(self, **kwargs) -> ToolResult:
        if _skills_manager is None:
            return ToolResult(success=False, output="", error="技能管理器未初始化")

        skills = _skills_manager.list_available_skills()
        if not skills:
            return ToolResult(
                success=True,
                output="(无可用技能)",
                metadata={"count": 0},
            )

        lines = [f"共 {len(skills)} 个可用技能：", ""]
        for s in skills:
            auto_tag = " [自动激活]" if s.get("auto_activate") else ""
            desc = s.get("description") or "(无描述)"
            lines.append(f"- **{s['name']}**{auto_tag}: {desc}")
            if s.get("tags"):
                lines.append(f"  标签: {', '.join(s['tags'])}")
            if s.get("paths"):
                lines.append(f"  适用路径: {', '.join(s['paths'])}")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"count": len(skills), "skills": skills},
        )
