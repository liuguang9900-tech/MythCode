"""
/ide — IDE 集成信息。
"""

from commands.base import BaseCommand
from ui.console import console


class IDECommand(BaseCommand):
    name = "ide"
    description = "显示 IDE 集成状态"

    async def execute(self, args: str, agent) -> None:
        console.print("[bold]IDE 集成[/bold]")
        console.print()
        console.print("[dim]MythCoder 当前运行在终端独立模式[/dim]")
        console.print()
        console.print("支持的集成方式:")
        console.print("  • VS Code 终端: 直接在 VS Code 内置终端中运行 mythcoder")
        console.print("  • JetBrains 终端: 在 IDE 终端中运行 mythcoder")
        console.print("  • 外部终端: iTerm2, Terminal.app, Windows Terminal 等")
        console.print()
        console.print("[dim]IDE 插件支持将在后续版本中添加[/dim]")
