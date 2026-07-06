"""
ReAct 核心循环 — 智能体的"大脑"。
实现 Reasoning + Acting 的自主决策循环：
  1. 接收用户输入
  2. 构建上下文 → 调用 LLM
  3. 解析响应：文本 → 流式输出 / Tool Call → 执行工具
  4. 工具结果反馈给 LLM → 继续推理
  5. 直到 LLM 返回最终答案或达到最大迭代次数
"""

import json
import asyncio
from typing import Optional, Callable, Awaitable

from config import get_config, ModelConfig
from llm.client import LLMClient
from agent.memory import ConversationMemory
from agent.context import ContextManager
from agent.snapshot import SnapshotManager
from agent.session_map import SessionMap, StepRecord
from agent.persistence import ConversationPersistence
from agent.session_index import SessionIndex
from agent.permissions import PermissionEngine, PermissionMode
from agent.auto_memory import AutoMemoryManager
from agent.rules import RulesManager
from agent.hooks import HookManager
from tools.registry import registry as tool_registry
from tools.sandbox import get_sandbox
from tools.todo_ops import set_todo_manager
from agent.todo import TodoManager
from utils.debug import get_debug_manager


# 回调类型
OnTextChunk = Callable[[str], Awaitable[None]]        # 文本增量回调
OnToolCall = Callable[[str, dict], Awaitable[bool]]    # 工具调用回调，返回是否批准
OnToolResult = Callable[[str, str, bool, dict], Awaitable[None]]  # 工具结果回调（含 metadata）
OnThinking = Callable[[str], Awaitable[None]]          # 思考过程回调
OnCompression = Callable[[dict], Awaitable[None]]       # 压缩通知回调


