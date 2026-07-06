"""
输出样式管理器 — 支持从 .claude/styles/*.json 加载自定义输出样式。
样式控制工具调用、结果、错误等的显示格式。
"""

import json
from pathlib import Path
from typing import Optional


# 内置默认样式
_BUILTIN_STYLES = {
    "default": {
        "name": "default",
        "description": "默认样式",
        "tool_call_format": "→ {tool_name}({args_preview})",
        "tool_result_format": "← {result_preview}",
        "tool_error_format": "✗ {error}",
        "thinking_format": "[dim]{thinking}[/dim]",
        "show_tool_args": True,
        "show_tool_result": True,
        "truncate_tool_args": 80,
        "truncate_tool_result": 200,
        "use_emoji": False,
        "color": {
            "tool_call": "cyan",
            "tool_result": "green",
            "tool_error": "red",
            "thinking": "dim",
            "info": "dim",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        },
    },
    "compact": {
        "name": "compact",
        "description": "紧凑样式（最少输出）",
        "tool_call_format": "{tool_name}",
        "tool_result_format": "✓",
        "tool_error_format": "✗",
        "thinking_format": "",
        "show_tool_args": False,
        "show_tool_result": False,
        "truncate_tool_args": 0,
        "truncate_tool_result": 0,
        "use_emoji": False,
        "color": {
            "tool_call": "dim",
            "tool_result": "dim",
            "tool_error": "red",
            "thinking": "dim",
            "info": "dim",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        },
    },
    "verbose": {
        "name": "verbose",
        "description": "详细样式（完整输出）",
        "tool_call_format": "┌─ 调用工具: {tool_name}\n│  参数: {args_full}",
        "tool_result_format": "└─ 结果: {result_full}",
        "tool_error_format": "└─ 错误: {error}",
        "thinking_format": "[思考]\n{thinking}\n[/思考]",
        "show_tool_args": True,
        "show_tool_result": True,
        "truncate_tool_args": 0,
        "truncate_tool_result": 0,
        "use_emoji": True,
        "color": {
            "tool_call": "cyan",
            "tool_result": "green",
            "tool_error": "red",
            "thinking": "blue",
            "info": "dim",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        },
    },
    "minimal": {
        "name": "minimal",
        "description": "极简样式（仅显示必要信息）",
        "tool_call_format": "→ {tool_name}",
        "tool_result_format": "",
        "tool_error_format": "✗ {error}",
        "thinking_format": "",
        "show_tool_args": False,
        "show_tool_result": False,
        "truncate_tool_args": 0,
        "truncate_tool_result": 0,
        "use_emoji": False,
        "color": {
            "tool_call": "dim",
            "tool_result": "dim",
            "tool_error": "red",
            "thinking": "dim",
            "info": "dim",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        },
    },
}


class OutputStyleManager:
    """输出样式管理器"""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._styles: dict[str, dict] = {}
        self._current_style: str = "default"
        self._load_builtin_styles()
        self._load_custom_styles()

    def _load_builtin_styles(self) -> None:
        """加载内置样式"""
        for name, style in _BUILTIN_STYLES.items():
            self._styles[name] = style

    def _load_custom_styles(self) -> None:
        """从 .claude/styles/*.json 加载自定义样式"""
        styles_dir = self.workspace_root / ".claude" / "styles"
        if not styles_dir.exists():
            return

        for path in styles_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    style = json.load(f)
                name = style.get("name", path.stem)
                self._styles[name] = style
            except (json.JSONDecodeError, IOError):
                continue

    def get_style(self, name: Optional[str] = None) -> dict:
        """获取样式配置"""
        style_name = name or self._current_style
        return self._styles.get(style_name, self._styles["default"])

    def set_style(self, name: str) -> bool:
        """设置当前样式"""
        if name not in self._styles:
            return False
        self._current_style = name
        return True

    def get_current_style(self) -> str:
        """获取当前样式名"""
        return self._current_style

    def list_styles(self) -> list[dict]:
        """列出所有可用样式"""
        result = []
        for name, style in self._styles.items():
            result.append({
                "name": name,
                "description": style.get("description", ""),
                "current": name == self._current_style,
            })
        return result

    def format_tool_call(self, tool_name: str, args: dict) -> str:
        """格式化工具调用输出"""
        style = self.get_style()
        fmt = style.get("tool_call_format", "{tool_name}")

        if not style.get("show_tool_args", True):
            args_preview = ""
            args_full = ""
        else:
            args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
            truncate = style.get("truncate_tool_args", 80)
            args_preview = args_str[:truncate] + ("..." if truncate > 0 and len(args_str) > truncate else "")
            args_full = args_str

        return fmt.format(
            tool_name=tool_name,
            args_preview=args_preview,
            args_full=args_full,
        )

    def format_tool_result(self, result: str, success: bool = True) -> str:
        """格式化工具结果输出"""
        style = self.get_style()
        if not style.get("show_tool_result", True):
            return ""

        if not success:
            fmt = style.get("tool_error_format", "✗ {error}")
            return fmt.format(error=result)

        fmt = style.get("tool_result_format", "← {result_preview}")
        truncate = style.get("truncate_tool_result", 200)
        if truncate > 0 and len(result) > truncate:
            result_preview = result[:truncate] + "..."
        else:
            result_preview = result
        return fmt.format(
            result_preview=result_preview,
            result_full=result,
        )

    def get_color(self, key: str) -> str:
        """获取指定元素的配色"""
        style = self.get_style()
        colors = style.get("color", {})
        return colors.get(key, "dim")

    def use_emoji(self) -> bool:
        """是否使用 emoji"""
        return self.get_style().get("use_emoji", False)

    def reload(self) -> None:
        """重新加载样式"""
        self._styles.clear()
        self._load_builtin_styles()
        self._load_custom_styles()
