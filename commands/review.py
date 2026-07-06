"""
/review — 代码审查（对 git diff 进行分析）。
/security-review — 安全审查（OWASP 检查）。
"""

import subprocess
from pathlib import Path
from commands.base import BaseCommand
from ui.console import console, print_error, print_info


class ReviewCommand(BaseCommand):
    name = "review"
    description = "代码审查：分析 git diff 并提供审查意见"

    async def execute(self, args: str, agent) -> None:
        workspace = Path(agent.workspace_root)

        # 获取 git diff
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            staged = result.stdout.strip()

            result = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            unstaged = result.stdout.strip()

            diff = staged or unstaged
            if not diff:
                print_info("没有待审查的更改（git diff 为空）")
                return

        except FileNotFoundError:
            print_error("未找到 git，请确保 git 已安装")
            return
        except subprocess.TimeoutExpired:
            print_error("git diff 超时")
            return

        # 截断过大的 diff
        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (diff 已截断)"

        console.print("[dim]正在分析代码变更...[/dim]")

        prompt = f"""请对以下 git diff 进行代码审查。关注：
1. 潜在的 bug 或逻辑错误
2. 安全漏洞
3. 性能问题
4. 代码风格和可读性
5. 是否有遗漏的边界情况

用中文回复，简洁明了。如果没有发现问题，直接说"代码变更看起来不错"。

```diff
{diff}
```"""

        try:
            response = await agent.llm.chat_simple(
                system="你是一个资深代码审查专家。请用中文回复。",
                user=prompt,
            )
            console.print()
            console.print("[bold]📋 代码审查结果[/bold]")
            console.print()
            console.print(response)
            console.print()
        except Exception as e:
            print_error(f"代码审查失败: {e}")


class SecurityReviewCommand(BaseCommand):
    name = "security-review"
    description = "安全审查：检查代码中的安全漏洞"

    async def execute(self, args: str, agent) -> None:
        workspace = Path(agent.workspace_root)

        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            staged = result.stdout.strip()

            result = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            unstaged = result.stdout.strip()

            diff = staged or unstaged
            if not diff:
                print_info("没有待审查的更改")
                return

        except FileNotFoundError:
            print_error("未找到 git")
            return
        except subprocess.TimeoutExpired:
            print_error("git diff 超时")
            return

        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (diff 已截断)"

        console.print("[dim]正在进行安全审查...[/dim]")

        prompt = f"""请对以下代码变更进行安全审查。重点检查 OWASP Top 10 相关漏洞：
1. 注入漏洞（SQL、命令、模板注入）
2. 认证和授权问题
3. 敏感数据泄露（密钥、密码、Token）
4. XSS 漏洞
5. 不安全的反序列化
6. 路径遍历
7. 不安全的依赖

用中文回复。如果没有安全问题，直接说"未发现安全漏洞"。

```diff
{diff}
```"""

        try:
            response = await agent.llm.chat_simple(
                system="你是一个资深应用安全专家。请用中文回复。",
                user=prompt,
            )
            console.print()
            console.print("[bold red]🔒 安全审查结果[/bold red]")
            console.print()
            console.print(response)
            console.print()
        except Exception as e:
            print_error(f"安全审查失败: {e}")
