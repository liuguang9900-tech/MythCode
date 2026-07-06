"""
/branch — Git 分支管理命令。
支持创建、切换、删除、列表等操作。
"""

from commands.base import BaseCommand
from ui.console import console, print_error, print_info, print_success
from utils.git_utils import GitHelper


class BranchCommand(BaseCommand):
    name = "branch"
    description = "Git 分支管理（list/create/switch/delete/merge）"
    usage = """\
/branch                 # 列出本地分支
/branch list [-r]       # 列出分支（-r 远程）
/branch create <name> [base]  # 创建并切换分支
/branch switch <name>   # 切换分支
/branch delete <name>   # 删除分支
/branch current         # 显示当前分支
"""

    async def execute(self, args: str, agent) -> None:
        git = GitHelper(agent.workspace_root)

        if not git.is_repo():
            print_error("当前目录不是 git 仓库")
            return

        parts = args.split()
        if not parts:
            # 默认列出本地分支
            self._list_branches(git, remote=False)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "list":
            remote = "-r" in rest
            self._list_branches(git, remote=remote)
        elif sub == "create":
            if not rest:
                print_info("用法: /branch create <name> [base]")
                return
            name = rest[0]
            base = rest[1] if len(rest) > 1 else None
            ok, msg = git.create_branch(name, base)
            if ok:
                print_success(msg)
            else:
                print_error(msg)
        elif sub in ("switch", "checkout", "co"):
            if not rest:
                print_info("用法: /branch switch <name>")
                return
            ok, msg = git.switch_branch(rest[0])
            if ok:
                print_success(msg)
            else:
                print_error(msg)
        elif sub in ("delete", "del", "rm"):
            if not rest:
                print_info("用法: /branch delete <name>")
                return
            ok, msg = git.delete_branch(rest[0], force="--force" in rest or "-f" in rest)
            if ok:
                print_success(msg)
            else:
                print_error(msg)
        elif sub in ("current", "curr"):
            branch = git.get_current_branch()
            if branch:
                console.print(f"[cyan]当前分支:[/cyan] {branch}")
            else:
                print_info("处于 detached HEAD 状态")
        else:
            # 直接作为分支名切换
            ok, msg = git.switch_branch(sub)
            if ok:
                print_success(msg)
            else:
                print_error(msg)

    def _list_branches(self, git: GitHelper, remote: bool = False) -> None:
        current = git.get_current_branch()
        branches = git.list_branches(remote=remote)
        if not branches:
            print_info("无分支")
            return
        console.print(f"[bold]{'远程' if remote else '本地'}分支:[/bold]")
        for b in branches:
            marker = "[green]*[/green] " if b == current else "  "
            console.print(f"{marker}{b}")
