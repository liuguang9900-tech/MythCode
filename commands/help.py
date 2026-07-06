"""
/help — 显示帮助信息。
"""

from commands.base import BaseCommand
from ui.console import print_help


class HelpCommand(BaseCommand):
    name = "help"
    description = "显示帮助信息"
    aliases = ["h", "?"]

    async def execute(self, args: str, agent) -> None:
        print_help()
