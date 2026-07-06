"""
/model — 查看或切换模型。
"""

from commands.base import BaseCommand
from config import get_config
from ui.console import console, print_error


class ModelCommand(BaseCommand):
    name = "model"
    description = "查看或切换模型"

    async def execute(self, args: str, agent) -> None:
        if not args.strip():
            cfg = get_config()
            console.print(f"[bold]当前模型:[/bold] [green]{cfg.model.provider}/{cfg.model.name}[/green]")
            console.print("[dim]用法: /model <模型名>  例如: /model gpt-4o[/dim]")
            return

        try:
            agent.switch_model(args.strip())
            console.print(f"[green]已切换到模型: {args.strip()}[/green]")
        except Exception as e:
            print_error(f"切换模型失败: {e}")
