"""
/memory — 查看/编辑自动记忆。
"""

from commands.base import BaseCommand
from ui.console import console, print_info


class MemoryCommand(BaseCommand):
    name = "memory"
    description = "查看自动记忆"

    async def execute(self, args: str, agent) -> None:
        if not hasattr(agent, 'auto_memory') or agent.auto_memory is None:
            console.print("[dim]自动记忆功能尚未启用[/dim]")
            console.print("[dim]自动记忆会在对话中自动记录重要信息[/dim]")
            return

        memories = agent.auto_memory.get_all()
        if not memories:
            print_info("没有已保存的记忆")
            return

        console.print("[bold]📝 自动记忆[/bold]")
        console.print()
        for i, mem in enumerate(memories, 1):
            console.print(f"  {i}. [cyan]{mem.get('title', '无标题')}[/cyan]")
            console.print(f"     {mem.get('content', '')[:200]}")
            console.print()
