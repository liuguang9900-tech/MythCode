"""
TODO 任务管理工具：TodoWrite — 让 LLM 跟踪多步任务进度。
"""

import json
from typing import Optional

from tools.base import BaseTool, ToolResult


class TodoWriteTool(BaseTool):
    """
    更新任务清单。采用替换式更新：传入完整的最新 TODO 列表。

    LLM 应在执行复杂任务（3 步以上）时主动使用此工具：
    1. 任务开始时创建清单
    2. 每完成一步更新状态
    3. 全部完成后清空或标记完成
    """

    name = "todo_write"
    description = "替换式更新任务清单，传入完整 TODO 列表（状态: pending/in_progress/completed）。"
    parameters = {
        "todos": {
            "type": "array",
            "description": "完整 TODO 列表（替换式）",
            "required": True,
            "items": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "任务内容",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "任务状态",
                    },
                    "activeForm": {
                        "type": "string",
                        "description": "进行中时的动作描述",
                    },
                },
            },
        },
    }

    async def execute(self, todos: list) -> ToolResult:
        """执行 TODO 更新"""
        # 延迟导入避免循环依赖
        from agent.todo import TodoManager, TodoItem, TodoStatus

        # 获取全局 TodoManager 实例
        todo_mgr = _get_todo_manager()
        if todo_mgr is None:
            return ToolResult(
                success=False,
                output="",
                error="TodoManager 未初始化（agent 未启动）",
            )

        # 解析并校验输入
        try:
            new_todos: list[TodoItem] = []
            for item in todos:
                if not isinstance(item, dict):
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"TODO 项必须是对象，得到: {type(item).__name__}",
                    )
                content = item.get("content", "").strip()
                if not content:
                    return ToolResult(
                        success=False,
                        output="",
                        error="TODO 项的 content 不能为空",
                    )
                status_str = item.get("status", "pending")
                try:
                    status = TodoStatus(status_str)
                except ValueError:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"无效的 status: {status_str}（应为 pending/in_progress/completed）",
                    )
                active_form = item.get("activeForm", "")
                new_todos.append(TodoItem(
                    content=content,
                    status=status,
                    active_form=active_form,
                ))
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"解析 TODO 列表失败: {e}"
            )

        # 更新状态
        todo_mgr.update_todos(new_todos)

        # 生成输出摘要
        if not new_todos:
            output = "任务清单已清空"
        else:
            lines = [f"任务清单已更新（{len(new_todos)} 项）:"]
            for i, todo in enumerate(new_todos, 1):
                icon = {
                    TodoStatus.PENDING: "○",
                    TodoStatus.IN_PROGRESS: "◐",
                    TodoStatus.COMPLETED: "●",
                }.get(todo.status, "○")
                desc = todo.active_form if (todo.status == TodoStatus.IN_PROGRESS and todo.active_form) else todo.content
                lines.append(f"  {i}. {icon} {desc}")
            output = "\n".join(lines)

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "count": len(new_todos),
                "progress": todo_mgr.get_progress_summary(),
            },
        )


# 全局 TodoManager 引用（由 AgentLoop 在初始化时设置）
_todo_manager = None


def set_todo_manager(mgr) -> None:
    """设置全局 TodoManager 实例（由 AgentLoop 调用）"""
    global _todo_manager
    _todo_manager = mgr


def _get_todo_manager():
    """获取全局 TodoManager 实例"""
    return _todo_manager
