"""
/exit, /quit — 退出程序。
"""

from commands.base import BaseCommand
from ui.console import console


class ExitCommand(BaseCommand):
    name = "exit"
    description = "退出程序"
    aliases = ["quit", "q"]

    async def execute(self, args: str, agent) -> str:
        agent.save_conversation()
        console.print("[dim]再见![/dim]")
        return "exit"
