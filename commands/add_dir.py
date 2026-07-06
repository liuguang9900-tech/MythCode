"""
/add-dir — 运行时添加额外工作目录。
"""

from pathlib import Path
from commands.base import BaseCommand
from ui.console import console, print_error


class AddDirCommand(BaseCommand):
    name = "add-dir"
    description = "运行时添加额外工作目录"

    async def execute(self, args: str, agent) -> None:
        if not args.strip():
            # 显示当前额外目录
            if agent.additional_roots:
                console.print("[bold]当前额外工作目录:[/bold]")
                for d in agent.additional_roots:
                    console.print(f"  • {d}")
            else:
                console.print("[dim]没有额外工作目录[/dim]")
            console.print("[dim]用法: /add-dir /path/to/dir[/dim]")
            return

        dir_path = Path(args.strip()).resolve()
        if not dir_path.exists():
            print_error(f"目录不存在: {dir_path}")
            return
        if not dir_path.is_dir():
            print_error(f"不是目录: {dir_path}")
            return

        if str(dir_path) in agent.additional_roots:
            print_error(f"目录已添加: {dir_path}")
            return

        agent.additional_roots.append(str(dir_path))
        agent.sandbox.set_additional_roots(agent.additional_roots)
        agent.context.set_additional_roots(agent.additional_roots)
        console.print(f"[green]已添加额外工作目录:[/green] {dir_path}")
