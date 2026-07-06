"""
事件钩子系统 — 在关键事件点执行用户自定义脚本。

钩子类型：
  - PreToolUse: 工具执行前触发，可阻止执行
  - PostToolUse: 工具执行后触发
  - Notification: 通知事件（会话开始/结束等）
  - UserPromptSubmit: 用户提交输入时触发

钩子脚本位置：.claude/hooks/
  - pre_tool_use.py    (或 .sh)
  - post_tool_use.py   (或 .sh)
  - notification.py    (或 .sh)

脚本通过 stdin 接收 JSON 事件数据，stdout 输出 JSON 结果。
PreToolUse 钩子返回 {"continue": false} 可阻止工具执行。
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Any


class HookManager:
    """事件钩子管理器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.hooks_dir = self.workspace_root / ".claude" / "hooks"
        self._enabled = True
        self._timeout = 30  # 钩子脚本超时秒数
        self._config_hooks: list[dict] = []  # 来自 settings.json 的钩子配置

    def disable(self) -> None:
        """禁用所有钩子"""
        self._enabled = False

    def enable(self) -> None:
        """启用钩子"""
        self._enabled = True

    def load_from_settings(self, settings_manager) -> None:
        """
        从 SettingsManager 加载钩子配置。

        配置格式（settings.json）：
        {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "write_file", "command": "python3 lint.py", "timeout": 10}
                ],
                "PostToolUse": [
                    {"matcher": "edit_file", "command": "python3 format.py"}
                ]
            }
        }
        """
        hooks_config = settings_manager.get("hooks", {}) or {}
        event_map = {
            "pretooluse": "pre_tool_use",
            "posttooluse": "post_tool_use",
            "notification": "notification",
            "userpromptsubmit": "user_prompt_submit",
            "sessionstart": "notification",
            "sessionend": "notification",
        }

        for event_name, hooks_list in hooks_config.items():
            normalized = event_name.lower().replace("_", "")
            hook_event = event_map.get(normalized, event_name.lower())
            if not isinstance(hooks_list, list):
                continue
            for hook in hooks_list:
                if not isinstance(hook, dict) or "command" not in hook:
                    continue
                self._config_hooks.append({
                    "event": hook_event,
                    "matcher": hook.get("matcher", "*"),
                    "command": hook["command"],
                    "timeout": hook.get("timeout", 30),
                })

    # ============================================================
    # 事件触发方法
    # ============================================================

    async def on_pre_tool_use(
        self, tool_name: str, tool_args: dict
    ) -> tuple[bool, Optional[str]]:
        """
        工具执行前触发。

        Returns:
            (allowed, message): allowed=False 表示阻止执行，message 为阻止原因
        """
        # 脚本钩子
        result = await self._run_hook("pre_tool_use", {
            "event": "pre_tool_use",
            "tool_name": tool_name,
            "tool_args": tool_args,
        })
        if isinstance(result, dict):
            if result.get("continue") is False:
                return False, result.get("message", "钩子阻止了工具执行")

        # 配置钩子
        for hook in self._config_hooks:
            if hook["event"] != "pre_tool_use":
                continue
            if not self._match_hook(hook["matcher"], tool_name, tool_args):
                continue
            hook_result = await self._run_config_hook(hook, {
                "event": "pre_tool_use",
                "tool_name": tool_name,
                "tool_args": tool_args,
            })
            if isinstance(hook_result, dict) and hook_result.get("continue") is False:
                return False, hook_result.get("message", "配置钩子阻止了工具执行")

        return True, None

    async def on_post_tool_use(
        self, tool_name: str, tool_args: dict, result: dict
    ) -> None:
        """工具执行后触发"""
        # 脚本钩子
        await self._run_hook("post_tool_use", {
            "event": "post_tool_use",
            "tool_name": tool_name,
            "tool_args": tool_args,
            "result": result,
        })

        # 配置钩子
        for hook in self._config_hooks:
            if hook["event"] != "post_tool_use":
                continue
            if not self._match_hook(hook["matcher"], tool_name, tool_args):
                continue
            await self._run_config_hook(hook, {
                "event": "post_tool_use",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "result": result,
            })

    async def on_notification(self, event_type: str, data: Optional[dict] = None) -> None:
        """
        通知事件触发。

        Args:
            event_type: 事件类型，如 "session_start", "session_end"
            data: 附加数据
        """
        await self._run_hook("notification", {
            "event": "notification",
            "type": event_type,
            "data": data or {},
        })

    async def on_user_prompt_submit(self, user_input: str) -> Optional[str]:
        """
        用户提交输入时触发。

        Returns:
            修改后的输入文本，None 表示不修改
        """
        result = await self._run_hook("user_prompt_submit", {
            "event": "user_prompt_submit",
            "input": user_input,
        })
        if result and isinstance(result, dict) and "input" in result:
            return result["input"]
        return None

    # ============================================================
    # 内部方法
    # ============================================================

    async def _run_hook(self, hook_name: str, event_data: dict) -> Any:
        """
        执行钩子脚本。

        Args:
            hook_name: 钩子名称（对应脚本文件名前缀）
            event_data: 通过 stdin 传递给脚本的 JSON 数据

        Returns:
            脚本 stdout 输出的 JSON 解析结果，或 None
        """
        if not self._enabled:
            return None

        script_path = self._find_script(hook_name)
        if script_path is None:
            return None

        event_json = json.dumps(event_data, ensure_ascii=False)

        try:
            if script_path.suffix == ".py":
                args_list = ["python3", str(script_path)]
            elif script_path.suffix == ".sh":
                args_list = ["bash", str(script_path)]
            else:
                args_list = [str(script_path)]

            proc = await asyncio.create_subprocess_exec(
                *args_list,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
                env={**os.environ, "MYTHCODER_WORKSPACE": str(self.workspace_root)},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(event_json.encode("utf-8")),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return None

            if proc.returncode != 0 and hook_name == "pre_tool_use":
                # PreToolUse 钩子非零退出 = 阻止执行
                stderr_msg = stderr.decode("utf-8", errors="ignore").strip()
                return {"continue": False, "message": stderr_msg or "钩子脚本返回非零退出码"}

            # 解析 stdout JSON
            stdout_text = stdout.decode("utf-8", errors="ignore").strip()
            if stdout_text:
                try:
                    return json.loads(stdout_text)
                except json.JSONDecodeError:
                    return stdout_text

            return None

        except (OSError, asyncio.CancelledError):
            return None

    def _find_script(self, hook_name: str) -> Optional[Path]:
        """查找钩子脚本文件"""
        if not self.hooks_dir.exists():
            return None

        for ext in (".py", ".sh"):
            script = self.hooks_dir / f"{hook_name}{ext}"
            if script.exists() and os.access(script, os.X_OK):
                return script
            # 也检查非可执行文件（Python 脚本不需要 +x）
            if script.exists() and ext == ".py":
                return script

        return None

    def _match_hook(self, matcher: str, tool_name: str, tool_args: dict) -> bool:
        """检查钩子匹配器是否匹配当前工具调用"""
        import fnmatch

        # 通配符
        if matcher == "*":
            return True

        # 工具名 glob 匹配
        if fnmatch.fnmatch(tool_name, matcher):
            return True

        # ToolName(arg_pattern) 格式
        if "(" in matcher and matcher.endswith(")"):
            rule_tool = matcher[:matcher.index("(")]
            if rule_tool != tool_name:
                return False
            arg_pattern = matcher[matcher.index("(") + 1:-1]
            if tool_args:
                args_str = str(tool_args)
                return arg_pattern in args_str or arg_pattern == "*"
            return False

        # Bash(command:*) 格式
        if ":" in matcher and tool_name == "execute_command":
            command = tool_args.get("command", "")
            prefix = matcher.split(":")[0]
            return command.startswith(prefix)

        return False

    async def _run_config_hook(self, hook: dict, event_data: dict) -> Optional[Any]:
        """执行配置中的钩子命令（安全实现：使用 shlex 分割，禁止 shell=True）"""
        if not self._enabled:
            return None

        command = hook["command"]
        timeout = hook.get("timeout", 30)
        event_json = json.dumps(event_data, ensure_ascii=False)

        try:
            import shlex
            args_list = shlex.split(command)
            if not args_list:
                return None

            proc = await asyncio.create_subprocess_exec(
                *args_list,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
                env={**os.environ, "MYTHCODER_WORKSPACE": str(self.workspace_root)},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(event_json.encode("utf-8")),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return None

            if proc.returncode != 0 and hook["event"] == "pre_tool_use":
                stderr_msg = stderr.decode("utf-8", errors="ignore").strip()
                return {"continue": False, "message": stderr_msg or "钩子返回非零退出码"}

            stdout_text = stdout.decode("utf-8", errors="ignore").strip()
            if stdout_text:
                try:
                    return json.loads(stdout_text)
                except json.JSONDecodeError:
                    return stdout_text

            return None

        except (OSError, asyncio.CancelledError):
            return None

    def list_hooks(self) -> list[str]:
        """列出所有可用的钩子"""
        if not self.hooks_dir.exists():
            return []

        hooks = set()
        for f in self.hooks_dir.iterdir():
            if f.suffix in (".py", ".sh"):
                hooks.add(f.stem)
        return sorted(hooks)
