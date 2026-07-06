"""
/config — 显示当前配置。
"""

from commands.base import BaseCommand
from ui.console import print_config_info


class ConfigCommand(BaseCommand):
    name = "config"
    description = "显示当前配置"

    async def execute(self, args: str, agent) -> None:
        print_config_info()
