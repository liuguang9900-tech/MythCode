"""
对话与状态关联映射表 — 将对话轮次、消息列表与文件快照强绑定。

每轮对话（Step）拥有唯一 ID，系统维护 Session 映射表，
将"对话轮次"、"消息列表"与"文件快照 ID"关联。
"""

import copy
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StepRecord:
    """单步记录"""
    step_id: int                              # 自增序号，从 1 开始
    user_input: str                           # 用户原始输入
    summary: str                              # 步骤摘要
    snapshot_ids: list[str] = field(default_factory=list)   # 关联的快照 ID 列表
    messages_snapshot: list[dict] = field(default_factory=list)  # 该步骤结束时的消息列表副本
    tool_calls: list[str] = field(default_factory=list)     # 调用的工具名称列表
    files_modified: list[str] = field(default_factory=list)  # 被修改的文件路径列表
    timestamp: str = ""                       # 时间戳

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")


class SessionMap:
    """会话映射表 — 管理所有步骤记录"""

    def __init__(self):
        self._steps: dict[int, StepRecord] = {}
        self._current_step_id: int = 0

    @property
    def current_step_id(self) -> int:
        return self._current_step_id

    def next_step_id(self) -> int:
        """获取下一个步骤 ID"""
        self._current_step_id += 1
        return self._current_step_id

    def record_step(self, record: StepRecord) -> None:
        """记录一个步骤"""
        self._steps[record.step_id] = record

    def get_step(self, step_id: int) -> Optional[StepRecord]:
        """获取指定步骤"""
        return self._steps.get(step_id)

    def get_all_steps(self) -> list[StepRecord]:
        """获取所有步骤（按 ID 升序）"""
        return [self._steps[sid] for sid in sorted(self._steps.keys())]

    def get_steps_after(self, step_id: int) -> list[StepRecord]:
        """获取指定步骤之后的所有记录"""
        return [
            self._steps[sid] for sid in sorted(self._steps.keys())
            if sid > step_id
        ]

    def truncate_after(self, step_id: int) -> None:
        """截断步骤记录：删除指定步骤之后的所有记录"""
        to_delete = [sid for sid in self._steps if sid > step_id]
        for sid in to_delete:
            del self._steps[sid]
        self._current_step_id = step_id

    def clear(self) -> None:
        """清空所有记录"""
        self._steps.clear()
        self._current_step_id = 0

    def build_step_summary(self, record: StepRecord) -> str:
        """生成步骤摘要文本"""
        parts = []

        if record.tool_calls:
            tools_str = ", ".join(record.tool_calls)
            parts.append(f"调用了 {tools_str}")

        if record.files_modified:
            files_str = ", ".join(record.files_modified)
            parts.append(f"修改了 {files_str}")
        elif not record.tool_calls:
            parts.append("(纯文本对话)")

        if not parts:
            parts.append("(无操作)")

        return "，".join(parts)

    def is_readonly_step(self, record: StepRecord) -> bool:
        """判断步骤是否只有读操作（无需文件还原）"""
        write_tools = {"write_file", "edit_file", "execute_command"}
        return not any(t in write_tools for t in record.tool_calls)
