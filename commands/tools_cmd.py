"""
/tools — 列出可用工具。
"""

from commands.base import BaseCommand
from ui.console import print_tools_list


class ToolsCommand(BaseCommand):
    name = "tools"
    description = "列出可用工具"

    async def execute(self, args: str, agent) -> None:
        print_tools_list()
