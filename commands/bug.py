"""
/bug — 报告错误：收集上下文并生成 bug 报告。
"""

import subprocess
import platform
from pathlib import Path
from commands.base import BaseCommand
from ui.console import console, print_error


class BugCommand(BaseCommand):
    name = "bug"
    description = "收集上下文并生成 bug 报告"

    async def execute(self, args: str, agent) -> None:
        console.print("[dim]正在收集系统信息...[/dim]")

        info = {
            "version": "0.1.0",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "workspace": str(agent.workspace_root),
            "model": f"{agent.cfg.model.provider}/{agent.cfg.model.name}",
            "messages_count": len(agent.memory.messages),
            "steps_count": agent.session_map.current_step_id,
        }

        # Git 信息
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-3"],
                capture_output=True, text=True,
                cwd=str(agent.workspace_root), timeout=5
            )
            info["recent_commits"] = result.stdout.strip()
        except Exception:
            info["recent_commits"] = "N/A"

        # 最近对话
        recent_msgs = []
        for msg in agent.memory.messages[-6:]:
            role = msg.get("role", "?")
            content = str(msg.get("content", ""))[:200]
            recent_msgs.append(f"[{role}] {content}")
        info["recent_messages"] = "\n".join(recent_msgs)

        # 生成报告
        report = f"""## Bug Report

**版本**: {info['version']}
**平台**: {info['platform']}
**Python**: {info['python']}
**工作目录**: {info['workspace']}
**模型**: {info['model']}
**消息数**: {info['messages_count']}
**步骤数**: {info['steps_count']}

### 最近提交
{info['recent_commits']}

### 最近对话
{info['recent_messages']}

### 问题描述
<!-- 请在此描述你遇到的问题 -->

### 期望行为
<!-- 请描述你期望的行为 -->

### 复现步骤
1. 
2. 
3. 
"""

        # 保存到文件
        report_path = Path(agent.workspace_root) / "BUG_REPORT.md"
        report_path.write_text(report, encoding="utf-8")

        console.print()
        console.print(f"[green]Bug 报告模板已生成:[/green] {report_path}")
        console.print("[dim]请编辑此文件补充问题描述后提交[/dim]")
