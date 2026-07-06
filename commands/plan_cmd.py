"""
/plan 命令 — 计划管理。
子命令：new/approve/reject/list/show/execute
"""

from typing import Optional
from commands.base import BaseCommand
from ui.console import console, print_info, print_error
from rich.table import Table


class PlanCommand(BaseCommand):
    """计划管理命令"""

    name = "plan"
    description = "计划管理：生成、审批、执行计划"
    aliases = ["plans"]

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行 /plan 命令"""
        parts = args.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "list"
        sub_args = parts[1] if len(parts) > 1 else ""

        if subcommand == "list":
            self._list_plans(agent)
        elif subcommand == "show":
            self._show_plan(agent, sub_args.strip())
        elif subcommand == "approve":
            self._approve_plan(agent, sub_args.strip())
        elif subcommand == "reject":
            self._reject_plan(agent, sub_args.strip())
        elif subcommand == "execute":
            return await self._execute_plan(agent, sub_args.strip())
        elif subcommand == "new":
            print_info("在 plan 模式下输入任务描述，LLM 会自动生成计划。使用 /permissions plan 切换到 plan 模式。")
        else:
            print_error(f"未知子命令: {subcommand}。可用: list, show, approve, reject, execute, new")

        return None

    def _list_plans(self, agent) -> None:
        """列出所有计划"""
        plans = agent.plan_manager.list_plans()
        if not plans:
            print_info("暂无计划")
            return

        table = Table(title="计划列表", show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("标题", style="white")
        table.add_column("状态", style="green")
        table.add_column("创建时间", style="dim")

        for plan in plans:
            status_color = {
                "draft": "yellow",
                "approved": "green",
                "rejected": "red",
                "completed": "blue",
                "executing": "cyan",
            }.get(plan["status"], "white")
            table.add_row(
                plan["id"],
                plan["title"][:40],
                f"[{status_color}]{plan['status']}[/{status_color}]",
                plan.get("created_at", ""),
            )

        console.print(table)

    def _show_plan(self, agent, plan_id: str) -> None:
        """显示计划详情"""
        if not plan_id:
            print_error("请指定计划 ID: /plan show <plan_id>")
            return

        plan = agent.plan_manager.get_plan(plan_id)
        if not plan:
            print_error(f"计划不存在: {plan_id}")
            return

        console.print(f"\n[bold cyan]计划: {plan['title']}[/bold cyan]")
        console.print(f"状态: {plan['status']}")
        console.print(f"创建时间: {plan.get('created_at', '')}")
        console.print("\n[bold]步骤:[/bold]")

        for i, step in enumerate(plan["steps"], 1):
            status_icon = {
                "pending": "○",
                "in_progress": "◐",
                "completed": "●",
            }.get(step.get("status", "pending"), "○")
            console.print(f"  {i}. {status_icon} {step['description']}")

    def _approve_plan(self, agent, plan_id: str) -> None:
        """批准计划"""
        if not plan_id:
            print_error("请指定计划 ID: /plan approve <plan_id>")
            return

        if agent.plan_manager.approve_plan(plan_id):
            console.print(f"[green]✓ 计划 {plan_id} 已批准[/green]")
            console.print("[dim]使用 /plan execute 开始执行计划[/dim]")
        else:
            print_error(f"批准失败：计划不存在或状态不允许")

    def _reject_plan(self, agent, plan_id: str) -> None:
        """拒绝计划"""
        if not plan_id:
            print_error("请指定计划 ID: /plan reject <plan_id>")
            return

        if agent.plan_manager.reject_plan(plan_id):
            console.print(f"[yellow]计划 {plan_id} 已拒绝[/yellow]")
        else:
            print_error(f"拒绝失败：计划不存在")

    async def _execute_plan(self, agent, plan_id: str) -> Optional[str]:
        """执行计划"""
        if not plan_id:
            # 使用活跃计划
            plan = agent.plan_manager.get_active_plan()
            if not plan:
                print_error("没有活跃计划。请先 /plan approve <plan_id>")
                return None
            plan_id = plan["id"]
        else:
            plan = agent.plan_manager.get_plan(plan_id)
            if not plan:
                print_error(f"计划不存在: {plan_id}")
                return None
            if plan["status"] != "approved":
                print_error(f"计划状态为 {plan['status']}，请先批准: /plan approve {plan_id}")
                return None

        # 切换到 acceptEdits 模式执行
        from agent.permissions import PermissionMode
        agent.permission_engine.set_mode(PermissionMode.ACCEPT_EDITS)
        agent.plan_manager.set_active_plan(plan_id)

        console.print(f"[green]开始执行计划: {plan['title']}[/green]")
        console.print("[dim]已切换到 acceptEdits 模式[/dim]")

        return None
