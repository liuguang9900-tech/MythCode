"""
/status — 显示当前会话状态。
"""

from commands.base import BaseCommand
from ui.console import console


class StatusCommand(BaseCommand):
    name = "status"
    description = "显示当前会话状态"

    async def execute(self, args: str, agent) -> None:
        steps = agent.session_map.get_all_steps()
        msg_count = len(agent.memory.messages)
        tokens = agent.memory.estimate_tokens()
        context_pct = agent.memory.get_context_usage_pct()

        console.print()
        console.print("[bold]📊 会话状态[/bold]")
        console.print(f"  会话名称: [cyan]{agent.session_name or '未命名'}[/cyan]")
        console.print(f"  工作目录: {agent.workspace_root}")
        console.print(f"  模型: {agent.cfg.model.provider}/{agent.cfg.model.name}")
        console.print(f"  对话轮次: {len(steps)}")
        console.print(f"  消息数量: {msg_count}")
        console.print(f"  估算 Tokens: {tokens:,}")
        console.print(f"  上下文使用率: {context_pct:.1f}%")
        console.print(f"  安全模式: {'[yellow]开启[/yellow]' if agent.safe_mode else '关闭'}")
        console.print(f"  权限模式: [cyan]{agent.permission_engine.mode.value}[/cyan]")
        if agent.additional_roots:
            console.print(f"  额外目录: {', '.join(agent.additional_roots)}")
        console.print()
