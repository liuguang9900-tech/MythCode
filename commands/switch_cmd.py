"""
/switch 命令 — 切换会话。
"""

from typing import Optional
from commands.base import BaseCommand
from ui.console import console, print_info, print_error, print_restored_conversation


class SwitchCommand(BaseCommand):
    """切换会话命令"""

    name = "switch"
    description = "切换到指定会话"

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行 /switch 命令"""
        session_id = args.strip()

        if not session_id:
            print_error("请指定会话 ID: /switch <session_id>")
            return None

        try:
            from agent.session_fork import SessionForker
            forker = SessionForker(agent.workspace_root, agent.session_index)
            result = forker.switch_to(agent, session_id)

            if result is None:
                print_error(f"会话不存在: {session_id}")
                return None

            print_restored_conversation(result)
            console.print(f"[green]✓ 已切换到会话: {session_id}[/green]")

        except Exception as e:
            print_error(f"切换会话失败: {e}")

        return None
