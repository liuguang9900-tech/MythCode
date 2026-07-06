"""
TaskTool — 子代理工具，启动子 Agent 处理独立子任务。
"""

from typing import Optional, Any
from tools.base import BaseTool, ToolResult


# 模块级父 Agent 引用（仿 todo_ops.py 模式）
_parent_agent = None


def set_parent_agent(agent) -> None:
    """设置父 Agent 引用"""
    global _parent_agent
    _parent_agent = agent


class TaskTool(BaseTool):
    """子代理工具 — 启动子 Agent 处理独立子任务"""

    name = "task"
    description = "启动子代理处理独立子任务（类型: explore/plan/general-purpose）。"
    parameters = {
        "task_type": {
            "type": "string",
            "enum": ["explore", "plan", "general-purpose"],
            "description": "子代理类型",
            "required": True,
        },
        "prompt": {
            "type": "string",
            "description": "任务描述，含上下文",
            "required": True,
        },
        "max_iterations": {
            "type": "integer",
            "description": "最大迭代次数，默认 10",
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        """执行子代理任务"""
        if _parent_agent is None:
            return ToolResult(
                success=False, output="", error="父 Agent 未初始化"
            )

        task_type = kwargs.get("task_type", "general-purpose")
        prompt = kwargs.get("prompt", "")
        max_iterations = kwargs.get("max_iterations", 10)

        if not prompt:
            return ToolResult(success=False, output="", error="任务描述不能为空")

        try:
            from agent.subagent import SubagentRunner

            runner = SubagentRunner(_parent_agent, _parent_agent.workspace_root)
            result = await runner.run(task_type, prompt, max_iterations)

            return ToolResult(
                success=True,
                output=result,
                metadata={
                    "task_type": task_type,
                    "prompt": prompt[:200],
                    "max_iterations": max_iterations,
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"子代理执行失败: {e}"
            )
