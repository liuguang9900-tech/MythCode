"""
Git 工具集 — 封装常用 Git 操作，支持分支管理、合并、冲突解决。
"""

import subprocess
from pathlib import Path
from typing import Optional


class GitHelper:
    """Git 操作助手"""

    def __init__(self, workspace_root: str):
        self.workspace = Path(workspace_root).resolve()

    def _run(self, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
        """执行 git 命令，返回 (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True,
                cwd=str(self.workspace), timeout=timeout,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            return -1, "", "git not found"
        except subprocess.TimeoutExpired:
            return -2, "", f"git {' '.join(args)} timed out"

    def is_repo(self) -> bool:
        """检查是否为 git 仓库"""
        code, _, _ = self._run(["rev-parse", "--is-inside-work-tree"])
        return code == 0

    def get_current_branch(self) -> Optional[str]:
        """获取当前分支名"""
        code, out, _ = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        if code == 0 and out and out != "HEAD":
            return out
        return None

    def list_branches(self, remote: bool = False) -> list[str]:
        """列出分支"""
        args = ["branch", "--list"]
        if remote:
            args.append("-r")
        code, out, _ = self._run(args)
        if code != 0:
            return []
        branches = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # 当前分支前缀 "* "
            if line.startswith("* "):
                line = line[2:]
            branches.append(line)
        return branches

    def create_branch(self, name: str, base: Optional[str] = None) -> tuple[bool, str]:
        """创建分支"""
        args = ["checkout", "-b", name]
        if base:
            args.append(base)
        code, out, err = self._run(args)
        if code == 0:
            return True, f"已创建并切换到分支 {name}"
        return False, err or out or "创建分支失败"

    def switch_branch(self, name: str) -> tuple[bool, str]:
        """切换分支"""
        code, out, err = self._run(["checkout", name])
        if code == 0:
            return True, f"已切换到分支 {name}"
        return False, err or out or "切换分支失败"

    def delete_branch(self, name: str, force: bool = False) -> tuple[bool, str]:
        """删除分支"""
        flag = "-D" if force else "-d"
        code, out, err = self._run(["branch", flag, name])
        if code == 0:
            return True, f"已删除分支 {name}"
        return False, err or out or "删除分支失败"

    def merge_branch(self, source: str, no_ff: bool = True) -> tuple[bool, str]:
        """合并分支"""
        args = ["merge", source]
        if no_ff:
            args.insert(1, "--no-ff")
        code, out, err = self._run(args)
        if code == 0:
            return True, out or f"已合并 {source}"
        return False, err or out or "合并失败"

    def has_conflicts(self) -> bool:
        """检查当前是否有合并冲突"""
        code, out, _ = self._run(["diff", "--name-only", "--diff-filter=U"])
        return code == 0 and bool(out)

    def list_conflicted_files(self) -> list[str]:
        """列出冲突文件"""
        code, out, _ = self._run(["diff", "--name-only", "--diff-filter=U"])
        if code != 0 or not out:
            return []
        return [f for f in out.splitlines() if f]

    def abort_merge(self) -> tuple[bool, str]:
        """中止合并"""
        code, out, err = self._run(["merge", "--abort"])
        if code == 0:
            return True, "已中止合并"
        return False, err or "中止合并失败"

    def resolve_conflict(self, file_path: str, resolution: str = "ours") -> tuple[bool, str]:
        """
        解决冲突文件
        resolution: ours/theirs/none（手动编辑后标记）
        """
        if resolution == "ours":
            code, out, err = self._run(["checkout", "--ours", file_path])
        elif resolution == "theirs":
            code, out, err = self._run(["checkout", "--theirs", file_path])
        else:
            code, out, err = 0, "", ""

        if code != 0:
            return False, err or "解决冲突失败"

        # 标记为已解决
        code, out, err = self._run(["add", file_path])
        if code == 0:
            return True, f"已解决冲突: {file_path} ({resolution})"
        return False, err or "标记解决失败"

    def get_status(self) -> str:
        """获取 git status 输出"""
        code, out, _ = self._run(["status"])
        return out if code == 0 else ""

    def get_log(self, count: int = 10, oneline: bool = True) -> str:
        """获取 git log"""
        args = ["log"]
        if oneline:
            args.append("--oneline")
        args.append(f"-{count}")
        code, out, _ = self._run(args)
        return out if code == 0 else ""

    def stash(self, message: Optional[str] = None) -> tuple[bool, str]:
        """暂存当前更改"""
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        code, out, err = self._run(args)
        if code == 0:
            return True, out or "已暂存"
        return False, err or "暂存失败"

    def stash_pop(self) -> tuple[bool, str]:
        """恢复暂存的更改"""
        code, out, err = self._run(["stash", "pop"])
        if code == 0:
            return True, out or "已恢复暂存"
        return False, err or "恢复暂存失败"

    def stash_list(self) -> list[str]:
        """列出暂存"""
        code, out, _ = self._run(["stash", "list"])
        if code != 0 or not out:
            return []
        return out.splitlines()

    def create_pr(
        self,
        title: str,
        body: str,
        base: str = "main",
        head: Optional[str] = None,
        web: bool = False,
    ) -> tuple[bool, str]:
        """使用 gh CLI 创建 PR"""
        args = ["pr", "create", "--title", title, "--body", body, "--base", base]
        if head:
            args.extend(["--head", head])
        if web:
            args.append("--web")

        code, out, err = self._run(args, timeout=60)
        if code == 0:
            return True, out or "PR 已创建"
        return False, err or out or "创建 PR 失败（请确认已安装 gh CLI 并登录）"

    def get_remotes(self) -> list[str]:
        """获取远程仓库列表"""
        code, out, _ = self._run(["remote", "-v"])
        if code != 0 or not out:
            return []
        return out.splitlines()

    def fetch(self, remote: str = "origin") -> tuple[bool, str]:
        """拉取远程"""
        code, out, err = self._run(["fetch", remote], timeout=60)
        if code == 0:
            return True, "已拉取"
        return False, err or "拉取失败"

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> tuple[bool, str]:
        """拉取并合并"""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        code, out, err = self._run(args, timeout=60)
        if code == 0:
            return True, out or "已拉取"
        return False, err or out or "拉取失败"

    def push(self, remote: str = "origin", branch: Optional[str] = None, set_upstream: bool = False) -> tuple[bool, str]:
        """推送"""
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.append(remote)
        if branch:
            args.append(branch)
        code, out, err = self._run(args, timeout=60)
        if code == 0:
            return True, out or "已推送"
        return False, err or out or "推送失败"
