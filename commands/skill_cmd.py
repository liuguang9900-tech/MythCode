"""
/skill 命令 — 技能管理。
子命令：list/activate/deactivate
"""

from typing import Optional
from commands.base import BaseCommand
from ui.console import console, print_info, print_error
from rich.table import Table


class SkillCommand(BaseCommand):
    """技能管理命令"""

    name = "skill"
    description = "技能管理：查看、激活、停用技能"
    aliases = ["skills"]

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行 /skill 命令"""
        parts = args.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "list"
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand == "list":
            self._list_skills(agent)
        elif subcommand == "activate":
            self._activate_skill(agent, sub_args.strip())
        elif subcommand == "deactivate":
            self._deactivate_skill(agent, sub_args.strip())
        else:
            print_error(f"未知子命令: {subcommand}。可用: list, activate, deactivate")

        return None

    def _list_skills(self, agent) -> None:
        """列出所有技能"""
        if not hasattr(agent, "skills") or agent.skills is None:
            print_info("技能系统未初始化")
            return

        skills = agent.skills.load_all()
        if not skills:
            print_info("暂无技能。在 .claude/skills/ 目录创建技能文件。")
            return

        active = set(agent.skills._active_skills)

        table = Table(title="技能列表", show_header=True)
        table.add_column("名称", style="cyan")
        table.add_column("描述", style="white")
        table.add_column("状态", style="green")
        table.add_column("自动激活", style="dim")

        for skill in skills:
            status = "[green]激活[/green]" if skill.name in active else "[dim]未激活[/dim]"
            auto = "是" if skill.auto_activate else "否"
            table.add_row(skill.name, skill.description[:40], status, auto)

        console.print(table)

    def _activate_skill(self, agent, name: str) -> None:
        """激活技能"""
        if not name:
            print_error("请指定技能名: /skill activate <name>")
            return

        if not hasattr(agent, "skills") or agent.skills is None:
            print_info("技能系统未初始化")
            return

        if agent.skills.activate(name):
            console.print(f"[green]✓ 技能 {name} 已激活[/green]")
        else:
            print_error(f"技能不存在: {name}")

    def _deactivate_skill(self, agent, name: str) -> None:
        """停用技能"""
        if not name:
            print_error("请指定技能名: /skill deactivate <name>")
            return

        if not hasattr(agent, "skills") or agent.skills is None:
            print_info("技能系统未初始化")
            return

        agent.skills.deactivate(name)
        console.print(f"[yellow]技能 {name} 已停用[/yellow]")
