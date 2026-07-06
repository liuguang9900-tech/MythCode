"""
TODO 任务管理器 — 跟踪多步任务的进度。
LLM 通过 TodoWrite 工具更新任务清单，状态注入 system prompt 让 LLM 始终感知当前进度。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TodoStatus(str, Enum):
    """TODO 项状态"""
    PENDING = "pending"          # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成


@dataclass
class TodoItem:
    """单个 TODO 项"""
    content: str                              # 任务内容描述
    status: TodoStatus = TodoStatus.PENDING   # 状态
    active_form: str = ""                     # 进行中时的描述（如 "正在重构 auth 模块"）


class TodoManager:
    """
    TODO 任务管理器。

    采用"替换式更新"策略（对标 Claude Code）：LLM 每次调用传入完整的最新 TODO 列表，
    而非增量修改。这样保证状态一致性，避免增量操作出错。
    """

    def __init__(self):
        self._todos: list[TodoItem] = []

    def get_todos(self) -> list[TodoItem]:
        """获取当前 TODO 列表（返回副本）"""
        return list(self._todos)

    def update_todos(self, todos: list[TodoItem]) -> None:
        """替换式更新整个 TODO 列表"""
        self._todos = list(todos)

    def clear(self) -> None:
        """清空 TODO 列表"""
        self._todos = []

    def has_todos(self) -> bool:
        """是否有 TODO 项"""
        return len(self._todos) > 0

    def get_context_for_prompt(self) -> str:
        """
        生成注入 system prompt 的 TODO 上下文。

        Returns:
            格式化的 TODO 列表文本；若无 TODO 则返回空字符串
        """
        if not self._todos:
            return ""

        lines = ["## 当前任务清单"]
        for i, todo in enumerate(self._todos, 1):
            icon = {
                TodoStatus.PENDING: "○",
                TodoStatus.IN_PROGRESS: "◐",
                TodoStatus.COMPLETED: "●",
            }.get(todo.status, "○")
            desc = todo.active_form if (todo.status == TodoStatus.IN_PROGRESS and todo.active_form) else todo.content
            lines.append(f"{i}. {icon} {desc}")

        return "\n".join(lines)

    def get_progress_summary(self) -> str:
        """获取进度摘要（用于 UI 显示）"""
        if not self._todos:
            return "无任务"
        total = len(self._todos)
        completed = sum(1 for t in self._todos if t.status == TodoStatus.COMPLETED)
        in_progress = sum(1 for t in self._todos if t.status == TodoStatus.IN_PROGRESS)
        return f"{completed}/{total} 完成, {in_progress} 进行中"
