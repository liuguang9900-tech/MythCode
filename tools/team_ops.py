"""
TeamOps 工具 — Agent Teams 多代理协作入口。
让主 Agent 可调度多个独立子代理并行处理多个子任务。
"""

import json
from typing import Any
from tools.base import BaseTool, ToolResult


# 模块级父 Agent 引用（仿 task_ops.py 模式）
_parent_agent = None


def set_parent_agent(agent) -> None:
    """设置父 Agent 引用"""
    global _parent_agent
    _parent_agent = agent


class TaskTeamTool(BaseTool):
    """多代理协作工具 — 并行/顺序执行多个独立子任务"""

    name = "task_team"
    description = (
        "启动多代理协作团队，并行或顺序执行多个独立子任务。"
        "每个成员拥有独立上下文，适合大型重构、并行探索、多方案对比等场景。"
        "并行模式：所有任务同时执行；顺序模式：前一个任务的结果可作后一个的输入。"
    )
    parameters = {
        "mode": {
            "type": "string",
            "enum": ["parallel", "sequential"],
            "description": "执行模式：parallel=并行，sequential=顺序（前一个结果可引用为 {prev_result}）",
            "required": True,
        },
        "tasks": {
            "type": "array",
            "description": "子任务列表，每项含 task_type(explore/plan/general-purpose)、prompt、可选 max_iterations",
            "required": True,
            "items": {
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "enum": ["explore", "plan", "general-purpose"],
                    },
                    "prompt": {"type": "string"},
                    "max_iterations": {"type": "integer"},
                },
            },
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        if _parent_agent is None:
            return ToolResult(success=False, output="", error="父 Agent 未初始化")

        mode = kwargs.get("mode", "parallel")
        tasks = kwargs.get("tasks", [])

        if not isinstance(tasks, list) or not tasks:
            return ToolResult(
                success=False, output="", error="tasks 必须是非空数组"
            )

        if len(tasks) > 10:
            return ToolResult(
                success=False,
                output="",
                error=f"任务数过多（{len(tasks)}），最多支持 10 个",
            )

        # 校验每个任务
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                return ToolResult(
                    success=False, output="", error=f"任务 {i} 必须是对象"
                )
            if t.get("task_type") not in ("explore", "plan", "general-purpose"):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"任务 {i} 的 task_type 无效: {t.get('task_type')}",
                )
            if not t.get("prompt"):
                return ToolResult(
                    success=False, output="", error=f"任务 {i} 的 prompt 不能为空"
                )

        try:
            from agent.agent_team import AgentTeam

            team = AgentTeam(_parent_agent, _parent_agent.workspace_root)
            if mode == "sequential":
                results = await team.run_sequential(tasks)
            else:
                results = await team.run_parallel(tasks)

            # 格式化输出
            lines = [
                f"# Agent Team 执行完成（模式: {mode}，成员: {len(results)}）",
                "",
            ]
            success_count = sum(1 for r in results if r.get("success"))
            lines.append(f"成功: {success_count}/{len(results)}")
            lines.append("")

            for i, r in enumerate(results):
                status = "✓" if r.get("success") else "✗"
                lines.append(f"## 任务 {i + 1} [{status}] {r.get('task_type')}")
                lines.append(f"**Prompt**: {r.get('prompt', '')[:200]}")
                if r.get("success"):
                    output = r.get("output", "")
                    # 限制单个结果长度
                    if len(output) > 2000:
                        output = output[:2000] + f"\n\n...(共 {len(output)} 字符，已截断)"
                    lines.append("")
                    lines.append("**输出**:")
                    lines.append(output)
                else:
                    lines.append(f"**错误**: {r.get('error', '未知错误')}")
                lines.append("")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={
                    "mode": mode,
                    "task_count": len(tasks),
                    "success_count": success_count,
                    "results": results,
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Agent Team 执行失败: {e}"
            )