class AgentLoop:
    """ReAct 自主推理循环"""

    def __init__(
        self,
        workspace_root: str = ".",
        on_text_chunk: Optional[OnTextChunk] = None,
        on_tool_call: Optional[OnToolCall] = None,
        on_tool_result: Optional[OnToolResult] = None,
        on_thinking: Optional[OnThinking] = None,
        on_compression: Optional[OnCompression] = None,
        safe_mode: bool = False,
        permission_mode: str = "default",
        session_name: Optional[str] = None,
        additional_roots: Optional[list[str]] = None,
    ):
        self.cfg = get_config()
        self.workspace_root = workspace_root
        self.llm = LLMClient()
        self.memory = ConversationMemory(self.cfg.model.name)
        self.context = ContextManager(self.memory, workspace_root)
        self.sandbox = get_sandbox()

        # 时空回溯组件
        self.snapshot = SnapshotManager(workspace_root)
        self.session_map = SessionMap()

        # 回调
        self.on_text_chunk = on_text_chunk
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_thinking = on_thinking
        self.on_compression = on_compression

        # 当前步骤追踪
        self._current_tool_calls: list[str] = []
        self._current_files_modified: list[str] = []
        self._current_snapshot_ids: list[str] = []

        # 并行执行锁（保护共享状态和 UI 输出）
        self._state_lock = asyncio.Lock()
        self._ui_lock = asyncio.Lock()

        # 新增：会话管理
        self.safe_mode = safe_mode
        self.permission_engine = PermissionEngine(PermissionMode(permission_mode))
        self.session_name = session_name
        self.session_index = SessionIndex()
        self._session_id: Optional[str] = None
        self._continue_conv = False  # 兼容旧的 -c 参数

        # 额外工作目录
        self.additional_roots = additional_roots or []
        if self.additional_roots:
            self.sandbox.set_additional_roots(self.additional_roots)
            self.context.set_additional_roots(self.additional_roots)

        # 调试
        self._debug = get_debug_manager()

        # 自动记忆
        self.auto_memory = AutoMemoryManager(workspace_root)
        self.context.set_auto_memory(self.auto_memory)

        # 规则引擎
        self.rules = RulesManager(workspace_root)
        self.context.set_rules(self.rules)

        # 钩子系统
        self.hooks = HookManager(workspace_root)

        # 设置管理器（多作用域配置）
        from config.settings import SettingsManager
        self.settings = SettingsManager(workspace_root)
        self.permission_engine.load_from_settings(self.settings)
        self.hooks.load_from_settings(self.settings)

        # 计划管理器
        from agent.plan_manager import PlanManager
        self.plan_manager = PlanManager(workspace_root)
        self.context.set_plan_manager(self.plan_manager)

        # 技能管理器
        from agent.skills import SkillManager
        self.skills = SkillManager(workspace_root)
        self.skills.load_all()
        self.context.set_skills(self.skills)

        # TODO 任务管理
        self.todo = TodoManager()
        set_todo_manager(self.todo)
        self.context.set_todo(self.todo)

        # 子代理：注入父 Agent 引用
        from tools.task_ops import set_parent_agent
        set_parent_agent(self)

        # 安全模式：禁用 CLAUDE.md、hooks、skills、auto-memory
        if self.safe_mode:
            self._debug.log("agent", "安全模式已启用：CLAUDE.md、hooks、skills、auto-memory 已禁用")
            self.context.disable_claude_md = True
            self.context.disable_auto_memory = True
            self.hooks.disable()

        # 中断控制
        self._cancelled = False
        self._current_task: Optional[asyncio.Task] = None
        self._session_started = False

        # MCP 管理
        self.mcp_manager: Optional[Any] = None  # 延迟初始化，避免无 mcp 模块时出错

        # 跨会话费用追踪
        from agent.cost_tracker import CostTracker
        self.cost_tracker = CostTracker(
            workspace_root=workspace_root,
            enabled=getattr(self.cfg.cost, "track_cross_session", True),
        )

        # 输出样式管理
        from agent.output_style import OutputStyleManager
        self.output_style_manager = OutputStyleManager(workspace_root)
        # 注册到全局，供 ui/console.py 使用
        from ui.console import set_style_manager
        set_style_manager(self.output_style_manager)

    async def initialize(self) -> None:
        """异步初始化（启动 MCP 等需要异步的组件）"""
        if self.cfg.mcp.enabled:
            try:
                from mcp.manager import MCPManager
                self.mcp_manager = MCPManager(self.workspace_root)
                self.mcp_manager.load_config()
                await self.mcp_manager.start_all()
                await self.mcp_manager.register_tools()
            except Exception as e:
                self._debug.log("agent", f"MCP 初始化失败: {e}")
                self.mcp_manager = None

        # 启动配置热重载
        try:
            from agent.config_reloader import ConfigReloader
            self.config_reloader = ConfigReloader(self)
            self.config_reloader.setup()
            self.config_reloader.start()
        except Exception as e:
            self._debug.log("agent", f"配置热重载启动失败: {e}")

    def reload_config(self) -> None:
        """重新加载配置并应用到各组件"""
        from config import reload_config, get_config
        reload_config()
        self.cfg = get_config()
        self._debug.log("agent", "配置已重新加载")

        # 同步到上下文管理器（context_window 等可能变化）
        try:
            self.memory.context_window = self.cfg.agent.context_window
            self.memory.summary_threshold = self.cfg.agent.summary_threshold
            self.memory.max_tool_result_tokens = getattr(self.cfg.agent, "max_tool_result_tokens", 4000)
            self.memory.preserve_important = getattr(self.cfg.agent, "preserve_important_messages", True)
        except Exception:
            pass

        # 同步费用追踪配置
        try:
            self.cost_tracker.enabled = getattr(self.cfg.cost, "track_cross_session", True)
        except Exception:
            pass

    def cancel_current(self) -> None:
        """取消当前正在执行的 LLM 请求"""
        self._cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    def _reset_cancelled(self) -> None:
        """重置取消标志（新请求开始前调用）"""
        self._cancelled = False
        self._current_task = None

    async def run(self, user_input: str) -> str:
        """
        执行一次完整的 ReAct 循环。

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            LLM 的最终文本回复
        """
        # 重置取消标志，记录当前 task
        self._reset_cancelled()
        self._current_task = asyncio.current_task()

        # 钩子：UserPromptSubmit — 可修改用户输入
        modified_input = await self.hooks.on_user_prompt_submit(user_input)
        if modified_input is not None:
            self._debug.log("agent", f"钩子修改了用户输入: {user_input[:50]}... -> {modified_input[:50]}...")
            user_input = modified_input

        # 钩子：SessionStart（首次 run 时触发）
        if not self._session_started:
            self._session_started = True
            await self.hooks.on_notification("session_start", {
                "workspace": str(self.workspace_root),
                "model": self.cfg.model.name,
            })

        # 首次 run 时初始化 session_id 并在 CostTracker 中创建会话
        if self._session_id is None:
            from agent.session_index import SessionIndex
            self._session_id = SessionIndex.generate_id()
            try:
                self.cost_tracker.start_session(self._session_id, self.cfg.model.name)
            except Exception:
                pass

        # 时空回溯：开始新步骤
        step_id = self.session_map.next_step_id()
        self._current_tool_calls = []
        self._current_files_modified = []
        self._current_snapshot_ids = []

        # 添加用户消息到历史
        self.memory.add_message("user", user_input)

        iteration = 0
        final_response = ""

        try:
            while iteration < self.cfg.agent.max_iterations:
                # 检查取消标志
                if self._cancelled:
                    final_response = "(已中断)"
                    break

                iteration += 1

                # 自动压缩：LLM 调用前检查上下文是否接近限制
                if self.memory.is_near_limit():
                    self._debug.log("agent", "上下文接近限制，自动触发压缩...")
                    compress_result = await self.memory.llm_compress(self.llm)
                    if compress_result:
                        self._debug.log(
                            "agent",
                            f"压缩完成: 节省 {compress_result['tokens_saved']} tokens, "
                            f"消息数 {compress_result['old_message_count']} → {compress_result['new_message_count']}"
                        )
                        if self.on_compression:
                            await self.on_compression(compress_result)

                # 1. 构建消息列表
                messages = self.context.build_messages(user_input) if iteration == 1 else self.memory.get_messages()

                # 确保 system prompt 在最前面
                if messages[0]["role"] != "system":
                    messages.insert(0, {"role": "system", "content": self.context.build_system_prompt()})

                # 2. 获取工具 Schema（按需加载：首轮仅核心工具，后续按需激活）
                if iteration == 1:
                    # 首轮：仅加载核心工具，节省 token
                    from tools.registry import CORE_TOOLS
                    tool_registry.set_active_tools(CORE_TOOLS.copy())
                # 后续轮次：保持当前激活集合（工具执行时可能动态激活扩展工具）
                tool_schemas = tool_registry.get_schemas()

                # 3. 调用 LLM（流式）
                text_buffer = ""
                tool_calls_buffer: list[dict] = []
                finish_reason = ""

                async for chunk in self.llm.chat(messages, tools=tool_schemas):
                    # 流式处理中也检查取消标志
                    if self._cancelled:
                        break

                    if chunk["type"] == "text_delta":
                        text_buffer += chunk["content"]
                        if self.on_text_chunk:
                            await self.on_text_chunk(chunk["content"])

                    elif chunk["type"] == "tool_call":
                        tool_calls_buffer.append(chunk["tool_call"])

                    elif chunk["type"] == "finish":
                        finish_reason = chunk["finish_reason"]

                    elif chunk["type"] == "error":
                        error_msg = f"LLM 调用错误: {chunk['error']}"
                        if self.on_text_chunk:
                            await self.on_text_chunk(f"\n[错误] {error_msg}\n")
                        return error_msg

                # 流结束后记录增量 token 用量（usage 在最后一个 chunk，晚于 finish 事件）
                self.record_token_usage()

                # 如果被取消，跳出循环
                if self._cancelled:
                    final_response = "(已中断)"
                    break

                # 4. 处理 LLM 响应
                if tool_calls_buffer:
                    # 有工具调用：记录 assistant 消息（含 tool_calls）
                    assistant_msg = {
                        "role": "assistant",
                        "content": text_buffer or None,
                        "tool_calls": tool_calls_buffer,
                    }
                    self.memory.messages.append(assistant_msg)

                    # 执行工具调用（支持并行）
                    if self.cfg.agent.parallel_tool_execution and len(tool_calls_buffer) > 1:
                        results = await self._execute_tools_parallel(tool_calls_buffer)
                        for tc, tool_result in zip(tool_calls_buffer, results):
                            if self._cancelled:
                                break
                            self._add_tool_result_to_memory(tc, tool_result)
                    else:
                        # 串行执行（单工具或禁用并行时）
                        for tc in tool_calls_buffer:
                            if self._cancelled:
                                break
                            tool_result = await self._execute_tool(tc)
                            self._add_tool_result_to_memory(tc, tool_result)

                    # 继续循环，让 LLM 处理工具结果
                    continue

                elif finish_reason == "stop" or text_buffer:
                    # 最终回复
                    final_response = text_buffer
                    self.memory.add_message("assistant", text_buffer)
                    break

                else:
                    # 异常情况
                    final_response = text_buffer or "(无响应)"
                    break

            else:
                # 达到最大迭代次数
                final_response = (
                    f"(已达到最大迭代次数 {self.cfg.agent.max_iterations}，任务可能未完成)"
                )

        except asyncio.CancelledError:
            final_response = "(已中断)"
            self._debug.log("agent", "任务被取消 (CancelledError)")

        # 时空回溯：记录步骤状态
        self._record_step(step_id, user_input)

        return final_response

    def _add_tool_result_to_memory(self, tool_call: dict, tool_result) -> None:
        """将工具结果添加到记忆，支持多模态（图片）结果"""
        # 检查是否为图片结果（多模态）
        if tool_result.success and tool_result.metadata and tool_result.metadata.get("is_image"):
            data_url = tool_result.metadata.get("data_url")
            if data_url:
                # 构建多模态 tool 消息
                content = [
                    {"type": "text", "text": tool_result.output or "图片已读取"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]
                self.memory.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": content,
                })
                return

        # 普通文本结果
        self.memory.add_tool_result(
            tool_call["id"],
            tool_result.output if tool_result.success else f"错误: {tool_result.error or '未知错误'}",
        )

    async def _execute_tools_parallel(self, tool_calls: list[dict]) -> list:
        """
        并行执行多个工具调用。

        策略：
        1. 依赖分析：写同一文件的工具串行；execute_command 与写工具串行；读工具并行
        2. 权限确认串行收集（UI 交互必须串行）
        3. 已批准的工具按依赖分组并行执行
        """
        from tools.base import ToolResult

        # 1. 解析所有工具调用并做依赖分析
        parsed_calls: list[dict] = []
        for idx, tc in enumerate(tool_calls):
            func_name = tc["function"]["name"]
            func_args_str = tc["function"].get("arguments", "{}")
            try:
                func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
            except json.JSONDecodeError:
                parsed_calls.append({
                    "idx": idx, "tc": tc, "name": func_name, "args": {},
                    "error": ToolResult(success=False, output="", error=f"工具参数 JSON 解析失败: {func_args_str}"),
                })
                continue
            parsed_calls.append({"idx": idx, "tc": tc, "name": func_name, "args": func_args, "error": None})

        # 2. 串行收集权限批准（UI 交互必须串行）
        for call in parsed_calls:
            if call["error"] is not None:
                continue
            if self._cancelled:
                call["error"] = ToolResult(success=False, output="", error="已取消")
                continue
            # 检查权限
            approved = await self._check_permission_and_confirm(call["name"], call["args"])
            if not approved:
                call["error"] = ToolResult(success=False, output="", error="用户取消了工具调用")

        # 3. 依赖分析：将工具调用分组
        groups = self._group_calls_by_dependency(parsed_calls)

        # 4. 按组执行：组内并行，组间串行
        results: list = [None] * len(tool_calls)
        for group in groups:
            if self._cancelled:
                for call in group:
                    if results[call["idx"]] is None:
                        results[call["idx"]] = ToolResult(success=False, output="", error="已取消")
                continue

            # 过滤掉已有错误的调用
            executable = [c for c in group if c["error"] is None and results[c["idx"]] is None]
            if not executable:
                for call in group:
                    if call["error"] is not None and results[call["idx"]] is None:
                        results[call["idx"]] = call["error"]
                continue

            # 并行执行组内工具
            tasks = [self._execute_tool_internal(c["tc"], c["name"], c["args"]) for c in executable]
            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            for call, gr in zip(executable, group_results):
                if isinstance(gr, Exception):
                    results[call["idx"]] = ToolResult(
                        success=False, output="", error=f"工具执行异常: {gr}"
                    )
                else:
                    results[call["idx"]] = gr

            # 处理组内错误调用
            for call in group:
                if call["error"] is not None and results[call["idx"]] is None:
                    results[call["idx"]] = call["error"]

        return results

    def _group_calls_by_dependency(self, parsed_calls: list[dict]) -> list[list[dict]]:
        """
        依赖分析：将工具调用分组。
        - 写同一文件的工具必须在同一组（串行执行）
        - execute_command 与任何写工具必须在同一组
        - 读工具可以独立分组（并行执行）
        """
        write_tools = {"write_file", "edit_file"}
        command_tool = "execute_command"

        # 收集所有写操作涉及的文件和命令
        write_files: dict[str, list[int]] = {}  # file_path -> [call_idx]
        has_command = False
        for call in parsed_calls:
            if call["error"] is not None:
                continue
            if call["name"] in write_tools:
                fp = call["args"].get("file_path", "")
                if fp:
                    write_files.setdefault(fp, []).append(call["idx"])
            elif call["name"] == command_tool:
                has_command = True

        # 使用并查集合并有依赖的调用
        parent = {i: i for i in range(len(parsed_calls))}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        # 同一文件的写操作合并
        for fp, indices in write_files.items():
            for i in range(1, len(indices)):
                union(indices[0], indices[i])

        # 所有写操作和命令操作合并到一组（命令可能修改任意文件）
        all_write_indices = [i for i, c in enumerate(parsed_calls)
                             if c["error"] is None and c["name"] in write_tools]
        command_indices = [i for i, c in enumerate(parsed_calls)
                           if c["error"] is None and c["name"] == command_tool]

        if all_write_indices or command_indices:
            base = all_write_indices[0] if all_write_indices else command_indices[0]
            for idx in all_write_indices + command_indices:
                union(base, idx)

        # 按组分类
        groups_map: dict[int, list[dict]] = {}
        for i, call in enumerate(parsed_calls):
            root = find(i)
            groups_map.setdefault(root, []).append(call)

        # 排序：写组优先（避免读操作看到中间状态）
        def group_priority(group):
            for c in group:
                if c["error"] is None and (c["name"] in write_tools or c["name"] == command_tool):
                    return 0
            return 1

        return sorted(groups_map.values(), key=group_priority)

    async def _check_permission_and_confirm(self, func_name: str, func_args: dict) -> bool:
        """权限检查和用户确认（串行调用）"""
        # PreToolUse 钩子
        hook_allowed, hook_message = await self.hooks.on_pre_tool_use(func_name, func_args)
        if not hook_allowed:
            return False

        # 权限引擎检查
        perm_approved, perm_reason = self.permission_engine.check_tool(func_name, func_args)
        if not perm_approved:
            if self.permission_engine.mode == PermissionMode.PLAN:
                return False
            if self.on_tool_call:
                approved = await self.on_tool_call(func_name, func_args)
                if not approved:
                    return False
        else:
            pass

        # execute_command 危险命令二次确认
        if func_name == "execute_command" and not perm_approved:
            command = func_args.get("command", "")
            if self.sandbox.needs_approval(command):
                if self.on_tool_call:
                    approved = await self.on_tool_call(
                        func_name,
                        {**func_args, "_requires_approval": True, "_reason": "危险命令"},
                    )
                    if not approved:
                        return False

        return True

    async def _execute_tool_internal(self, tool_call: dict, func_name: str, func_args: dict):
        """工具实际执行（不含权限检查，用于并行执行）"""
        from tools.base import ToolResult

        # 查找工具
        tool = tool_registry.get(func_name)
        if tool is None:
            return ToolResult(success=False, output="", error=f"未知工具: {func_name}")

        # 记录工具调用（加锁保护共享状态）
        async with self._state_lock:
            self._current_tool_calls.append(func_name)

        # 时空回溯：写操作前自动快照（串行化快照避免竞争）
        async with self._state_lock:
            if func_name in ("write_file", "edit_file"):
                file_path = func_args.get("file_path", "")
                if file_path:
                    try:
                        resolved = self.sandbox.resolve_path(file_path)
                        rel_path = str(resolved.relative_to(self.sandbox.project_root))
                        sid = self.snapshot.take_snapshot(
                            self.session_map.current_step_id, [rel_path]
                        )
                        if sid:
                            self._current_snapshot_ids.append(sid)
                    except (PermissionError, ValueError):
                        pass
            elif func_name == "execute_command":
                sid = self.snapshot.take_full_snapshot(self.session_map.current_step_id)
                if sid:
                    self._current_snapshot_ids.append(sid)

        # 执行工具
        try:
            result = await tool.execute(**func_args)
        except Exception as e:
            result = ToolResult(
                success=False, output="", error=f"工具执行异常: {e}"
            )

        # 记录修改的文件（加锁）
        if result.success and func_name in ("write_file", "edit_file"):
            file_path = func_args.get("file_path", "")
            if file_path:
                try:
                    resolved = self.sandbox.resolve_path(file_path)
                    rel_path = str(resolved.relative_to(self.sandbox.project_root))
                    async with self._state_lock:
                        if rel_path not in self._current_files_modified:
                            self._current_files_modified.append(rel_path)
                except (PermissionError, ValueError):
                    pass

        # 通知 UI 层（加锁保护 UI 输出顺序）
        if self.on_tool_result:
            async with self._ui_lock:
                await self.on_tool_result(
                    func_name,
                    result.output if result.success else result.error,
                    result.success,
                    result.metadata,
                )

        # 钩子：PostToolUse
        await self.hooks.on_post_tool_use(
            func_name, func_args,
            {"success": result.success, "output": result.output, "error": result.error}
        )

        return result

    async def _execute_tool(self, tool_call: dict) -> "ToolResult":
        """执行单个工具调用"""
        from tools.base import ToolResult

        func_name = tool_call["function"]["name"]
        func_args_str = tool_call["function"].get("arguments", "{}")

        # 解析参数
        try:
            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
        except json.JSONDecodeError:
            return ToolResult(
                success=False, output="", error=f"工具参数 JSON 解析失败: {func_args_str}"
            )

        # 查找工具
        tool = tool_registry.get(func_name)
        if tool is None:
            return ToolResult(
                success=False, output="", error=f"未知工具: {func_name}"
            )

        # 按需激活：如果工具存在但未激活，自动激活
        tool_registry.activate_tool(func_name)

        # 记录工具调用
        self._current_tool_calls.append(func_name)

        # 时空回溯：写操作前自动快照
        if func_name in ("write_file", "edit_file"):
            file_path = func_args.get("file_path", "")
            if file_path:
                try:
                    resolved = self.sandbox.resolve_path(file_path)
                    rel_path = str(resolved.relative_to(self.sandbox.project_root))
                    sid = self.snapshot.take_snapshot(
                        self.session_map.current_step_id, [rel_path]
                    )
                    if sid:
                        self._current_snapshot_ids.append(sid)
                except (PermissionError, ValueError):
                    pass
        elif func_name == "execute_command":
            # 命令执行前做全工作区哈希快照
            sid = self.snapshot.take_full_snapshot(self.session_map.current_step_id)
            if sid:
                self._current_snapshot_ids.append(sid)

        # 钩子：PreToolUse — 可阻止工具执行
        hook_allowed, hook_message = await self.hooks.on_pre_tool_use(func_name, func_args)
        if not hook_allowed:
            return ToolResult(
                success=False, output="", error=hook_message or "钩子阻止了工具执行"
            )

        # 权限引擎检查
        perm_approved, perm_reason = self.permission_engine.check_tool(func_name, func_args)
        if not perm_approved:
            # plan 模式或 deny 规则：直接拒绝
            if self.permission_engine.mode == PermissionMode.PLAN:
                return ToolResult(
                    success=False, output="", error=perm_reason or "权限不足"
                )
            # default/acceptEdits 模式：需要用户确认
            if self.on_tool_call:
                approved = await self.on_tool_call(func_name, func_args)
                if not approved:
                    return ToolResult(
                        success=False, output="", error="用户取消了工具调用"
                    )
        else:
            # 权限引擎批准：跳过 UI 确认（auto/bypass 模式）
            pass

        # 特殊处理：execute_command 需要用户确认（仅 default 模式下未自动批准时）
        if func_name == "execute_command" and not perm_approved:
            command = func_args.get("command", "")
            if self.sandbox.needs_approval(command):
                if self.on_tool_call:
                    approved = await self.on_tool_call(
                        func_name,
                        {**func_args, "_requires_approval": True, "_reason": "危险命令"},
                    )
                    if not approved:
                        return ToolResult(
                            success=False, output="", error="用户拒绝了命令执行"
                        )

        # 执行工具
        try:
            result = await tool.execute(**func_args)
        except Exception as e:
            result = ToolResult(
                success=False, output="", error=f"工具执行异常: {e}"
            )

        # 记录修改的文件
        if result.success and func_name in ("write_file", "edit_file"):
            file_path = func_args.get("file_path", "")
            if file_path:
                try:
                    resolved = self.sandbox.resolve_path(file_path)
                    rel_path = str(resolved.relative_to(self.sandbox.project_root))
                    if rel_path not in self._current_files_modified:
                        self._current_files_modified.append(rel_path)
                except (PermissionError, ValueError):
                    pass

        # 通知 UI 层
        if self.on_tool_result:
            await self.on_tool_result(
                func_name,
                result.output if result.success else result.error,
                result.success,
                result.metadata,
            )

        # 钩子：PostToolUse
        await self.hooks.on_post_tool_use(
            func_name, func_args,
            {"success": result.success, "output": result.output, "error": result.error}
        )

        return result

    def _record_step(self, step_id: int, user_input: str) -> None:
        """记录当前步骤的完整状态到 SessionMap"""
        summary = self.session_map.build_step_summary(StepRecord(
            step_id=step_id,
            user_input=user_input,
            summary="",
            tool_calls=self._current_tool_calls,
            files_modified=self._current_files_modified,
        ))

        record = StepRecord(
            step_id=step_id,
            user_input=user_input,
            summary=summary,
            snapshot_ids=list(self._current_snapshot_ids),
            messages_snapshot=self.memory.snapshot_messages(),
            tool_calls=list(self._current_tool_calls),
            files_modified=list(self._current_files_modified),
        )
        self.session_map.record_step(record)

    def reset(self) -> None:
        """重置对话历史和状态"""
        self.memory.clear()
        self.session_map.clear()
        # 同时删除持久化存档
        cfg = get_config()
        if cfg.persistence.persist_conversation:
            persistence = ConversationPersistence(self.workspace_root)
            persistence.delete()

    def switch_model(self, model_name: str) -> None:
        """
        运行时切换模型。

        Args:
            model_name: 模型名称，如 "gpt-4o" 或 "deepseek/deepseek-chat"
        """
        new_config = ModelConfig(
            provider=self.cfg.model.provider,
            name=model_name,
            api_key=self.cfg.model.api_key,
            api_base=self.cfg.model.api_base,
            temperature=self.cfg.model.temperature,
            max_tokens=self.cfg.model.max_tokens,
            timeout=self.cfg.model.timeout,
        )
        self.llm.reconfigure(new_config)
        self.cfg.model.name = model_name
        self._debug.log("agent", f"模型已切换为: {model_name}")

    async def compact_context(self) -> Optional[dict]:
        """使用 LLM 压缩对话上下文，释放 Token 空间"""
        return await self.memory.llm_compress(self.llm)

    def get_token_usage(self) -> dict:
        """获取当前会话的 Token 用量统计（纯读取，不触发记录）"""
        llm_usage = self.llm.get_usage()
        return {
            "prompt_tokens": llm_usage["prompt_tokens"],
            "completion_tokens": llm_usage["completion_tokens"],
            "total_tokens": llm_usage["total_tokens"],
            "request_count": llm_usage["request_count"],
            "context_usage_pct": self.memory.get_context_usage_pct(),
        }

    def record_token_usage(self) -> dict:
        """
        记录增量 token 用量到 CostTracker。
        使用 LLMClient.get_usage_delta() 获取自上次记录以来的增量，避免重复计数。
        应在每次 LLM 调用完成后（finish 事件）调用。
        """
        delta = self.llm.get_usage_delta()
        if self.cost_tracker.enabled and delta["total_tokens"] > 0:
            try:
                self.cost_tracker.record(
                    model_name=self.cfg.model.name,
                    prompt_tokens=delta["prompt_tokens"],
                    completion_tokens=delta["completion_tokens"],
                    session_id=self._session_id,
                )
            except Exception:
                pass
        return delta

    def save_conversation(self) -> None:
        """持久化当前对话状态到磁盘"""
        cfg = get_config()
        if not cfg.persistence.persist_conversation:
            return
        persistence = ConversationPersistence(self.workspace_root)
        persistence.save(self.memory, self.session_map)

        # 更新会话索引
        session_id = self._session_id or SessionIndex.generate_id()
        self._session_id = session_id
        name = self.session_name or f"会话 {session_id[:8]}"
        steps = self.session_map.get_all_steps()
        self.session_index.register_session(
            session_id=session_id,
            name=name,
            workspace=self.workspace_root,
            step_count=len(steps),
        )

    async def notify_session_end(self) -> None:
        """发送会话结束通知（由 UI 层在退出前调用）"""
        if self._session_started:
            await self.hooks.on_notification("session_end", {
                "workspace": str(self.workspace_root),
                "total_steps": self.session_map.current_step_id,
            })
        # 停止 MCP 服务器
        if self.mcp_manager:
            try:
                await self.mcp_manager.stop_all()
            except Exception as e:
                self._debug.log("agent", f"停止 MCP 失败: {e}")

    def load_conversation(self, resume_id: str = "latest") -> Optional[dict]:
        """
        从磁盘恢复对话状态。

        Args:
            resume_id: 会话 ID 或 "latest"

        Returns:
            恢复摘要信息 dict，供 UI 层展示；如果无存档则返回 None。
        """
        cfg = get_config()
        if not cfg.persistence.persist_conversation:
            return None

        # 如果是 "latest"，从索引获取最新会话
        if resume_id == "latest":
            latest = self.session_index.get_latest(self.workspace_root)
            if latest:
                resume_id = latest["id"]
            else:
                return None

        self._session_id = resume_id

        persistence = ConversationPersistence(self.workspace_root)
        data = persistence.load()
        if data is None:
            return None

        # 恢复 memory
        mem_data = data.get("memory", {})
        self.memory.messages = mem_data.get("messages", [])
        self.memory.summary = mem_data.get("summary", None)

        # 恢复 session_map
        sm_data = data.get("session_map", {})
        self.session_map.clear()
        self.session_map._current_step_id = sm_data.get("current_step_id", 0)
        for step_data in sm_data.get("steps", []):
            record = StepRecord(
                step_id=step_data["step_id"],
                user_input=step_data["user_input"],
                summary=step_data["summary"],
                snapshot_ids=step_data.get("snapshot_ids", []),
                messages_snapshot=step_data.get("messages_snapshot", []),
                tool_calls=step_data.get("tool_calls", []),
                files_modified=step_data.get("files_modified", []),
                timestamp=step_data.get("timestamp", ""),
            )
            self.session_map._steps[record.step_id] = record

        # 构建摘要信息供 UI 展示
        steps = self.session_map.get_all_steps()
        last_exchanges = []
        user_msgs = [m for m in self.memory.messages if m.get("role") == "user"]
        assistant_msgs = [m for m in self.memory.messages if m.get("role") == "assistant"]

        for i in range(max(0, len(user_msgs) - 3), len(user_msgs)):
            user_content = user_msgs[i].get("content", "")[:100]
            assistant_content = ""
            if i < len(assistant_msgs):
                assistant_content = assistant_msgs[i].get("content", "") or ""
                if not assistant_content:
                    tc_names = [
                        tc["function"]["name"]
                        for tc in assistant_msgs[i].get("tool_calls", [])
                    ]
                    assistant_content = f"[工具调用: {', '.join(tc_names)}]"
                assistant_content = assistant_content[:100]
            last_exchanges.append({
                "user": user_content,
                "assistant_preview": assistant_content,
            })

        return {
            "step_count": len(steps),
            "message_count": len(self.memory.messages),
            "saved_at": data.get("saved_at", "未知"),
            "last_exchanges": last_exchanges,
        }

    def rewind_to_step(self, target_step_id: int) -> dict:
        """
        时空回溯：回滚到指定步骤。

        执行双重清理：
        a) 物理文件还原
        b) 记忆截断

        Returns:
            {"success": bool, "files_restored": [...], "warnings": [...], "target_step": int}
        """
        result = {
            "success": True,
            "files_restored": [],
            "warnings": [],
            "target_step": target_step_id,
        }

        target_record = self.session_map.get_step(target_step_id)
        if target_record is None:
            result["success"] = False
            result["warnings"].append(f"步骤 {target_step_id} 不存在")
            return result

        # 获取需要回滚的步骤
        steps_after = self.session_map.get_steps_after(target_step_id)

        # a) 物理文件还原：反向遍历，从最新到最旧还原
        restored_files = set()
        for record in reversed(steps_after):
            if self.session_map.is_readonly_step(record):
                continue

            for sid in reversed(record.snapshot_ids):
                if not self.snapshot.verify_snapshot(sid):
                    result["warnings"].append(
                        f"[yellow]⚠ 快照 {sid} (Step {record.step_id}) 文件缺失，"
                        f"部分文件可能无法还原[/yellow]"
                    )
                    continue

                files = self.snapshot.restore_snapshot(sid)
                for f in files:
                    if f not in restored_files:
                        restored_files.add(f)
                        result["files_restored"].append(f)

        # b) 记忆截断：精确截断到目标步骤结束时的状态
        self.memory.truncate_to_step(target_record.messages_snapshot)

        # c) 清理废弃快照
        self.snapshot.delete_snapshots_after(target_step_id)

        # d) 截断 SessionMap
        self.session_map.truncate_after(target_step_id)

        return result
