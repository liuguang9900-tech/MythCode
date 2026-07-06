"""
/commit — 自动生成 commit message 并提交。
/commit --amend    # 修改最近一次 commit
/commit --fixup <hash>  # 创建 fixup 提交
/pr — 生成 PR 描述，可选 --create 直接通过 gh CLI 创建 PR。
"""

import subprocess
from pathlib import Path
from commands.base import BaseCommand
from ui.console import console, print_error, print_info, print_success
from utils.git_utils import GitHelper


class CommitCommand(BaseCommand):
    name = "commit"
    description = "自动生成 commit message 并提交（支持 --amend/--fixup）"
    usage = """\
/commit                # 自动生成并提交
/commit --amend        # 修改最近一次 commit message
/commit --fixup <hash> # 创建 fixup 提交
"""

    async def execute(self, args: str, agent) -> None:
        workspace = Path(agent.workspace_root)
        git = GitHelper(agent.workspace_root)

        # 解析参数
        is_amend = "--amend" in args
        fixup_hash = None
        if "--fixup" in args:
            parts = args.split()
            idx = parts.index("--fixup")
            if idx + 1 < len(parts):
                fixup_hash = parts[idx + 1]

        # 获取 staged diff
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            diff = result.stdout.strip()
            if not diff:
                # 尝试 unstaged
                result = subprocess.run(
                    ["git", "diff"],
                    capture_output=True, text=True, cwd=str(workspace), timeout=10
                )
                diff = result.stdout.strip()
                if not diff:
                    print_info("没有待提交的更改")
                    return
                console.print("[yellow]没有 staged 的更改，将使用 unstaged diff[/yellow]")

        except FileNotFoundError:
            print_error("未找到 git")
            return
        except subprocess.TimeoutExpired:
            print_error("git diff 超时")
            return

        if len(diff) > 6000:
            diff = diff[:6000] + "\n... (diff 已截断)"

        # 获取最近 commit 风格
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True, text=True, cwd=str(workspace), timeout=5
            )
            recent_commits = result.stdout.strip()
        except Exception:
            recent_commits = ""

        console.print("[dim]正在生成 commit message...[/dim]")

        # 根据模式构建 prompt
        if is_amend:
            # 获取最近一次 commit message
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%B"],
                    capture_output=True, text=True, cwd=str(workspace), timeout=5
                )
                last_msg = result.stdout.strip()
            except Exception:
                last_msg = ""

            prompt = f"""请为以下 git diff 生成一个规范的 commit message（用于 amend）。

原 commit message:
{last_msg}

参考最近的 commit 风格：
{recent_commits if recent_commits else '无历史记录'}

要求：
- 使用中文
- 格式：<类型>: <简短描述>
- 类型：feat(新功能), fix(修复), refactor(重构), docs(文档), style(格式), test(测试), chore(构建)
- 描述不超过 50 字

```diff
{diff}
```

只输出 commit message，不要加额外说明。"""
        elif fixup_hash:
            prompt = f"""请为以下 git diff 生成一个 fixup commit message。

参考最近的 commit 风格：
{recent_commits if recent_commits else '无历史记录'}

要求：
- 使用中文
- 格式：<类型>: <简短描述>
- 类型：feat(新功能), fix(修复), refactor(重构), docs(文档), style(格式), test(测试), chore(构建)
- 描述不超过 50 字

```diff
{diff}
```

只输出 commit message，不要加额外说明。"""
        else:
            prompt = f"""请为以下 git diff 生成一个规范的 commit message。

参考最近的 commit 风格：
{recent_commits if recent_commits else '无历史记录'}

要求：
- 使用中文
- 格式：<类型>: <简短描述>
- 类型：feat(新功能), fix(修复), refactor(重构), docs(文档), style(格式), test(测试), chore(构建)
- 描述不超过 50 字
- 如果需要，可以在第二行空行后添加详细说明

```diff
{diff}
```

只输出 commit message，不要加额外说明。"""

        try:
            commit_msg = await agent.llm.chat_simple(
                system="你是一个专业的 Git 提交信息撰写助手。",
                user=prompt,
            )
            commit_msg = commit_msg.strip().strip("`").strip()

            console.print()
            console.print("[bold]生成的 commit message:[/bold]")
            console.print(f"  [cyan]{commit_msg}[/cyan]")
            console.print()

            # 确认
            try:
                confirm = input("  是否提交? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]已取消[/dim]")
                return

            if confirm not in ("y", "yes", "是"):
                print_info("已取消提交")
                return

            # 执行 git add 和 commit
            subprocess.run(["git", "add", "-A"], cwd=str(workspace), check=True)

            if is_amend:
                subprocess.run(
                    ["git", "commit", "--amend", "-m", commit_msg],
                    cwd=str(workspace), check=True
                )
                print_success("已 amend 最近一次提交!")
            elif fixup_hash:
                subprocess.run(
                    ["git", "commit", "--fixup", fixup_hash, "-m", commit_msg],
                    cwd=str(workspace), check=True
                )
                print_success(f"已创建 fixup 提交（针对 {fixup_hash}）!")
            else:
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=str(workspace), check=True
                )
                print_success("提交成功!")

        except subprocess.CalledProcessError as e:
            print_error(f"Git 操作失败: {e}")
        except Exception as e:
            print_error(f"生成 commit message 失败: {e}")


