"""
对话历史管理 — 滑动窗口 + Token 估算 + 摘要压缩。
线程安全：使用 asyncio.Lock 保护并发修改。
"""

import asyncio
from typing import Optional

from config import get_config
from llm.token_counter import get_token_counter


class ConversationMemory:
    """对话历史管理器（线程安全）"""

    def __init__(self, model_name: str = "gpt-4o"):
        cfg = get_config()
        self.max_turns = cfg.agent.history_max_turns
        self.context_window = cfg.agent.context_window
        self.summary_threshold = cfg.agent.summary_threshold
        self.max_tool_result_tokens = getattr(cfg.agent, "max_tool_result_tokens", 4000)
        self.preserve_important = getattr(cfg.agent, "preserve_important_messages", True)
        # 嵌套压缩：当累积摘要本身超过此 token 阈值时，对摘要再压缩
        self.max_summary_tokens = getattr(cfg.agent, "max_summary_tokens", 800)
        self.max_compress_iterations = getattr(cfg.agent, "max_compress_iterations", 3)
        self.token_counter = get_token_counter(model_name)

        self.messages: list[dict] = []       # 完整消息列表
        self.summary: Optional[str] = None    # 压缩摘要
        self.important_messages: set[int] = set()  # 重要消息索引（不被压缩）
        self._lock = asyncio.Lock()           # 保护并发修改

    async def add_message_async(self, role: str, content: str, **kwargs) -> None:
        """异步添加一条消息到历史（线程安全）"""
        async with self._lock:
            msg = {"role": role, "content": content, **kwargs}
            self.messages.append(msg)
            self._maybe_compress()

    async def add_tool_result_async(self, tool_call_id: str, content: str) -> None:
        """异步添加工具调用结果（线程安全）"""
        async with self._lock:
            truncated = self._truncate_tool_result(content)
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": truncated,
            })

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """添加一条消息到历史（向后兼容，非并发场景使用）"""
        msg = {"role": role, "content": content, **kwargs}
        self.messages.append(msg)
        self._maybe_compress()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """添加工具调用结果（含智能截断）"""
        truncated = self._truncate_tool_result(content)
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": truncated,
        })

    def mark_important(self, msg_idx: int) -> None:
        """标记消息为重要（不被压缩）"""
        if 0 <= msg_idx < len(self.messages):
            self.important_messages.add(msg_idx)

    def _truncate_tool_result(self, content: str) -> str:
        """智能截断工具结果（保留头尾）"""
        if not content:
            return content

        # 估算 token 数（1 token ≈ 4 字符）
        max_chars = self.max_tool_result_tokens * 4
        if len(content) <= max_chars:
            return content

        # 保留头部 70% 和尾部 30%
        head_chars = int(max_chars * 0.7)
        tail_chars = max_chars - head_chars

        head = content[:head_chars]
        tail = content[-tail_chars:]
        skipped = len(content) - max_chars

        return f"{head}\n\n... (已截断 {skipped} 字符) ...\n\n{tail}"

    def get_messages(self) -> list[dict]:
        """获取当前有效的消息列表（含摘要 + 旧工具结果摘要化）"""
        messages = list(self.messages)

        # 对非最近一轮的工具结果进行摘要化，大幅减少 token 消耗
        messages = self._summarize_old_tool_results(messages)

        if self.summary:
            summary_msg = {
                "role": "system",
                "content": f"[对话历史摘要]\n{self.summary}",
            }
            return [summary_msg] + messages
        return messages

    def _summarize_old_tool_results(self, messages: list[dict]) -> list[dict]:
        """
        将非最近一轮的工具结果替换为简短摘要。
        最近一轮（最后一个 assistant 消息之前的）工具结果保持完整。
        早期工具结果只保留前 100 字符 + 字符数提示。
        """
        if len(messages) < 6:
            return messages

        # 找到最后一个 assistant 消息的索引（作为"最近一轮"的起点）
        last_assistant_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                last_assistant_idx = i
                break

        # 最近一轮的工具结果范围：保留最后 4 条消息中的工具结果完整，更早的摘要化
        recent_threshold = max(0, len(messages) - 4)

        result = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "tool" and i < recent_threshold:
                content = msg.get("content", "")
                # 已经是摘要的跳过
                if content.startswith("[工具结果摘要]") or len(content) <= 100:
                    result.append(msg)
                else:
                    # 替换为摘要（仅保留前 100 字符）
                    preview = content[:100].replace("\n", " ")
                    char_count = len(content)
                    summarized = {
                        **msg,
                        "content": f"[工具结果摘要] {preview}... (共 {char_count} 字符，已省略)",
                    }
                    result.append(summarized)
            else:
                result.append(msg)

        return result

    def estimate_tokens(self) -> int:
        """估算当前消息列表的总 Token 数"""
        return self.token_counter.count_messages(self.get_messages())

    def is_near_limit(self) -> bool:
        """检查是否接近上下文窗口限制"""
        ratio = self.estimate_tokens() / self.context_window
        return ratio >= self.summary_threshold

    def get_context_usage_pct(self) -> float:
        """获取上下文窗口使用百分比"""
        return (self.estimate_tokens() / self.context_window) * 100

    async def llm_compress(self, llm_client) -> Optional[dict]:
        """
        使用 LLM 生成高质量对话摘要，替换早期消息。
        重要消息（important_messages）会被保留，不参与压缩。
        返回压缩结果统计。
        """
        if len(self.messages) < 6:
            return None

        # 保留最近 4 条消息
        keep_count = 4
        # 计算可压缩范围：除最近 keep_count 条之外的消息
        compressible_range = self._get_compressible_indices(end_exclusive=len(self.messages) - keep_count)
        if not compressible_range:
            return None

        to_compress = [self.messages[i] for i in compressible_range]
        compress_indices = compressible_range

        # 构建压缩 prompt
        conversation_text = []
        for msg in to_compress:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if msg.get("tool_calls"):
                tools = [tc["function"]["name"] for tc in msg["tool_calls"]]
                content = f"[调用工具: {', '.join(tools)}]"
            conversation_text.append(f"[{role}]: {content[:300]}")

        prompt = f"""请将以下对话历史压缩为简洁的摘要。保留：
- 用户的关键请求
- AI 执行的重要操作（工具调用、文件修改）
- 重要的发现或结论

对话历史：
{chr(10).join(conversation_text)}

请用中文输出摘要，不超过 500 字。"""

        try:
            summary = await llm_client.chat_simple(
                system="你是一个对话摘要助手。请简洁准确地总结对话内容。",
                user=prompt,
                max_tokens=500,
            )
            if summary:
                old_count = len(to_compress)
                # 从 messages 中移除被压缩的索引（倒序删除避免索引偏移）
                kept_messages = []
                for i, msg in enumerate(self.messages):
                    if i not in set(compress_indices):
                        kept_messages.append(msg)
                self.messages = kept_messages
                # 重建 important_messages 索引：被保留的重要消息重新计算新索引
                new_important: set[int] = set()
                old_to_new: dict[int, int] = {}
                new_idx = 0
                for old_idx in range(len(compress_indices) + len(self.messages)):
                    if old_idx in set(compress_indices):
                        continue
                    if old_idx in self.important_messages:
                        new_important.add(new_idx)
                    old_to_new[old_idx] = new_idx
                    new_idx += 1
                self.important_messages = new_important

                if self.summary:
                    self.summary = self.summary + "\n" + summary
                else:
                    self.summary = summary

                # 嵌套压缩：当累积摘要本身过大时，对摘要再压缩
                nested = await self._compress_summary_if_needed(llm_client)

                return {
                    "tokens_saved": self.token_counter.count_messages(to_compress),
                    "old_message_count": old_count,
                    "new_message_count": len(self.messages),
                    "summary_compressed": nested,
                }
        except Exception:
            pass

        return None

    async def _compress_summary_if_needed(self, llm_client) -> Optional[dict]:
        """
        嵌套压缩：当累积摘要本身超过 max_summary_tokens 时，对摘要再压缩。
        支持多次迭代压缩，直到摘要低于阈值或达到最大迭代次数。
        """
        if not self.summary:
            return None

        iterations = 0
        last_result = None
        while iterations < self.max_compress_iterations:
            summary_tokens = self.token_counter.count(self.summary)
            if summary_tokens <= self.max_summary_tokens:
                break
            iterations += 1

            try:
                compressed = await llm_client.chat_simple(
                    system="你是一个对话摘要助手。请将已有的对话摘要进一步浓缩，保留最关键的信息（用户核心请求、重要结论、关键决策），删除冗余细节。",
                    user=f"请将以下摘要压缩到更短（目标 {self.max_summary_tokens} tokens 以内）：\n\n{self.summary}",
                    max_tokens=self.max_summary_tokens,
                )
            except Exception:
                break

            if not compressed or len(compressed) >= len(self.summary):
                # 压缩无效果，停止
                break

            old_tokens = summary_tokens
            self.summary = compressed
            new_tokens = self.token_counter.count(self.summary)
            last_result = {
                "iteration": iterations,
                "old_tokens": old_tokens,
                "new_tokens": new_tokens,
                "tokens_saved": old_tokens - new_tokens,
            }

        return last_result

    def _get_compressible_indices(self, end_exclusive: int) -> list[int]:
        """获取可压缩的消息索引列表（排除重要消息）"""
        if self.preserve_important:
            return [i for i in range(end_exclusive) if i not in self.important_messages]
        return list(range(end_exclusive))

    def _maybe_compress(self) -> None:
        """如果 Token 数超过阈值，压缩早期消息为摘要"""
        if not self.is_near_limit():
            return

        # 保留最近 N 轮对话，压缩更早的消息
        keep_turns = max(2, self.max_turns // 3)
        keep_count = keep_turns * 2  # 每轮 = user + assistant

        if len(self.messages) <= keep_count:
            return

        compressible = self._get_compressible_indices(len(self.messages) - keep_count)
        if not compressible:
            return

        to_compress = [self.messages[i] for i in compressible]
        compress_set = set(compressible)

        # 保留未被压缩的消息
        kept = [msg for i, msg in enumerate(self.messages) if i not in compress_set]
        self.messages = kept

        # 重建 important_messages 索引
        new_important: set[int] = set()
        new_idx = 0
        for old_idx in range(len(kept) + len(compressible)):
            if old_idx in compress_set:
                continue
            if old_idx in self.important_messages:
                new_important.add(new_idx)
            new_idx += 1
        self.important_messages = new_important

        # 生成简单摘要（实际项目中可调用 LLM 生成更好的摘要）
        compressed_text = self._generate_summary(to_compress)
        if self.summary:
            self.summary = self.summary + "\n" + compressed_text
        else:
            self.summary = compressed_text

    @staticmethod
    def _generate_summary(messages: list[dict]) -> str:
        """生成对话摘要（简化版：提取关键操作）"""
        summary_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                summary_parts.append(f"用户请求: {content[:200]}")
            elif role == "assistant":
                if msg.get("tool_calls"):
                    tools = [tc["function"]["name"] for tc in msg.get("tool_calls", [])]
                    summary_parts.append(f"AI 调用了工具: {', '.join(tools)}")
                elif content:
                    summary_parts.append(f"AI 回复: {content[:200]}")
            elif role == "tool":
                summary_parts.append(f"工具返回: {content[:200]}")
        return "\n".join(summary_parts)

    def snapshot_messages(self) -> list[dict]:
        """获取当前消息列表的深拷贝（用于时空回溯）"""
        import copy
        return copy.deepcopy(self.messages)

    def restore_messages(self, messages: list[dict]) -> None:
        """从快照还原消息列表"""
        import copy
        self.messages = copy.deepcopy(messages)
        self.summary = None  # 还原时清除摘要，避免不一致
        self.important_messages.clear()  # 还原时清除重要标记

    def truncate_to_step(self, messages_snapshot: list[dict]) -> None:
        """
        将消息列表精确截断到指定步骤结束时的状态。
        同时清除摘要。
        """
        import copy
        self.messages = copy.deepcopy(messages_snapshot)
        self.summary = None
        # 截断后只保留在范围内的 important 索引
        self.important_messages = {i for i in self.important_messages if i < len(self.messages)}

    def clear(self) -> None:
        """清空历史"""
        self.messages.clear()
        self.summary = None
        self.important_messages.clear()
