"""
Token 计数器 — 基于 tiktoken 的 Token 估算。
"""

from typing import Optional

import tiktoken


class TokenCounter:
    """Token 计数工具，用于上下文窗口管理"""

    # 常用模型编码映射
    MODEL_ENCODING = {
        "gpt-4": "cl100k_base",
        "gpt-4o": "o200k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "claude": "cl100k_base",  # Claude 近似
    }

    def __init__(self, model_name: str = "gpt-4o"):
        encoding_name = self.MODEL_ENCODING.get(model_name, "cl100k_base")
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        """计算文本的 Token 数"""
        return len(self.encoder.encode(text))

    def count_messages(self, messages: list[dict]) -> int:
        """
        估算一组消息的总 Token 数。
        参考 OpenAI 的计数规则：每条消息有固定开销 + 内容 Token。
        """
        total = 0
        for msg in messages:
            # 每条消息的基础开销
            total += 4
            for key, value in msg.items():
                if value is None:
                    continue
                if isinstance(value, str):
                    total += self.count(value)
                elif isinstance(value, list):
                    # tool_calls 等复杂结构
                    total += self.count(str(value))
        total += 2  # 回复 priming
        return total


# 全局计数器
_counter: Optional[TokenCounter] = None


def get_token_counter(model_name: str = "gpt-4o") -> TokenCounter:
    global _counter
    if _counter is None:
        _counter = TokenCounter(model_name)
    return _counter
