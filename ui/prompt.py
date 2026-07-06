"""
Prompt Toolkit 输入处理 — 多行编辑、自动补全、历史记录。
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from pathlib import Path


def _get_all_commands() -> list[str]:
    """从命令注册中心动态获取所有命令名（含别名），延迟导入避免循环依赖"""
    try:
        from commands.registry import registry as command_registry
        commands = []
        for cmd in command_registry.list_commands():
            commands.append(f"/{cmd.name}")
            for alias in cmd.aliases:
                commands.append(f"/{alias}")
        return commands
    except Exception:
        # 注册中心尚未初始化时回退到基础命令
        return ["/help", "/clear", "/config", "/tools", "/rewind", "/exit", "/quit"]


class SlashCompleter(Completer):
    """斜杠命令自动补全"""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd in _get_all_commands():
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


# 终端样式
PROMPT_STYLE = Style.from_dict({
    "prompt": "bold cyan",
    "separator": "dim",
    "input": "",
})


def create_session(history_file: str = "") -> PromptSession:
    """创建 Prompt Toolkit 会话"""
    history = None
    if history_file:
        history_path = Path(history_file)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_path))

    # 键绑定
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _(event):
        """Alt+Enter 插入换行"""
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        completer=SlashCompleter(),
        style=PROMPT_STYLE,
        key_bindings=kb,
        multiline=False,
        wrap_lines=True,
    )
    return session


def get_prompt_message() -> str:
    """获取提示符消息"""
    return [
        ("class:prompt", "> "),
    ]
