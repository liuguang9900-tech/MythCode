"""
/compact — 压缩对话上下文，调用 LLM 生成高质量摘要。
"""

from commands.base import BaseCommand
from ui.console import console, print_info, print_error


class CompactCommand(BaseCommand):
    name = "compact"
    description = "压缩对话上下文，释放 Token 空间"

    async def execute(self, args: str, agent) -> None:
        try:
            console.print("[dim]正在压缩对话上下文...[/dim]")
            result = await agent.compact_context()
            if result:
                saved = result.get("tokens_saved", 0)
                new_count = result.get("new_message_count", 0)
                console.print(
                    f"[green]上下文已压缩[/green] — "
                    f"节省约 {saved} tokens，当前 {new_count} 条消息"
                )
            else:
                print_info("当前上下文无需压缩")
        except Exception as e:
            print_error(f"压缩失败: {e}")
