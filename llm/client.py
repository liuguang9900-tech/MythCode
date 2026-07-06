"""
统一 LLM 客户端 — 基于 LiteLLM 的多模型接入层。
支持流式输出、Function Calling、自动重试、错误脱敏、fallback 模型。
"""

import asyncio
import logging
import re
from typing import AsyncIterator, Optional

from litellm import acompletion

from config import get_config, ModelConfig
from llm.token_counter import get_token_counter

logger = logging.getLogger(__name__)


# 需要重试的异常模式（429 限流、5xx 服务端错误、网络超时）
_RETRYABLE_PATTERNS = [
    r"429",
    r"rate.?limit",
    r"too many requests",
    r"500",
    r"502",
    r"503",
    r"504",
    r"internal server error",
    r"bad gateway",
    r"service unavailable",
    r"gateway timeout",
    r"timeout",
    r"timed? out",
    r"connection (reset|refused|closed)",
    r"temporary failure",
]


def _is_retryable(error: Exception) -> bool:
    """判断异常是否可重试"""
    err_str = str(error).lower()
    return any(re.search(p, err_str) for p in _RETRYABLE_PATTERNS)


def _sanitize_error(error: Exception) -> str:
    """脱敏错误信息，移除 API Key、Authorization 等敏感字段"""
    msg = str(error)
    # 移除 api_key=xxx
    msg = re.sub(r"api_key[=:]\s*['\"]?[^\s'\"]+['\"]?", "api_key=***", msg, flags=re.IGNORECASE)
    # 移除 Authorization: Bearer xxx
    msg = re.sub(r"authorization[=:]\s*['\"]?bearer\s+[^\s'\"]+['\"]?", "authorization=***", msg, flags=re.IGNORECASE)
    # 移除 sk-xxx 格式的密钥
    msg = re.sub(r"sk-[a-zA-Z0-9]{20,}", "sk-***", msg)
    # 移除 token=xxx
    msg = re.sub(r"token[=:]\s*['\"]?[^\s'\"]+['\"]?", "token=***", msg, flags=re.IGNORECASE)
    return msg


