"""
AgentTeam — 多 Agent 协作系统。
支持多个独立会话+独立上下文的 Agent 并行执行多个子任务，
区别于 SubagentRunner 的单会话内子代理。

设计要点：
- 每个 team member 是独立的 SubagentRunner 实例，拥有独立的 LLM/Memory/Context
- 任务并行执行，结果按提交顺序聚合
- 支持 explore/plan/general-purpose 三种类型
- 主 Agent 通过 task_team 工具调度 Team
"""

import asyncio
from typing import Optional, TYPE_CHECKING

from agent.subagent import SubagentRunner
from agent.subagent_prompts import SUBAGENT_PROMPTS
from utils.debug import get_debug_manager

if TYPE_CHECKING:
    from agent.loop import AgentLoop


class AgentTeam:
    """多 Agent 协调器 — 让多个独立子代理并行处理多个子任务"""

    # 最大并行成员数（避免无限制并发）
    MAX_PARALLEL_MEMBERS = 5
    # 单个成员最大迭代次数
    DEFAULT_MAX_ITERATIONS = 8

    def __init__(self, parent_agent: "AgentLoop", workspace_root: str):
        self.parent_agent = parent_agent
        self.workspace_root = workspace_root
        self._debug = get_debug_manager()

    async def run_parallel(self, tasks: list[dict]) -> list[dict]:
        """
        并行执行多个独立子任务。

        Args:
            tasks: 子任务列表，每个任务为 dict:
                {
                    "task_type": "explore" | "plan" | "general-purpose",
                    "prompt": "任务描述",
                    "max_iterations": 8  # 可选
                }

        Returns:
            结果列表（与输入任务顺序一致），每个结果为 dict:
            {
                "task_type": str,
                "prompt": str,
                "success": bool,
                "output": str,
                "error": Optional[str],
            }
        """
        if not tasks:
            return []

        # 限制并发数：超过 MAX_PARALLEL_MEMBERS 则分批
        results: list[Optional[dict]] = [None] * len(tasks)
        batch_size = self.MAX_PARALLEL_MEMBERS

        for batch_start in range(0, len(tasks), batch_size):
            batch = tasks[batch_start:batch_start + batch_size]
            # 为批次中的每个任务创建独立的 SubagentRunner
            coroutines = []
            for idx, task in enumerate(batch):
                global_idx = batch_start + idx
                coroutines.append(
                    self._run_single_with_index(global_idx, task, results)
                )
            # 并行执行本批
            await asyncio.gather(*coroutines, return_exceptions=True)

        # 处理未填充的结果（异常情况）
        for i, r in enumerate(results):
            if r is None:
                results[i] = {
                    "task_type": tasks[i].get("task_type", "unknown"),
                    "prompt": tasks[i].get("prompt", ""),
                    "success": False,
                    "output": "",
                    "error": "任务未执行（内部错误）",
                }

        return results

    async def _run_single_with_index(
        self,
        idx: int,
        task: dict,
        results: list,
    ) -> None:
        """运行单个子任务并写入结果列表的指定位置"""
        task_type = task.get("task_type", "general-purpose")
        prompt = task.get("prompt", "")
        max_iterations = task.get("max_iterations", self.DEFAULT_MAX_ITERATIONS)

        if task_type not in SUBAGENT_PROMPTS:
            results[idx] = {
                "task_type": task_type,
                "prompt": prompt,
                "success": False,
                "output": "",
                "error": f"未知子代理类型: {task_type}，支持: {list(SUBAGENT_PROMPTS.keys())}",
            }
            return

        if not prompt:
            results[idx] = {
                "task_type": task_type,
                "prompt": prompt,
                "success": False,
                "output": "",
                "error": "任务描述不能为空",
            }
            return

        try:
            # 每个成员独立的 SubagentRunner（独立 LLM/Memory/Context）
            runner = SubagentRunner(self.parent_agent, self.workspace_root)
            output = await runner.run(task_type, prompt, max_iterations)
            results[idx] = {
                "task_type": task_type,
                "prompt": prompt,
                "success": True,
                "output": output,
                "error": None,
            }
        except Exception as e:
            self._debug.log("agent_team", f"成员 {idx} 执行失败: {e}")
            results[idx] = {
                "task_type": task_type,
                "prompt": prompt,
                "success": False,
                "output": "",
                "error": f"子代理执行异常: {e}",
            }

    async def run_sequential(self, tasks: list[dict]) -> list[dict]:
        """
        顺序执行多个子任务，前一个的结果可作为后一个的上下文。
        适用于有依赖关系的任务链。

        Args:
            tasks: 同 run_parallel，但 prompt 中可用 {prev_result} 占位符引用前一个结果

        Returns:
            结果列表（与输入任务顺序一致）
        """
        results: list[dict] = []
        prev_output = ""

        for task in tasks:
            prompt = task.get("prompt", "")
            # 替换占位符
            if "{prev_result}" in prompt and prev_output:
                prompt = prompt.replace("{prev_result}", prev_output)

            task_with_prompt = {**task, "prompt": prompt}
            single_results = await self.run_parallel([task_with_prompt])
            result = single_results[0] if single_results else {
                "task_type": task.get("task_type", "unknown"),
                "prompt": prompt,
                "success": False,
                "output": "",
                "error": "任务未执行",
            }
            results.append(result)
            prev_output = result.get("output", "")

        return results
