"""
Rich Console 封装 — Markdown 渲染、面板、颜色主题。
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich import box

from config import get_config

# 全局 Console 实例
console = Console()


def _get_version_str() -> str:
    """读取版本号：优先从已安装包元数据，其次从 pyproject.toml"""
    # 1. 从已安装包的元数据读取（pip install 后可用）
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version("mythcoder")
        except PackageNotFoundError:
            pass
    except ImportError:
        pass

    # 2. 从源码目录的 pyproject.toml 读取（开发模式）
    try:
        from pathlib import Path
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("version ="):
                    return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return "0.0.0"


def print_welcome():
    """打印欢迎界面 — 专业极简风格"""
    cfg = get_config()
    version = _get_version_str()

    # ── 顶部装饰线 ──
    console.print()
    console.print("[dim]─────────────────────────────────────────────────────────────[/dim]")

    # ── Logo 区 ──
    logo = Text()
    logo.append("  ◆  ", style="bold cyan")
    logo.append("Myth", style="bold cyan")
    logo.append("Code", style="bold white")
    logo.append(f"  v{version}", style="dim")
    console.print(logo)
    console.print("[dim italic]  AI Coding Agent · 终端里的自主编程智能体[/dim italic]")

    console.print("[dim]─────────────────────────────────────────────────────────────[/dim]")

    # ── 信息区：紧凑键值对 ──
    model_str = f"[bold green]{cfg.model.provider}[/bold green] / [green]{cfg.model.name}[/green]"
    ctx_str = f"[yellow]{cfg.agent.context_window // 1000}K[/yellow]"
    iter_str = f"[cyan]{cfg.agent.max_iterations}[/cyan]"
    safe_str = "[green]开启[/green]" if cfg.safety.require_approval else "[yellow]关闭[/yellow]"

    console.print(
        f"  [dim]模型[/dim] {model_str}   [dim]·[/dim]   "
        f"[dim]上下文[/dim] {ctx_str} [dim]tokens[/dim]   [dim]·[/dim]   "
        f"[dim]迭代上限[/dim] {iter_str}   [dim]·[/dim]   "
        f"[dim]安全确认[/dim] {safe_str}"
    )
    console.print(f"  [dim]工作目录[/dim] [blue]{cfg.safety.project_root}[/blue]")

    console.print("[dim]─────────────────────────────────────────────────────────────[/dim]")

    # ── 快捷命令区：三列网格 ──
    console.print("  [bold]快捷命令[/bold]")
    console.print()

    cmd_grid = Table(show_header=False, box=None, padding=(0, 4), show_edge=False)
    cmd_grid.add_column(justify="left", no_wrap=True)
    cmd_grid.add_column(justify="left", no_wrap=True)
    cmd_grid.add_column(justify="left", no_wrap=True)

    cmd_grid.add_row(
        "[cyan]/help[/cyan]    [dim]查看帮助[/dim]",
        "[cyan]/rewind[/cyan]  [dim]时空回溯[/dim]",
        "[cyan]/tools[/cyan]   [dim]工具列表[/dim]",
    )
    cmd_grid.add_row(
        "[cyan]/config[/cyan]  [dim]查看配置[/dim]",
        "[cyan]/clear[/cyan]   [dim]清空对话[/dim]",
        "[cyan]/exit[/cyan]    [dim]退出程序[/dim]",
    )
    console.print(cmd_grid)

    console.print("[dim]─────────────────────────────────────────────────────────────[/dim]")

    # ── 底部提示 ──
    console.print("  [dim]输入自然语言指令开始工作，或使用 [cyan]/[/cyan] 触发斜杠命令[/dim]")
    console.print()


def print_restored_conversation(info: dict):
    """打印恢复的对话摘要"""
    step_count = info.get("step_count", 0)
    message_count = info.get("message_count", 0)
    saved_at = info.get("saved_at", "未知")
    last_exchanges = info.get("last_exchanges", [])

    summary_lines = []
    summary_lines.append(f"[bold]已恢复之前的对话[/bold]")
    summary_lines.append(f"[dim]保存时间: {saved_at}[/dim]")
    summary_lines.append(f"[dim]对话步骤: {step_count} 步, 共 {message_count} 条消息[/dim]")

    if last_exchanges:
        summary_lines.append("")
        summary_lines.append("[bold]最近对话:[/bold]")
        for i, exchange in enumerate(last_exchanges):
            user_preview = exchange.get("user", "")[:80]
            assistant_preview = exchange.get("assistant_preview", "")[:80]
            summary_lines.append(f"  [cyan]你:[/cyan] {user_preview}")
            summary_lines.append(f"  [green]AI:[/green] {assistant_preview}")
            if i < len(last_exchanges) - 1:
                summary_lines.append("  [dim]---[/dim]")

    panel = Panel(
        "\n".join(summary_lines),
        title="[bold cyan]对话已恢复[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def print_help():
    """打印帮助信息"""
    from commands.registry import registry as command_registry

    commands = command_registry.list_commands()
    cmd_lines = []
    for cmd in sorted(commands, key=lambda c: c.name):
        aliases = f" ({', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
        cmd_lines.append(f"| `/{cmd.name}`{aliases} | {cmd.description} |")

    help_text = f"""
