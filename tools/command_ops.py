"""
命令执行工具：Execute_Command（Bash/Zsh）
"""

import asyncio
import os
import platform
from pathlib import Path

from tools.base import BaseTool, ToolResult
from tools.sandbox import get_sandbox
from config import get_config


class ExecuteCommandTool(BaseTool):
    """执行终端命令并捕获输出"""

    name = "execute_command"
    description = "执行 shell 命令并返回输出（非交互式，超时 120s，输出超 100000 字符截断）。"
    parameters = {
        "command": {
            "type": "string",
            "description": "要执行的 shell 命令",
            "required": True,
        },
        "working_dir": {
            "type": "string",
            "description": "工作目录，默认项目根",
            "required": False,
        },
    }

    async def execute(
        self, command: str, working_dir: str = ""
    ) -> ToolResult:
        sandbox = get_sandbox()
        cfg = get_config()

        # 安全检查
        is_safe, reason = sandbox.check_command(command)
        if not is_safe:
            return ToolResult(
                success=False,
                output="",
                error=f"命令需要用户确认: {reason}",
                metadata={"requires_approval": True, "command": command, "reason": reason},
            )

        # 确定工作目录
        if working_dir:
            try:
                cwd = sandbox.resolve_path(working_dir)
            except PermissionError as e:
                return ToolResult(success=False, output="", error=str(e))
        else:
            cwd = sandbox.project_root

        if not cwd.exists():
            return ToolResult(
                success=False, output="", error=f"工作目录不存在: {cwd}"
            )

        try:
            # 根据平台选择 shell
            shell_cmd = _get_shell_command()

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                executable=shell_cmd,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=cfg.tools.command_timeout
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # 截断过长输出
            max_out = cfg.tools.command_max_output
            if len(stdout_str) > max_out:
                stdout_str = stdout_str[:max_out] + f"\n... (输出被截断，共 {len(stdout_str)} 字符)"
            if len(stderr_str) > max_out:
                stderr_str = stderr_str[:max_out] + f"\n... (stderr 被截断，共 {len(stderr_str)} 字符)"

            output_parts = []
            if stdout_str:
                output_parts.append(stdout_str.rstrip())
            if stderr_str:
                output_parts.append(f"[stderr]\n{stderr_str.rstrip()}")

            output = "\n".join(output_parts) if output_parts else "(无输出)"

            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=f"命令退出码: {process.returncode}" if process.returncode != 0 else None,
                metadata={
                    "exit_code": process.returncode,
                    "cwd": str(cwd),
                    "stdout_len": len(stdout_str),
                    "stderr_len": len(stderr_str),
                },
            )

        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return ToolResult(
                success=False,
                output="",
                error=f"命令执行超时 ({cfg.tools.command_timeout}s): {command}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"命令执行异常: {e}"
            )


def _get_shell_command() -> str:
    """获取当前平台的 shell 可执行文件路径"""
    system = platform.system()
    if system == "Windows":
        return os.environ.get("COMSPEC", "cmd.exe")
    # macOS / Linux: 优先使用用户的默认 shell
    return os.environ.get("SHELL", "/bin/bash")
