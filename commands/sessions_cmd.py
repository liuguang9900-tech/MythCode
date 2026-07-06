"""
/sessions 命令 — 列出所有会话。
"""

from typing import Optional
from commands.base import BaseCommand
from ui.console import console, print_info, print_error
from rich.table import Table


class SessionsCommand(BaseCommand):
    """会话列表命令"""

    name = "sessions"
    description = "列出所有会话"
    aliases = ["session-list"]

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行 /sessions 命令"""
        sessions = agent.session_index._load().get("sessions", [])

        if not sessions:
            print_info("暂无会话记录")
            return None

        # 按工作区过滤
        workspace = str(agent.workspace_root)
        workspace_sessions = [s for s in sessions if s.get("workspace") == workspace]

        if not workspace_sessions:
            print_info("当前工作区暂无会话")
            return None

        table = Table(title="会话列表", show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="white")
        table.add_column("步骤数", style="green")
        table.add_column("保存时间", style="dim")

        current_session = agent._session_id
        for s in reversed(workspace_sessions):
            sid = s["id"]
            marker = "[green]→[/green] " if sid == current_session else "   "
            table.add_row(
                f"{marker}{sid}",
                s.get("name", "")[:30],
                str(s.get("step_count", 0)),
                s.get("saved_at", ""),
            )

        console.print(table)
        console.print("\n[dim]使用 /switch <session_id> 切换会话[/dim]")

        return None
