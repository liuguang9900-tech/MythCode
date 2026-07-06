"""
SubagentRunner — 子 Agent 运行器。
支持启动子 Agent 处理独立子任务，拥有独立上下文。
"""

import asyncio
from typing import Optional, TYPE_CHECKING

from config import get_config
from llm.client import LLMClient
from agent.memory import ConversationMemory
from agent.context import ContextManager
from agent.permissions import PermissionEngine, PermissionMode
from agent.subagent_prompts import SUBAGENT_PROMPTS
from tools.registry import registry as tool_registry
from utils.debug import get_debug_manager

if TYPE_CHECKING:
    from agent.loop import AgentLoop


class SubagentRunner:
    """子 Agent 运行器"""

    # 最大递归深度
    MAX_DEPTH = 2

    def __init__(self, parent_agent: "AgentLoop", workspace_root: str):
        self.parent_agent = parent_agent
        self.workspace_root = workspace_root
        self._debug = get_debug_manager()
        self._depth = 0

    async def run(
        self,
        task_type: str,
        prompt: str,
        max_iterations: int = 10,
    ) -> str:
        """
        启动子 Agent 执行任务。

        Args:
            task_type: 子代理类型（explore/plan/general-purpose）
            prompt: 任务描述
            max_iterations: 最大迭代次数

        Returns:
            子 Agent 的最终文本回复
        """
        # 深度检查
        if self._depth >= self.MAX_DEPTH:
            return f"错误：子代理嵌套深度超过限制（{self.MAX_DEPTH} 层）"

        # 验证类型
        if task_type not in SUBAGENT_PROMPTS:
            return f"错误：未知子代理类型: {task_type}，支持: {list(SUBAGENT_PROMPTS.keys())}"

        self._depth += 1
        try:
            return await self._run_subagent(task_type, prompt, max_iterations)
        finally:
            self._depth -= 1

    async def _run_subagent(
        self,
        task_type: str,
        prompt: str,
        max_iterations: int,
    ) -> str:
        """运行子 Agent 循环"""
        cfg = get_config()

        # 创建独立组件
        sub_llm = LLMClient()
        sub_memory = ConversationMemory(cfg.model.name)
        sub_context = ContextManager(sub_memory, self.workspace_root)

        # 设置额外工作目录
        if self.parent_agent.additional_roots:
            sub_context.set_additional_roots(self.parent_agent.additional_roots)

        # 注入子 Agent 专用 system prompt
        sub_context.set_subagent_prompt(SUBAGENT_PROMPTS[task_type], task_type)

        # 权限设置：explore 类型强制 PLAN 模式
        if task_type == "explore":
            sub_permission = PermissionEngine(PermissionMode.PLAN)
        else:
            # general-purpose 继承父 Agent 的权限模式但默认 auto
            sub_permission = PermissionEngine(PermissionMode.AUTO)

        # 添加用户消息
        sub_memory.add_message("user", prompt)

        # 子代理静默执行：不转发工具调用过程到父 Agent UI

        final_response = ""
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                # 构建消息
                messages = sub_context.build_messages(prompt) if iteration == 1 else sub_memory.get_messages()
                if messages[0]["role"] != "system":
                    messages.insert(0, {"role": "system", "content": sub_context.build_system_prompt()})

                tool_schemas = tool_registry.get_schemas()

                # 流式调用 LLM
                text_buffer = ""
                tool_calls_buffer: list[dict] = []
                finish_reason = ""

                async for chunk in sub_llm.chat(messages, tools=tool_schemas):
                    if chunk["type"] == "text_delta":
                        text_buffer += chunk["content"]
                    elif chunk["type"] == "tool_call":
                        tool_calls_buffer.append(chunk["tool_call"])
                    elif chunk["type"] == "finish":
                        finish_reason = chunk["finish_reason"]
                    elif chunk["type"] == "error":
                        return f"子代理 LLM 错误: {chunk['error']}"

                # 处理响应
                if tool_calls_buffer:
                    assistant_msg = {
                        "role": "assistant",
                        "content": text_buffer or None,
                        "tool_calls": tool_calls_buffer,
                    }
                    sub_memory.messages.append(assistant_msg)

                    # 执行工具（子 Agent 的工具调用通过父 Agent 的回调转发）
                    for tc in tool_calls_buffer:
                        tool_result = await self._execute_subagent_tool(
                            tc, sub_permission, task_type
                        )
                        sub_memory.add_tool_result(
                            tc["id"],
                            tool_result.output if tool_result.success
                            else f"错误: {tool_result.error or '未知错误'}",
                        )
                    continue

                elif finish_reason == "stop" or text_buffer:
                    final_response = text_buffer
                    sub_memory.add_message("assistant", text_buffer)
                    break

                else:
                    final_response = text_buffer or "(子代理无响应)"
                    break

            else:
                final_response = f"(子代理达到最大迭代次数 {max_iterations})"

        except Exception as e:
            final_response = f"子代理执行异常: {e}"

        # 累加 Token 用量到父 Agent
        sub_usage = sub_llm.get_usage()
        self.parent_agent.llm._prompt_tokens += sub_usage["prompt_tokens"]
        self.parent_agent.llm._completion_tokens += sub_usage["completion_tokens"]
        self.parent_agent.llm._request_count += sub_usage["request_count"]

        return final_response

    async def _execute_subagent_tool(
        self,
        tool_call: dict,
        permission_engine: PermissionEngine,
        task_type: str,
    ):
        """执行子 Agent 的工具调用"""
        import json
        from tools.base import ToolResult
        from tools.registry import registry as tool_registry

        func_name = tool_call["function"]["name"]
        func_args_str = tool_call["function"].get("arguments", "{}")

        try:
            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
        except json.JSONDecodeError:
            return ToolResult(success=False, output="", error=f"参数解析失败: {func_args_str}")

        tool = tool_registry.get(func_name)
        if tool is None:
            return ToolResult(success=False, output="", error=f"未知工具: {func_name}")

        # 权限检查
        approved, reason = permission_engine.check_tool(func_name, func_args)
        if not approved:
            return ToolResult(success=False, output="", error=reason or "权限不足")

        # 子代理工具调用静默执行，不转发到父 Agent UI

        try:
            result = await tool.execute(**func_args)
        except Exception as e:
            result = ToolResult(success=False, output="", error=f"工具执行异常: {e}")

        return result
