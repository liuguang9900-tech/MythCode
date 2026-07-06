"""
/cost — 显示 Token 用量和费用估算，支持跨会话累计和预算检查。
"""

from commands.base import BaseCommand
from ui.console import console, print_warning
from agent.cost_tracker import CostTracker, get_model_price, calculate_cost


class CostCommand(BaseCommand):
    name = "cost"
    description = "显示 Token 用量和费用估算（含跨会话累计）"
    usage = """\
/cost              # 显示当前会话费用
/cost total        # 显示跨会话累计
/cost today        # 显示今日费用
/cost month        # 显示本月费用
/cost sessions     # 列出最近会话
/cost budget       # 显示预算使用情况
"""

    async def execute(self, args: str, agent) -> None:
        # 获取或创建 CostTracker
        tracker = getattr(agent, "cost_tracker", None)
        if tracker is None:
            tracker = CostTracker(
                workspace_root=agent.workspace_root,
                enabled=getattr(agent.cfg.cost, "track_cross_session", True),
            )

        sub = args.strip().split()[0] if args.strip() else ""

        if sub == "total":
            self._show_total(tracker)
        elif sub == "today":
            self._show_period(tracker, "today")
        elif sub in ("yesterday",):
            self._show_period(tracker, "yesterday")
        elif sub == "week":
            self._show_period(tracker, "week")
        elif sub == "month":
            self._show_period(tracker, "month")
        elif sub == "sessions":
            self._show_sessions(tracker)
        elif sub == "budget":
            self._show_budget(tracker, agent)
        else:
            self._show_current_session(agent, tracker)

    def _show_current_session(self, agent, tracker: CostTracker) -> None:
        """显示当前会话费用"""
        usage = agent.get_token_usage()
        model = agent.cfg.model.name

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens

        cost = calculate_cost(model, prompt_tokens, completion_tokens)
        price = get_model_price(model)

        console.print()
        console.print("[bold]当前会话 Token 用量[/bold]")
        console.print(f"  模型: [cyan]{model}[/cyan]")
        if price:
            console.print(f"  价格: [dim]${price['input']:.2f}/M input, ${price['output']:.2f}/M output[/dim]")
        console.print(f"  输入 tokens: {prompt_tokens:,}")
        console.print(f"  输出 tokens: {completion_tokens:,}")
        console.print(f"  总计 tokens: {total_tokens:,}")

        if cost is not None:
            console.print(f"  估算费用: [yellow]${cost:.4f}[/yellow]")
        else:
            console.print(f"  估算费用: [dim]未知（模型 {model} 无价格数据）[/dim]")

        console.print(f"  上下文窗口使用: {usage.get('context_usage_pct', 0):.1f}%")

        # 显示跨会话累计
        if tracker.enabled:
            total = tracker.get_total()
            console.print()
            console.print("[bold]跨会话累计[/bold]")
            console.print(f"  总 tokens: {total.get('total_tokens', 0):,}")
            console.print(f"  总费用: [yellow]${total.get('cost', 0):.4f}[/yellow]")

            # 预算检查
            daily_budget = getattr(agent.cfg.cost, "daily_budget", 0)
            monthly_budget = getattr(agent.cfg.cost, "monthly_budget", 0)
            if daily_budget > 0 or monthly_budget > 0:
                budget = tracker.check_budget(daily_budget, monthly_budget)
                if budget["warnings"]:
                    for w in budget["warnings"]:
                        print_warning(w)

        console.print()

    def _show_total(self, tracker: CostTracker) -> None:
        """显示跨会话总计"""
        total = tracker.get_total()
        console.print()
        console.print("[bold]跨会话累计费用[/bold]")
        console.print(f"  输入 tokens: {total.get('prompt_tokens', 0):,}")
        console.print(f"  输出 tokens: {total.get('completion_tokens', 0):,}")
        console.print(f"  总 tokens: {total.get('total_tokens', 0):,}")
        console.print(f"  总费用: [yellow]${total.get('cost', 0):.4f}[/yellow]")
        console.print()

    def _show_period(self, tracker: CostTracker, period: str) -> None:
        """显示指定时段费用"""
        labels = {
            "today": "今日",
            "yesterday": "昨日",
            "week": "本周（近7天）",
            "month": "本月",
        }
        label = labels.get(period, period)
        data = tracker.get_period_costs(period)
        console.print()
        console.print(f"[bold]{label}费用[/bold]")
        console.print(f"  输入 tokens: {data.get('prompt_tokens', 0):,}")
        console.print(f"  输出 tokens: {data.get('completion_tokens', 0):,}")
        console.print(f"  总 tokens: {data.get('total_tokens', 0):,}")
        console.print(f"  费用: [yellow]${data.get('cost', 0):.4f}[/yellow]")
        console.print()

    def _show_sessions(self, tracker: CostTracker) -> None:
        """列出最近会话"""
        sessions = tracker.list_sessions(limit=10)
        if not sessions:
            console.print("[dim]无会话记录[/dim]")
            return

        console.print()
        console.print("[bold]最近会话[/bold]")
        for s in sessions:
            sid = s["session_id"][:12]
            model = s["model"]
            cost = s["cost"]
            tokens = s["total_tokens"]
            time_str = s.get("last_call_time") or s.get("start_time", "")
            # 简化时间显示
            if time_str:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    time_str = time_str[:16]
            console.print(f"  [cyan]{sid}[/cyan]  {model:30s}  {tokens:>10,} tokens  ${cost:.4f}  [dim]{time_str}[/dim]")
        console.print()

    def _show_budget(self, tracker: CostTracker, agent) -> None:
        """显示预算使用情况"""
        daily_budget = getattr(agent.cfg.cost, "daily_budget", 0)
        monthly_budget = getattr(agent.cfg.cost, "monthly_budget", 0)
        threshold = getattr(agent.cfg.cost, "warning_threshold", 0.8)

        budget = tracker.check_budget(daily_budget, monthly_budget)

        console.print()
        console.print("[bold]预算使用情况[/bold]")

        if daily_budget > 0:
            pct = budget["daily_pct"]
            color = "red" if pct >= 100 else "yellow" if pct >= threshold * 100 else "green"
            console.print(f"  日预算: [yellow]${budget['daily_used']:.4f}[/yellow] / ${daily_budget:.4f}  [{color}]{pct:.1f}%[/{color}]")
        else:
            console.print("  日预算: [dim]未设置[/dim]")

        if monthly_budget > 0:
            pct = budget["monthly_pct"]
            color = "red" if pct >= 100 else "yellow" if pct >= threshold * 100 else "green"
            console.print(f"  月预算: [yellow]${budget['monthly_used']:.4f}[/yellow] / ${monthly_budget:.4f}  [{color}]{pct:.1f}%[/{color}]")
        else:
            console.print("  月预算: [dim]未设置[/dim]")

        if budget["warnings"]:
            console.print()
            for w in budget["warnings"]:
                print_warning(w)

        console.print()
