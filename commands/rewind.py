"""
/rewind — 时空回溯：回滚到历史步骤。
"""

from commands.base import BaseCommand
from ui.console import console, print_info, print_error, print_rewind_steps, print_rewind_result


class RewindCommand(BaseCommand):
    name = "rewind"
    description = "时空回溯：回滚到历史步骤"

    async def execute(self, args: str, agent) -> None:
        steps = agent.session_map.get_all_steps()

        if not steps:
            print_info("没有可回溯的历史步骤")
            return

        print_rewind_steps(steps)

        try:
            choice = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]已取消[/dim]")
            return

        if choice.lower() in ("q", "quit", "cancel"):
            print_info("已取消回滚")
            return

        try:
            target_step = int(choice)
        except ValueError:
            print_error(f"无效的步骤序号: {choice}")
            return

        if target_step < 0 or target_step > agent.session_map.current_step_id:
            print_error(f"步骤序号超出范围 (0-{agent.session_map.current_step_id})")
            return

        if target_step < agent.session_map.current_step_id:
            console.print(
                f"[yellow]⚠ 将回滚到 Step {target_step}，"
                f"丢弃 Step {target_step + 1} 到 Step {agent.session_map.current_step_id} 的所有更改[/yellow]"
            )
            try:
                confirm = input("  确认? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]已取消[/dim]")
                return
            if confirm not in ("y", "yes", "是"):
                print_info("已取消回滚")
                return

        result = agent.rewind_to_step(target_step)
        print_rewind_result(result)
