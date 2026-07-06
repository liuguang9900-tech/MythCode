"""
/doctor — 诊断配置、LLM 连接、工具可用性。
"""

import sys
import asyncio
from pathlib import Path
from commands.base import BaseCommand
from ui.console import console


class DoctorCommand(BaseCommand):
    name = "doctor"
    description = "诊断系统配置和连接状态"

    async def execute(self, args: str, agent) -> None:
        console.print()
        console.print("[bold]🔍 MythCoder 系统诊断[/bold]")
        console.print()

        issues = []
        ok_count = 0
        warn_count = 0

        # 1. Python 版本
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 10):
            console.print(f"  [green]✓[/green] Python 版本: {py_ver}")
            ok_count += 1
        else:
            console.print(f"  [red]✗[/red] Python 版本: {py_ver} (需要 >= 3.10)")
            issues.append("Python 版本过低")

        # 2. 配置文件
        config_path = Path(agent.workspace_root) / "config.yaml"
        if config_path.exists():
            console.print(f"  [green]✓[/green] 配置文件: {config_path}")
            ok_count += 1
        else:
            console.print(f"  [yellow]![/yellow] 配置文件不存在: {config_path}")
            warn_count += 1

        # 2.1 API Key 检查
        import os
        api_key = agent.cfg.model.api_key or ""
        if api_key and not api_key.startswith("${"):
            # 已解析出实际 key（可能是环境变量已设置）
            console.print(f"  [green]✓[/green] API Key: 已配置 ({agent.cfg.model.provider})")
            ok_count += 1
        elif os.getenv("MYTHCODER_API_KEY"):
            console.print(f"  [green]✓[/green] API Key: 从环境变量 MYTHCODER_API_KEY 读取")
            ok_count += 1
        else:
            console.print(f"  [red]✗[/red] API Key: 未配置（请设置环境变量 MYTHCODER_API_KEY）")
            issues.append("API Key 未配置：请 export MYTHCODER_API_KEY=sk-xxx")

        # 3. LLM 连接
        console.print("  [dim]…[/dim] 正在测试 LLM 连接...")
        try:
            response = await agent.llm.chat_simple(
                system="你是一个助手。",
                user="回复 'pong'",
                max_tokens=10,
            )
            if response:
                console.print(f"  [green]✓[/green] LLM 连接正常 ({agent.cfg.model.provider}/{agent.cfg.model.name})")
                ok_count += 1
            else:
                console.print(f"  [yellow]![/yellow] LLM 返回空响应")
                warn_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] LLM 连接失败: {e}")
            issues.append(f"LLM 连接失败: {e}")

        # 4. 工具可用性
        from tools.registry import registry as tool_registry
        tools = tool_registry.list_tools()
        console.print(f"  [green]✓[/green] 已注册工具: {len(tools)} 个 ({', '.join(t.name for t in tools)})")
        ok_count += 1

        # 5. 工作目录
        workspace = Path(agent.workspace_root)
        if workspace.exists():
            console.print(f"  [green]✓[/green] 工作目录: {workspace}")
            ok_count += 1
        else:
            console.print(f"  [red]✗[/red] 工作目录不存在: {workspace}")
            issues.append("工作目录不存在")

        # 6. Git
        git_dir = workspace / ".git"
        if git_dir.exists():
            console.print(f"  [green]✓[/green] Git 仓库: 已初始化")
            ok_count += 1
        else:
            console.print(f"  [dim]○[/dim] Git 仓库: 未检测到")
            warn_count += 1

        # 7. ripgrep
        import shutil
        if shutil.which("rg"):
            console.print(f"  [green]✓[/green] ripgrep: 已安装")
            ok_count += 1
        else:
            console.print(f"  [dim]○[/dim] ripgrep: 未安装 (将使用 Python fallback)")
            warn_count += 1

        # 8. 磁盘空间
        try:
            import shutil
            usage = shutil.disk_usage(workspace)
            free_gb = usage.free / (1024 ** 3)
            if free_gb > 1:
                console.print(f"  [green]✓[/green] 磁盘可用空间: {free_gb:.1f} GB")
                ok_count += 1
            else:
                console.print(f"  [yellow]![/yellow] 磁盘可用空间不足: {free_gb:.1f} GB")
                warn_count += 1
        except Exception:
            pass

        # 9. 持久化目录
        persist_dir = workspace / ".mythcoder"
        if persist_dir.exists():
            console.print(f"  [green]✓[/green] 持久化目录: {persist_dir}")
            ok_count += 1
        else:
            console.print(f"  [dim]○[/dim] 持久化目录: 尚未创建")
            warn_count += 1

        # 总结
        console.print()
        total = ok_count + warn_count + len(issues)
        console.print(f"[bold]诊断结果:[/bold] {ok_count}/{total} 通过", end="")
        if warn_count > 0:
            console.print(f", {warn_count} 警告", end="")
        if issues:
            console.print(f", {len(issues)} 错误")
            console.print()
            console.print("[bold red]需要修复的问题:[/bold red]")
            for issue in issues:
                console.print(f"  • {issue}")
        else:
            console.print()
        console.print()
