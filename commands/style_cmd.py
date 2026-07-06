"""
/style — 切换或列出输出样式。
"""

from commands.base import BaseCommand
from ui.console import console, print_error, print_info, print_success


class StyleCommand(BaseCommand):
    name = "style"
    description = "切换或列出输出样式"
    usage = """\
/style              # 列出所有样式
/style <name>       # 切换到指定样式
/style current      # 显示当前样式
/style reload       # 重新加载样式
"""

    async def execute(self, args: str, agent) -> None:
        # 获取或创建 OutputStyleManager
        manager = getattr(agent, "output_style_manager", None)
        if manager is None:
            from agent.output_style import OutputStyleManager
            manager = OutputStyleManager(agent.workspace_root)
            agent.output_style_manager = manager

        sub = args.strip()

        if not sub:
            # 列出所有样式
            self._list_styles(manager)
            return

        if sub == "current":
            current = manager.get_current_style()
            style = manager.get_style()
            console.print(f"[cyan]当前样式:[/cyan] {current}")
            console.print(f"[dim]{style.get('description', '')}[/dim]")
            return

        if sub == "reload":
            manager.reload()
            print_success("样式已重新加载")
            return

        # 切换样式
        if manager.set_style(sub):
            print_success(f"已切换到样式: {sub}")
        else:
            print_error(f"未找到样式: {sub}")
            console.print("[dim]可用样式:[/dim]")
            self._list_styles(manager)

    def _list_styles(self, manager) -> None:
        """列出所有样式"""
        styles = manager.list_styles()
        if not styles:
            print_info("无可用样式")
            return

        console.print()
        console.print("[bold]可用样式[/bold]")
        for s in styles:
            marker = "[green]*[/green] " if s["current"] else "  "
            name = s["name"]
            desc = s.get("description", "")
            console.print(f"{marker}[cyan]{name:15s}[/cyan]  [dim]{desc}[/dim]")
        console.print()
