"""
工具基类 — 定义所有工具的抽象接口和通用逻辑。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str                          # 返回给 LLM 的文本
    error: Optional[str] = None          # 错误信息（如有）
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据


class BaseTool(ABC):
    """工具抽象基类"""

    name: str = ""                       # 工具名称（唯一标识）
    description: str = ""                # 工具描述（给 LLM 看）
    parameters: dict[str, Any] = {}      # JSON Schema 参数定义

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑，子类必须实现"""
        ...

    def to_openai_schema(self) -> dict:
        """生成 OpenAI Function Calling 格式的 JSON Schema"""
        # 清理参数：移除参数内部的 "required" 字段（它只能出现在顶层 required 数组中）
        clean_properties = {}
        required_params = []
        for name, schema in self.parameters.items():
            if isinstance(schema, dict):
                clean = {k: v for k, v in schema.items() if k != "required"}
                clean_properties[name] = clean
                if schema.get("required"):
                    required_params.append(name)
            else:
                clean_properties[name] = schema

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": clean_properties,
                    "required": required_params,
                },
            },
        }