class PRCommand(BaseCommand):
    name = "pr"
    description = "生成 Pull Request 描述（--create 直接创建）"
    usage = """\
/pr                # 生成 PR 描述
/pr --create       # 使用 gh CLI 创建 PR
/pr --create --base develop  # 指定目标分支
"""

    async def execute(self, args: str, agent) -> None:
        workspace = Path(agent.workspace_root)
        git = GitHelper(agent.workspace_root)

        create_pr = "--create" in args
        base = "main"
        if "--base" in args:
            parts = args.split()
            idx = parts.index("--base")
            if idx + 1 < len(parts):
                base = parts[idx + 1]

        # 获取与 base 分支的 diff
        try:
            # 先尝试 origin/<base>...HEAD
            result = subprocess.run(
                ["git", "diff", f"origin/{base}...HEAD"],
                capture_output=True, text=True, cwd=str(workspace), timeout=10
            )
            diff = result.stdout.strip()
            if not diff:
                # 尝试 <base>...HEAD
                result = subprocess.run(
                    ["git", "diff", f"{base}...HEAD"],
                    capture_output=True, text=True, cwd=str(workspace), timeout=10
                )
                diff = result.stdout.strip()
            if not diff:
                # 尝试 HEAD~1
                result = subprocess.run(
                    ["git", "diff", "HEAD~1"],
                    capture_output=True, text=True, cwd=str(workspace), timeout=10
                )
                diff = result.stdout.strip()

            if not diff:
                print_info("没有可比较的更改")
                return

            # 获取 commit log
            log_ref = f"origin/{base}...HEAD"
            result = subprocess.run(
                ["git", "log", "--oneline", log_ref],
                capture_output=True, text=True, cwd=str(workspace), timeout=5
            )
            commits = result.stdout.strip()
            if not commits:
                result = subprocess.run(
                    ["git", "log", "--oneline", "HEAD~5..HEAD"],
                    capture_output=True, text=True, cwd=str(workspace), timeout=5
                )
                commits = result.stdout.strip()

        except FileNotFoundError:
            print_error("未找到 git")
            return
        except subprocess.TimeoutExpired:
            print_error("git 操作超时")
            return

        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (diff 已截断)"

        console.print("[dim]正在生成 PR 描述...[/dim]")

        prompt = f"""请为以下代码变更生成一个 Pull Request 描述。

## 提交记录
{commits if commits else '无'}

## 代码变更
```diff
{diff}
```

请生成包含以下内容的 PR 描述（中文，Markdown 格式）：
1. **概述**：简要说明本次变更的目的
2. **主要变更**：列出关键改动
3. **测试**：建议的测试方式
4. **注意事项**：需要 reviewer 关注的点

直接输出 PR 描述内容。"""

        try:
            response = await agent.llm.chat_simple(
                system="你是一个专业的 PR 描述撰写助手。",
                user=prompt,
            )
            # 提取标题（第一行）
            lines = response.strip().splitlines()
            title = ""
            for line in lines:
                stripped = line.strip().lstrip("#").strip()
                if stripped and not stripped.startswith("**"):
                    title = stripped
                    break
            if not title:
                title = f"PR: {git.get_current_branch() or 'changes'}"

            console.print()
            console.print("[bold]PR 描述[/bold]")
            console.print()
            console.print(response)
            console.print()

            if create_pr:
                # 询问确认
                try:
                    confirm = input("\n  是否创建 PR? (y/n): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    return
                if confirm not in ("y", "yes", "是"):
                    print_info("已取消创建 PR")
                    return

                head = git.get_current_branch()
                ok, msg = git.create_pr(
                    title=title,
                    body=response,
                    base=base,
                    head=head,
                )
                if ok:
                    print_success(f"PR 已创建: {msg}")
                else:
                    print_error(msg)
                    console.print("[dim]提示：请确认已安装 gh CLI 并执行 gh auth login[/dim]")

        except Exception as e:
            print_error(f"生成 PR 描述失败: {e}")