class LLMClient:
    """统一大模型客户端（生产级：重试 + 脱敏 + fallback）"""

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or get_config().model
        self.token_counter = get_token_counter(self.config.name)
        # Token 用量统计（会话累计值）
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._request_count = 0
        # 上次记录的快照，用于计算增量（避免重复计数）
        self._last_recorded_prompt = 0
        self._last_recorded_completion = 0
        self._last_recorded_request_count = 0
        # 重试配置
        self._max_retries = 3
        self._retry_base_delay = 1.0  # 基础延迟（秒）
        self._retry_max_delay = 30.0  # 最大延迟（秒）
        # fallback 模型配置（可选）
        self._fallback_config: Optional[ModelConfig] = None

    def set_fallback(self, config: ModelConfig) -> None:
        """设置 fallback 模型（主模型失败时切换）"""
        self._fallback_config = config
        logger.info(f"已设置 fallback 模型: {config.provider}/{config.name}")

    def reconfigure(self, config: ModelConfig) -> None:
        """运行时重新配置模型参数"""
        self.config = config
        self.token_counter = get_token_counter(config.name)

    def reset_usage(self) -> None:
        """重置 Token 用量统计（同步重置快照）"""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._request_count = 0
        self._last_recorded_prompt = 0
        self._last_recorded_completion = 0
        self._last_recorded_request_count = 0

    def get_usage(self) -> dict:
        """获取 Token 用量统计（累计快照，纯读取，不触发记录）"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "request_count": self._request_count,
        }

    def get_usage_delta(self) -> dict:
        """
        获取自上次调用以来的增量用量（用于 record，避免重复计数）。
        每次调用会更新快照，二次调用无新增时返回 0。
        """
        delta_prompt = self.prompt_tokens - self._last_recorded_prompt
        delta_completion = self.completion_tokens - self._last_recorded_completion
        delta_requests = self._request_count - self._last_recorded_request_count
        # 更新快照
        self._last_recorded_prompt = self.prompt_tokens
        self._last_recorded_completion = self.completion_tokens
        self._last_recorded_request_count = self._request_count
        return {
            "prompt_tokens": delta_prompt,
            "completion_tokens": delta_completion,
            "total_tokens": delta_prompt + delta_completion,
            "request_count": delta_requests,
        }

    async def chat_simple(
        self,
        system: str,
        user: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        简单对话接口：发送 system + user 消息，返回文本回复。
        用于 /init, /review, /commit 等命令的内部 LLM 调用。
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs = {
            "model": self._build_model_id(),
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "timeout": self.config.timeout,
            "stream": False,
            "api_key": self.config.api_key,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base

        response = await self._call_with_retry(kwargs)
        choice = response.choices[0] if response.choices else None
        if choice and choice.message.content:
            # 统计用量
            if hasattr(response, "usage") and response.usage:
                self.prompt_tokens += response.usage.prompt_tokens or 0
                self.completion_tokens += response.usage.completion_tokens or 0
            self._request_count += 1
            return choice.message.content
        return ""

    def _build_model_id(self) -> str:
        """构建 LiteLLM 格式的模型标识符"""
        provider = self.config.provider
        name = self.config.name
        if "/" in name:
            return name
        return f"{provider}/{name}"

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = True,
    ) -> AsyncIterator[dict]:
        """
        发送聊天请求，返回流式响应迭代器。

        每个 yield 的 dict 包含:
          - "type": "text_delta" | "tool_call" | "finish"
          - 对应字段: "content" / "tool_call" / "finish_reason"
        """
        kwargs = {
            "model": self._build_model_id(),
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "stream": stream,
            "api_key": self.config.api_key,
        }
        # 流式响应需要显式请求 usage 数据（OpenAI 兼容 API 默认不返回）
        if stream:
            kwargs["stream_options"] = {"include_usage": True}

        # 自定义 API 地址
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream:
            async for chunk in self._stream_response(**kwargs):
                yield chunk
        else:
            response = await self._call_with_retry(kwargs)
            for item in self._parse_non_stream_response(response):
                yield item

    async def _call_with_retry(self, kwargs: dict) -> any:
        """带重试的 LLM 调用（非流式）"""
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return await acompletion(**kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self._max_retries and _is_retryable(e):
                    delay = min(
                        self._retry_base_delay * (2 ** attempt),
                        self._retry_max_delay,
                    )
                    logger.warning(
                        f"LLM 调用失败（第 {attempt + 1} 次），{delay:.1f}s 后重试: {_sanitize_error(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    break

        # 尝试 fallback 模型
        if self._fallback_config is not None:
            logger.warning(f"主模型失败，切换到 fallback: {self._fallback_config.provider}/{self._fallback_config.name}")
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["model"] = f"{self._fallback_config.provider}/{self._fallback_config.name}"
            fallback_kwargs["api_key"] = self._fallback_config.api_key
            if self._fallback_config.api_base:
                fallback_kwargs["api_base"] = self._fallback_config.api_base
            try:
                return await acompletion(**fallback_kwargs)
            except Exception as e:
                last_error = e

        raise RuntimeError(f"LLM 调用失败（已重试 {self._max_retries} 次）: {_sanitize_error(last_error)}")

    async def _stream_response(self, **kwargs) -> AsyncIterator[dict]:
        """处理流式响应（带重试）"""
        accumulated_tool_calls: dict[int, dict] = {}
        last_error = None

        for attempt in range(self._max_retries + 1):
            accumulated_tool_calls = {}
            try:
                response = await acompletion(**kwargs)
                async for chunk in response:
                    # usage 数据通常在最后一个 chunk（choices 可能为空）
                    if hasattr(chunk, "usage") and chunk.usage:
                        self.prompt_tokens += chunk.usage.prompt_tokens or 0
                        self.completion_tokens += chunk.usage.completion_tokens or 0

                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # 文本增量
                    if delta.content:
                        yield {"type": "text_delta", "content": delta.content}

                    # 工具调用增量
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.id:
                                accumulated_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    accumulated_tool_calls[idx]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                    # 结束
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                    if finish_reason:
                        self._request_count += 1
                        if accumulated_tool_calls:
                            for tc in sorted(accumulated_tool_calls.values(), key=lambda x: x.get("index", 0)):
                                yield {"type": "tool_call", "tool_call": tc}
                        yield {"type": "finish", "finish_reason": finish_reason}
                return  # 成功完成，退出重试循环

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self._max_retries and _is_retryable(e):
                    delay = min(
                        self._retry_base_delay * (2 ** attempt),
                        self._retry_max_delay,
                    )
                    logger.warning(
                        f"流式响应失败（第 {attempt + 1} 次），{delay:.1f}s 后重试: {_sanitize_error(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    break

        # 尝试 fallback 模型
        if self._fallback_config is not None:
            logger.warning(f"主模型流式失败，切换到 fallback: {self._fallback_config.provider}/{self._fallback_config.name}")
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["model"] = f"{self._fallback_config.provider}/{self._fallback_config.name}"
            fallback_kwargs["api_key"] = self._fallback_config.api_key
            if self._fallback_config.api_base:
                fallback_kwargs["api_base"] = self._fallback_config.api_base
            try:
                response = await acompletion(**fallback_kwargs)
                async for chunk in response:
                    # usage 数据通常在最后一个 chunk（choices 可能为空）
                    if hasattr(chunk, "usage") and chunk.usage:
                        self.prompt_tokens += chunk.usage.prompt_tokens or 0
                        self.completion_tokens += chunk.usage.completion_tokens or 0
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue
                    if delta.content:
                        yield {"type": "text_delta", "content": delta.content}
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.id:
                                accumulated_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    accumulated_tool_calls[idx]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                    if finish_reason:
                        self._request_count += 1
                        if accumulated_tool_calls:
                            for tc in sorted(accumulated_tool_calls.values(), key=lambda x: x.get("index", 0)):
                                yield {"type": "tool_call", "tool_call": tc}
                        yield {"type": "finish", "finish_reason": finish_reason}
                return
            except Exception as e:
                last_error = e

        yield {"type": "error", "error": _sanitize_error(last_error)}

    def _parse_non_stream_response(self, response) -> list[dict]:
        """解析非流式响应"""
        results = []
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return [{"type": "error", "error": "空响应"}]

        if choice.message.content:
            results.append({"type": "text_delta", "content": choice.message.content})

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                results.append({
                    "type": "tool_call",
                    "tool_call": {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    },
                })

        results.append({
            "type": "finish",
            "finish_reason": choice.finish_reason or "stop",
        })
        return results

    def estimate_tokens(self, messages: list[dict]) -> int:
        """估算消息列表的 Token 数"""
        return self.token_counter.count_messages(messages)
