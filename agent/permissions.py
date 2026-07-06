"""
权限引擎 — 规则驱动的工具执行权限控制。
支持多种权限模式：default、acceptEdits、plan、auto、bypassPermissions。
支持从 settings.json 加载权限规则。
"""

import re
import fnmatch
from enum import Enum
from typing import Optional


class PermissionMode(str, Enum):
    """权限模式枚举"""
    DEFAULT = "default"              # 正常询问
    ACCEPT_EDITS = "acceptEdits"     # 自动批准编辑操作
    PLAN = "plan"                    # 只读模式，拒绝所有写操作
    AUTO = "auto"                    # 自动批准所有操作
    BYPASS = "bypassPermissions"     # 跳过所有权限检查


# 写操作工具名
_WRITE_TOOLS = {"write_file", "edit_file", "execute_command", "notebook_edit"}

# 网络工具名（plan 模式下允许）
_NETWORK_TOOLS = {"web_fetch", "web_search"}

# 安全命令模式（auto 模式下自动批准）
_SAFE_COMMAND_PATTERNS = [
    r"^ls\b", r"^dir\b", r"^cat\b", r"^head\b", r"^tail\b",
    r"^echo\b", r"^pwd\b", r"^whoami\b", r"^date\b", r"^env\b",
    r"^git\s+status\b", r"^git\s+log\b", r"^git\s+diff\b", r"^git\s+branch\b",
    r"^python.*-m\s+pytest\b", r"^python.*test",
    r"^find\b", r"^grep\b", r"^rg\b", r"^wc\b",
    r"^which\b", r"^type\b", r"^uname\b",
]


