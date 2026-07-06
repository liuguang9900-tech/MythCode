"""
/clear — 清空对话历史。
"""

from commands.base import BaseCommand
from ui.console import print_info


class ClearCommand(BaseCommand):
    name = "clear"
    description = "清空对话历史"

    async def execute(self, args: str, agent) -> None:
        agent.reset()
        print_info("对话历史已清空")
