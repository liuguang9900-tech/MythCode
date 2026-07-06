"""
/merge — Git 合并命令，支持冲突检测和解决。
"""

from commands.base import BaseCommand
from ui.console import console, print_error, print_info, print_success, print_warning
from utils.git_utils import GitHelper


class MergeCommand(BaseCommand):
    name = "merge"
    description = "Git 合并分支，支持冲突解决"
    usage = """\
/merge <source>             # 合并 source 分支到当前分支
/merge <source> --ff        # 快进合并
/merge abort                # 中止合并
/merge status               # 查看合并状态/冲突文件
/merge resolve <file> ours  # 解决冲突（ours/theirs）
/merge resolve --all ours   # 批量解决所有冲突
/merge continue             # 提交合并（解决完冲突后）
"""

    async def execute(self, args: str, agent) -> None:
        git = GitHelper(agent.workspace_root)

        if not git.is_repo():
            print_error("当前目录不是 git 仓库")
            return

        parts = args.split()
        if not parts:
            print_info("用法: /merge <source>")
            return

        sub = parts[0]

        if sub == "abort":
            ok, msg = git.abort_merge()
            if ok:
                print_success(msg)
            else:
                print_error(msg)
            return

        if sub == "status":
            self._show_status(git)
            return

        if sub == "resolve":
            self._resolve(git, parts[1:])
            return

        if sub == "continue":
            self._continue_merge(git)
            return

        # 默认：合并分支
        no_ff = "--ff" not in parts and "--ff-only" not in parts
        ok, msg = git.merge_branch(sub, no_ff=no_ff)
        if ok:
            print_success(msg)
        else:
            print_error(msg)
            if git.has_conflicts():
                print_warning("存在冲突文件：")
                for f in git.list_conflicted_files():
                    console.print(f"  [yellow]{f}[/yellow]")
                console.print("\n[dim]使用 /merge resolve <file> ours|theirs 解决冲突[/dim]")
                console.print("[dim]使用 /merge abort 中止合并[/dim]")

    def _show_status(self, git: GitHelper) -> None:
        if git.has_conflicts():
            print_warning("当前存在合并冲突：")
            for f in git.list_conflicted_files():
                console.print(f"  [yellow]{f}[/yellow]")
        else:
            current = git.get_current_branch() or "HEAD"
            print_info(f"当前分支: {current}，无合并冲突")
            console.print("\n[dim]最近提交:[/dim]")
            console.print(git.get_log(count=5))

    def _resolve(self, git: GitHelper, args: list[str]) -> None:
        if not args:
            print_info("用法: /merge resolve <file> ours|theirs")
            return

        # /merge resolve --all ours
        if args[0] == "--all":
            resolution = args[1] if len(args) > 1 else "ours"
            files = git.list_conflicted_files()
            if not files:
                print_info("无冲突文件")
                return
            success_count = 0
            for f in files:
                ok, msg = git.resolve_conflict(f, resolution)
                if ok:
                    success_count += 1
                    console.print(f"  [green]✓[/green] {f}")
                else:
                    console.print(f"  [red]✗[/red] {f}: {msg}")
            print_success(f"已解决 {success_count}/{len(files)} 个冲突")
            if success_count == len(files):
                console.print("[dim]使用 /merge continue 提交合并[/dim]")
            return

        # /merge resolve <file> ours|theirs
        file_path = args[0]
        resolution = args[1] if len(args) > 1 else "ours"
        if resolution not in ("ours", "theirs", "none"):
            print_error("resolution 必须是 ours/theirs/none")
            return
        ok, msg = git.resolve_conflict(file_path, resolution)
        if ok:
            print_success(msg)
        else:
            print_error(msg)

    def _continue_merge(self, git: GitHelper) -> None:
        if git.has_conflicts():
            print_error("仍有未解决的冲突，请先解决所有冲突")
            for f in git.list_conflicted_files():
                console.print(f"  [yellow]{f}[/yellow]")
            return
        # git commit 完成合并
        import subprocess
        try:
            result = subprocess.run(
                ["git", "commit", "--no-edit"],
                cwd=str(git.workspace),
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                print_success("合并已完成")
            else:
                # 可能没有正在进行的合并
                if "no merge in progress" in result.stderr.lower():
                    print_info("无进行中的合并")
                else:
                    print_error(result.stderr or result.stdout)
        except Exception as e:
            print_error(f"提交合并失败: {e}")
