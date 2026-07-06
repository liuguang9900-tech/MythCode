"""
命令基类 — 所有斜杠命令的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent.loop import AgentLoop


class BaseCommand(ABC):
    """斜杠命令抽象基类"""

    name: str = ""
    description: str = ""
    aliases: list[str] = []

    @abstractmethod
    async def execute(self, args: str, agent: "AgentLoop") -> Optional[str]:
        """
        执行命令。

        Args:
            args: 命令参数（/command 后面的部分）
            agent: 当前 AgentLoop 实例

        Returns:
            "exit" 表示需要退出程序，None 表示继续运行
        """
        ...
