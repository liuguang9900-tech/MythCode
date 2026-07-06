"""
IDE 事件处理器 — 将 Agent 事件转发到 IDE。
"""

from typing import Optional, Any
from ide.bridge import IDEBridge
from ide.protocol import IDEEvent


class IDEEventHandler:
    """将 Agent 事件转发到 IDE"""

    def __init__(self, bridge: IDEBridge):
        self.bridge = bridge

    async def on_tool_call_started(self, tool_name: str, args: dict) -> None:
        """工具调用开始"""
        await self.bridge.send_event({
            "type": IDEEvent.TOOL_CALL_STARTED.value,
            "tool_name": tool_name,
            "args": args,
        })

    async def on_tool_call_completed(
        self, tool_name: str, success: bool, output: str, metadata: dict = None
    ) -> None:
        """工具调用完成"""
        await self.bridge.send_event({
            "type": IDEEvent.TOOL_CALL_COMPLETED.value,
            "tool_name": tool_name,
            "success": success,
            "output": output[:500],  # 截断避免过大
            "metadata": metadata or {},
        })

    async def on_file_modified(self, file_path: str, action: str = "modified") -> None:
        """文件被修改"""
        await self.bridge.send_event({
            "type": IDEEvent.FILE_MODIFIED.value,
            "file_path": file_path,
            "action": action,
        })

    async def on_diff_ready(self, file_path: str, diff: str) -> None:
        """diff 准备好"""
        await self.bridge.send_event({
            "type": IDEEvent.DIFF_READY.value,
            "file_path": file_path,
            "diff": diff,
        })

    async def on_session_started(self, workspace: str) -> None:
        """会话开始"""
        await self.bridge.send_event({
            "type": IDEEvent.SESSION_STARTED.value,
            "workspace": workspace,
        })

    async def on_session_ended(self, total_steps: int) -> None:
        """会话结束"""
        await self.bridge.send_event({
            "type": IDEEvent.SESSION_ENDED.value,
            "total_steps": total_steps,
        })
