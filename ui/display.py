"""
流式输出展示 — 处理 LLM 流式响应的终端渲染。
"""

from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from ui.console import console


class StreamDisplay:
    """流式输出显示器 — 实时渲染 LLM 的增量文本"""

    def __init__(self):
        self.buffer = ""
        self.live: Live | None = None
        self.is_active = False

    def start(self):
        """开始流式显示"""
        self.buffer = ""
        self.is_active = True
        self.live = Live(
            Markdown(""),
            console=console,
            refresh_per_second=10,
            transient=False,
        )
        self.live.start()

    def add_chunk(self, text: str):
        """添加文本增量"""
        self.buffer += text
        if self.live and self.is_active:
            self.live.update(Markdown(self.buffer))

    def finish(self):
        """结束流式显示"""
        self.is_active = False
        if self.live:
            self.live.stop()
            self.live = None

    def get_text(self) -> str:
        """获取累积的完整文本"""
        return self.buffer


class ThinkingDisplay:
    """思考过程展示 — 显示 Agent 正在做什么"""

    def __init__(self):
        self.spinner: Spinner | None = None

    def show(self, message: str = "思考中..."):
        """显示思考状态"""
        self.spinner = Spinner("dots", text=f"[dim]{message}[/dim]")
        console.print(self.spinner)

    def hide(self):
        """隐藏思考状态"""
        # Rich spinner 会自动管理，这里做清理标记
        self.spinner = None
