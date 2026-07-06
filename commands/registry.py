"""
命令注册中心 — 对标 ToolRegistry 的注册模式。
"""

from typing import Optional
from commands.base import BaseCommand


class CommandRegistry:
    """斜杠命令注册中心（单例）"""

    _instance: Optional["CommandRegistry"] = None

    def __new__(cls) -> "CommandRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._commands: dict[str, BaseCommand] = {}
            cls._instance._aliases: dict[str, str] = {}
        return cls._instance

    def register(self, command: BaseCommand) -> None:
        """注册命令"""
        name = command.name.lstrip("/")
        if name in self._commands:
            raise ValueError(f"命令 '{name}' 已注册")
        self._commands[name] = command
        for alias in command.aliases:
            alias = alias.lstrip("/")
            self._aliases[alias] = name

    def get(self, name: str) -> Optional[BaseCommand]:
        """获取命令（支持别名）"""
        name = name.lstrip("/")
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None

    def list_commands(self) -> list[BaseCommand]:
        """列出所有命令"""
        return list(self._commands.values())

    def get_names(self) -> list[str]:
        """获取所有命令名"""
        return list(self._commands.keys())


# 全局单例
registry = CommandRegistry()
