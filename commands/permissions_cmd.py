"""
/permissions — 交互式管理权限规则。
"""

from commands.base import BaseCommand
from ui.console import console, print_error


class PermissionsCommand(BaseCommand):
    name = "permissions"
    description = "管理权限规则"

    async def execute(self, args: str, agent) -> None:
        engine = agent.permission_engine

        if not args.strip():
            # 显示当前状态
            console.print(f"[bold]当前权限模式:[/bold] [cyan]{engine.mode.value}[/cyan]")
            console.print()
            console.print("[bold]可用模式:[/bold]")
            console.print("  default     — 正常询问确认")
            console.print("  acceptEdits — 自动批准编辑操作")
            console.print("  plan        — 只读模式，拒绝写操作")
            console.print("  auto        — 自动批准所有操作")
            console.print("  bypass      — 跳过所有权限检查")
            console.print()
            console.print("[dim]用法: /permissions <模式名>  例如: /permissions plan[/dim]")
            return

        mode_name = args.strip()
        mode_map = {
            "default": "default",
            "acceptedits": "acceptEdits",
            "plan": "plan",
            "auto": "auto",
            "bypass": "bypassPermissions",
        }

        mapped = mode_map.get(mode_name.lower(), mode_name)
        from agent.permissions import PermissionMode

        try:
            new_mode = PermissionMode(mapped)
            engine.set_mode(new_mode)
            console.print(f"[green]权限模式已切换为: {new_mode.value}[/green]")
        except ValueError:
            print_error(f"无效的权限模式: {mode_name}")
            console.print("[dim]可用模式: default, acceptEdits, plan, auto, bypass[/dim]")