## 可用命令

| 命令 | 说明 |
|------|------|
{chr(10).join(cmd_lines)}

## 使用方式
直接输入自然语言指令，智能体会自动：
- 读取和分析代码文件
- 搜索代码库
- 执行终端命令
- 编写和修改代码

## 示例
```
> 帮我找到所有定义 API 路由的文件
> 在 src/api.py 中添加一个 /health 端点
> 运行测试并修复失败的用例
```
"""
    console.print(Markdown(help_text))


def print_config_info():
    """打印当前配置"""
    cfg = get_config()

    table = Table(title="当前配置", box=box.ROUNDED)
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("模型", f"{cfg.model.provider}/{cfg.model.name}")
    table.add_row("温度", str(cfg.model.temperature))
    table.add_row("最大 Token", str(cfg.model.max_tokens))
    table.add_row("最大迭代", str(cfg.agent.max_iterations))
    table.add_row("上下文窗口", f"{cfg.agent.context_window} tokens")
    table.add_row("历史轮数", str(cfg.agent.history_max_turns))
    table.add_row("安全确认", "开启" if cfg.safety.require_approval else "关闭")
    table.add_row("工作目录", cfg.safety.project_root)

    console.print(table)


def print_tools_list():
    """打印可用工具列表"""
    from tools.registry import registry

    table = Table(title="可用工具", box=box.ROUNDED)
    table.add_column("工具名称", style="cyan")
    table.add_column("描述", style="white")

    for tool in registry.list_tools():
        desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
        table.add_row(tool.name, desc)

    console.print(table)


def print_tool_call(name: str, args: dict):
    """打印工具调用信息"""
    # 写工具的大内容参数脱敏：不打印文件正文，仅显示规模，避免刷屏
    args = _redact_tool_args(name, args)

    style_manager = _get_style_manager()
    if style_manager is not None:
        formatted = style_manager.format_tool_call(name, args)
        color = style_manager.get_color("tool_call")
        if formatted:
            console.print(f"[{color}]{formatted}[/{color}]")
        return

    args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
    panel = Panel(
        f"[bold yellow]🔧 {name}[/bold yellow]\n[dim]{args_str}[/dim]",
        box=box.ROUNDED,
        border_style="yellow",
    )
    console.print(panel)


# 写类工具中需要脱敏的大内容字段
_CONTENT_FIELDS = {"content", "old_string", "new_string", "notebook_json"}


def _redact_tool_args(name: str, args: dict) -> dict:
    """对写工具的大内容参数脱敏，替换为规模摘要，保留 file_path 等元信息用于进度追踪"""
    if name not in ("write_file", "edit_file", "write_notebook"):
        return args
    redacted = {}
    for k, v in args.items():
        if k in _CONTENT_FIELDS and isinstance(v, str):
            lines = v.count("\n") + (1 if v else 0)
            redacted[k] = f"<{lines} 行, {len(v)} 字符>"
        else:
            redacted[k] = v
    return redacted


def print_tool_result(name: str, success: bool, output_preview: str):
    """打印工具执行结果"""
    style_manager = _get_style_manager()
    if style_manager is not None:
        formatted = style_manager.format_tool_result(output_preview or "", success)
        color = style_manager.get_color("tool_result" if success else "tool_error")
        if formatted:
            console.print(f"[{color}]{formatted}[/{color}]")
        return

    style = "green" if success else "red"
    icon = "✓" if success else "✗"
    if output_preview is None:
        output_preview = "(无输出)"
    preview = output_preview[:2000] + "..." if len(output_preview) > 2000 else output_preview

    panel = Panel(
        f"[bold {style}]{icon} {name}[/bold {style}]\n[dim]{preview}[/dim]",
        box=box.ROUNDED,
        border_style=style,
    )
    console.print(panel)


# 全局样式管理器引用（由 AgentLoop 设置）
_global_style_manager = None


def set_style_manager(manager) -> None:
    """设置全局样式管理器"""
    global _global_style_manager
    _global_style_manager = manager


def _get_style_manager():
    """获取全局样式管理器"""
    return _global_style_manager


def print_approval_request(command: str, reason: str):
    """打印用户确认请求"""
    panel = Panel(
        f"[bold red]⚠ 需要确认[/bold red]\n\n"
        f"[yellow]原因:[/yellow] {reason}\n"
        f"[yellow]命令:[/yellow] {command}\n\n"
        f"输入 [green]y[/green] 执行, [red]n[/red] 取消",
        box=box.ROUNDED,
        border_style="red",
    )
    console.print(panel)


def print_error(message: str):
    """打印错误信息"""
    console.print(f"[red]✗ {message}[/red]")


# ============================================================
# 状态指示器 — 长时间等待时显示 spinner（参考 Claude Code）
# 用法：
#   with status_spinner("思考中..."):
#       do_long_work()
# ============================================================

def status_spinner(message: str, spinner: str = "dots"):
    """返回一个 Status 上下文管理器，用于显示长时间操作的进度"""
    return console.status(f"[cyan]{message}[/cyan]", spinner=spinner)


def print_step(message: str):
    """打印步骤提示（无 spinner，仅一行）"""
    console.print(f"[dim]→ {message}[/dim]")


def print_info(message: str):
    """打印信息"""
    console.print(f"[dim]{message}[/dim]")


def print_success(message: str):
    """打印成功信息"""
    console.print(f"[green]✓ {message}[/green]")


def print_warning(message: str):
    """打印警告信息"""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_code_block(code: str, language: str = ""):
    """打印代码块（带语法高亮）"""
    cfg = get_config()
    if language:
        syntax = Syntax(code, language, theme=cfg.ui.syntax_theme)
    else:
        syntax = Syntax(code, "text", theme=cfg.ui.syntax_theme)
    console.print(syntax)


def print_markdown(text: str):
    """渲染 Markdown 文本"""
    console.print(Markdown(text))


def print_rewind_steps(steps: list) -> None:
    """打印时空回溯步骤列表"""
    if not steps:
        console.print("[yellow]没有可回溯的历史步骤[/yellow]")
        return

    table = Table(title="时空回溯 - 历史步骤", box=box.ROUNDED)
    table.add_column("Step", style="cyan", justify="right", width=5)
    table.add_column("用户输入", style="white", max_width=60)
    table.add_column("操作摘要", style="dim", max_width=40)
    table.add_column("类型", style="dim", width=8)

    for step in steps:
        step_type = "[dim]仅读取[/dim]" if _is_readonly_step(step) else "[yellow]有修改[/yellow]"
        user_input = step.user_input[:80] + ("..." if len(step.user_input) > 80 else "")
        summary = step.summary[:60] + ("..." if len(step.summary) > 60 else "")
        table.add_row(
            str(step.step_id),
            user_input,
            summary,
            step_type,
        )

    console.print(table)
    console.print("[dim]输入要回到的步骤序号 (或 q 取消)[/dim]")


def print_rewind_result(result: dict) -> None:
    """打印回滚结果"""
    if not result.get("success"):
        console.print(f"[red]✗ 回滚失败: {result.get('warnings', ['未知错误'])[0]}[/red]")
        return

    target = result.get("target_step", "?")
    files = result.get("files_restored", [])
    warnings = result.get("warnings", [])

    panel_content = f"[bold green]✓ 已回滚到 Step {target}[/bold green]\n"

    if files:
        panel_content += f"\n[bold]已还原文件 ({len(files)}):[/bold]\n"
        for f in files:
            panel_content += f"  • {f}\n"
    else:
        panel_content += "\n[dim](无文件需要还原，仅截断了对话历史)[/dim]\n"

    if warnings:
        panel_content += f"\n[yellow]⚠ 警告:[/yellow]\n"
        for w in warnings:
            panel_content += f"  • {w}\n"

    panel = Panel(panel_content.strip(), box=box.ROUNDED, border_style="green")
    console.print(panel)


def _is_readonly_step(step) -> bool:
    """判断步骤是否只有读操作"""
    write_tools = {"write_file", "edit_file", "execute_command"}
    return not any(t in write_tools for t in step.tool_calls)


def print_json_output(data: dict, output_format: str = "json") -> None:
    """非交互输出模式：以指定格式输出 JSON"""
    import json
    if output_format == "stream-json":
        # JSON Lines 格式
        print(json.dumps(data, ensure_ascii=False))
    else:
        # 标准 JSON 格式
        print(json.dumps(data, indent=2, ensure_ascii=False))


def print_todo_list(todos: list) -> None:
    """打印 TODO 任务清单面板"""
    if not todos:
        return

    table = Table(title="任务清单", box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim", justify="right", width=3)
    table.add_column("状态", justify="center", width=4)
    table.add_column("任务", style="white")

    for i, todo in enumerate(todos, 1):
        status = todo.status.value if hasattr(todo.status, "value") else str(todo.status)
        icon = {
            "pending": "[dim]○[/dim]",
            "in_progress": "[yellow bold]◐[/yellow bold]",
            "completed": "[green]●[/green]",
        }.get(status, "○")
        desc = todo.active_form if (status == "in_progress" and todo.active_form) else todo.content
        table.add_row(str(i), icon, desc)

    console.print(table)


def print_diff_preview(file_path: str, diff_text: str, is_new_file: bool = False) -> None:
    """打印文件变更的 diff 预览"""
    from utils.diff_utils import count_diff_changes, format_diff_for_display

    if not diff_text and not is_new_file:
        console.print("[dim](无变更)[/dim]")
        return

    changes = count_diff_changes(diff_text)
    title = f"变更预览: {file_path}"
    if is_new_file:
        title += " (新建文件)"

    header = f"[bold]{title}[/bold]"
    if not is_new_file:
        header += f"  [green]+{changes['added']}[/green] [red]-{changes['removed']}[/red]"

    console.print()
    console.print(header)

    # 新建文件不打印 diff 内容体（整个文件都是新增，会刷屏），仅显示进度标题
    if is_new_file:
        console.print(f"[dim]  已创建，共 {changes['added']} 行[/dim]")
        console.print()
        return

    console.print()
    # 渲染带颜色的 diff（仅对编辑场景，展示局部修改）
    formatted = format_diff_for_display(diff_text)
    if formatted:
        console.print(formatted)
    console.print()
