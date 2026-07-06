"""
/upgrade — 检查更新。
"""

from commands.base import BaseCommand
from ui.console import console


class UpgradeCommand(BaseCommand):
    name = "upgrade"
    description = "检查 MythCoder 更新"

    async def execute(self, args: str, agent) -> None:
        console.print("[bold]当前版本:[/bold] mythcoder v0.1.0")
        console.print("[dim]自动更新功能将在后续版本中支持[/dim]")
        console.print("[dim]请手动执行: pip install --upgrade mythcoder[/dim]")