class PermissionEngine:
    """权限规则引擎"""

    def __init__(self, mode: PermissionMode = PermissionMode.DEFAULT):
        self.mode = mode
        self._deny_rules: list[str] = []
        self._ask_rules: list[str] = []
        self._allow_rules: list[str] = []
        # 会话级"总是允许"规则（用户确认时选择"总是允许"后记录）
        # key 为工具名+参数指纹，value 为 True
        self._session_allow_rules: set[str] = set()

    def set_mode(self, mode: PermissionMode) -> None:
        self.mode = mode

    def load_from_settings(self, settings_manager) -> None:
        """
        从 SettingsManager 加载权限规则。

        配置格式（settings.json）：
        {
            "permissions": {
                "allow": ["read_file", "Bash(git status)", "Edit(src/**/*.py)"],
                "deny": ["Bash(rm -rf:*)", "Edit(.env)"],
                "ask": ["execute_command", "write_file"]
            }
        }
        """
        perms = settings_manager.get("permissions", {}) or {}
        for rule in perms.get("allow", []) or []:
            self.add_rule("allow", rule)
        for rule in perms.get("deny", []) or []:
            self.add_rule("deny", rule)
        for rule in perms.get("ask", []) or []:
            self.add_rule("ask", rule)

    def add_rule(self, rule_type: str, pattern: str) -> None:
        """添加权限规则"""
        if rule_type == "deny":
            self._deny_rules.append(pattern)
        elif rule_type == "ask":
            self._ask_rules.append(pattern)
        elif rule_type == "allow":
            self._allow_rules.append(pattern)

    def add_session_allow(self, tool_name: str, tool_args: Optional[dict] = None) -> None:
        """
        添加会话级"总是允许"规则。

        用户在确认工具调用时选择"总是允许"后调用此方法，
        后续相同工具+参数指纹的调用将自动批准。

        Args:
            tool_name: 工具名
            tool_args: 工具参数（用于生成指纹，仅取关键参数）
        """
        fingerprint = self._make_fingerprint(tool_name, tool_args)
        self._session_allow_rules.add(fingerprint)

    def clear_session_allow(self) -> None:
        """清空会话级"总是允许"规则"""
        self._session_allow_rules.clear()

    @staticmethod
    def _make_fingerprint(tool_name: str, tool_args: Optional[dict]) -> str:
        """
        生成工具调用的指纹。

        策略：
        - execute_command: 取命令的第一个 token（如 "git" from "git status"）
        - write_file/edit_file: 仅工具名（文件路径变化大，按工具名放行）
        - 其他: 工具名
        """
        if tool_name == "execute_command" and tool_args:
            command = tool_args.get("command", "")
            # 取命令的第一个 token 作为指纹
            tokens = command.split()
            if tokens:
                return f"{tool_name}:{tokens[0]}"
            return tool_name
        return tool_name

    def check_tool(self, tool_name: str, tool_args: Optional[dict] = None) -> tuple[bool, str]:
        """
        检查工具调用是否需要批准。

        Returns:
            (approved, reason): approved=True 表示可以直接执行
        """
        # bypassPermissions: 跳过所有检查
        if self.mode == PermissionMode.BYPASS:
            return True, ""

        # plan 模式：拒绝所有写操作（但允许网络工具和读工具）
        if self.mode == PermissionMode.PLAN:
            if tool_name in _WRITE_TOOLS:
                return False, f"plan 模式下不允许写操作: {tool_name}"
            return True, ""

        # auto 模式：自动批准
        if self.mode == PermissionMode.AUTO:
            return True, ""

        # 会话级"总是允许"规则优先检查（用户之前选择过"总是允许"）
        fingerprint = self._make_fingerprint(tool_name, tool_args)
        if fingerprint in self._session_allow_rules:
            return True, ""

        # acceptEdits 模式：自动批准编辑操作
        if self.mode == PermissionMode.ACCEPT_EDITS:
            if tool_name in ("write_file", "edit_file", "notebook_edit"):
                return True, ""
            # 安全命令自动批准
            if tool_name == "execute_command" and tool_args:
                command = tool_args.get("command", "")
                if self._is_safe_command(command):
                    return True, ""

        # default 模式：规则评估
        # 1. deny 规则优先
        for pattern in self._deny_rules:
            if self._match_rule(pattern, tool_name, tool_args):
                return False, f"被 deny 规则拒绝: {pattern}"

        # 2. allow 规则
        for pattern in self._allow_rules:
            if self._match_rule(pattern, tool_name, tool_args):
                return True, ""

        # 3. ask 规则（匹配则需确认，不匹配则默认行为）
        for pattern in self._ask_rules:
            if self._match_rule(pattern, tool_name, tool_args):
                return False, "需要用户确认"

        # 默认行为：读工具自动批准，写工具需确认
        if tool_name not in _WRITE_TOOLS:
            return True, ""
        return False, "需要用户确认"

    def _match_rule(self, pattern: str, tool_name: str, tool_args: Optional[dict]) -> bool:
        """检查工具调用是否匹配规则"""
        # 通配符匹配所有工具
        if pattern == "*":
            return True

        # 精确工具名匹配
        if pattern == tool_name:
            return True

        # ToolName(arg_pattern) 格式
        if "(" in pattern and pattern.endswith(")"):
            rule_tool = pattern[:pattern.index("(")]
            if rule_tool != tool_name:
                return False
            arg_pattern = pattern[pattern.index("(") + 1:-1]
            return self._match_tool_specific(tool_name, tool_args, arg_pattern)

        # 工具名 glob 匹配（如 edit_*）
        if fnmatch.fnmatch(tool_name, pattern):
            return True

        return False

    def _match_tool_specific(self, tool_name: str, tool_args: Optional[dict], arg_pattern: str) -> bool:
        """
        工具特定参数匹配。
        支持的格式：
        - Bash(git push:*): 匹配 git push 开头的命令
        - Edit(src/**/*.py): 匹配路径 glob
        - WebFetch(domain:github.com): 匹配域名
        - execute_command(git status): 精确子串匹配
        """
        if not tool_args:
            return False

        # 处理 key:value 格式（如 git push:* 或 domain:github.com）
        if ":" in arg_pattern:
            key, value_pattern = arg_pattern.split(":", 1)
            key = key.strip()
            value_pattern = value_pattern.strip()

            if tool_name == "execute_command":
                command = tool_args.get("command", "")
                # Bash(git:*:*) 格式，key 是命令前缀
                if key in command:
                    if value_pattern == "*":
                        return True
                    # 检查 key 后面的部分是否匹配 value_pattern
                    remaining = command[len(key):].strip()
                    if value_pattern == "*" or remaining.startswith(value_pattern):
                        return True
                return False

            if key == "domain" and tool_name in ("web_fetch", "web_search"):
                url = tool_args.get("url", "")
                return value_pattern in url

            # 通用 key:value 匹配
            arg_value = str(tool_args.get(key, ""))
            if value_pattern == "*":
                return bool(arg_value)
            return fnmatch.fnmatch(arg_value, value_pattern)

        # 路径 glob 匹配（用于 write_file/edit_file）
        if tool_name in ("write_file", "edit_file", "notebook_edit"):
            file_path = tool_args.get("file_path", "")
            if file_path:
                # 支持 ** 递归匹配
                pattern = arg_pattern.replace("**", "*")
                return fnmatch.fnmatch(file_path, pattern) or arg_pattern in file_path

        # 命令子串匹配（用于 execute_command）
        if tool_name == "execute_command":
            command = tool_args.get("command", "")
            return arg_pattern in command

        # 通用参数子串匹配
        args_str = str(tool_args)
        return arg_pattern in args_str

    @staticmethod
    def _is_safe_command(command: str) -> bool:
        """检查命令是否属于安全命令"""
        for pattern in _SAFE_COMMAND_PATTERNS:
            if re.search(pattern, command):
                return True
        return False
