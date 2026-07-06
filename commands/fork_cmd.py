"""
/fork 命令 — 从指定步骤创建新会话分支。
"""

from typing import Optional
from commands.base import BaseCommand
from ui.console import console, print_info, print_error, print_rewind_steps


class ForkCommand(BaseCommand):
    """会话分叉命令"""

    name = "fork"
    description = "从指定步骤创建新会话分支"

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行 /fork 命令"""
        parts = args.split(maxsplit=1)

        if not parts or not parts[0]:
            # 显示步骤列表供选择
            steps = agent.session_map.get_all_steps()
            if not steps:
                print_info("暂无步骤记录")
                return None
            print_rewind_steps(steps)
            console.print("\n[dim]用法: /fork <step_id> <新会话名称>[/dim]")
            return None

        try:
            step_id = int(parts[0])
        except ValueError:
            print_error(f"无效的步骤 ID: {parts[0]}")
            return None

        name = parts[1].strip() if len(parts) > 1 else f"分叉自步骤 {step_id}"

        try:
            from agent.session_fork import SessionForker
            forker = SessionForker(agent.workspace_root, agent.session_index)
            new_session_id = forker.fork_from_step(agent, step_id, name)

            if new_session_id is None:
                print_error(f"步骤 {step_id} 不存在")
                return None

            console.print(f"[green]✓ 已创建新会话分支: {new_session_id}[/green]")
            console.print(f"[dim]名称: {name}[/dim]")
            console.print(f"[dim]使用 /switch {new_session_id} 切换到该会话[/dim]")

        except Exception as e:
            print_error(f"创建分叉失败: {e}")

        return None
