"""
MCPToolWrapper — 将 MCP 工具包装为 BaseTool 子类。
"""

from typing import Any
from tools.base import BaseTool, ToolResult
from mcp.client import MCPClient, MCPError


class MCPToolWrapper(BaseTool):
    """将 MCP 服务器提供的工具包装为本地 BaseTool"""

    def __init__(self, client: MCPClient, tool_schema: dict):
        self._client = client
        self._tool_name = tool_schema.get("name", "")
        self.name = f"mcp__{client.name}__{self._tool_name}"
        self.description = tool_schema.get("description", "") or f"MCP 工具: {self._tool_name}"
        self.parameters = tool_schema.get("inputSchema", {}) or {}

    async def execute(self, **kwargs) -> ToolResult:
        """调用 MCP 服务器执行工具"""
        try:
            result = await self._client.call_tool(self._tool_name, kwargs)
            is_error = result.get("isError", False)
            content = result.get("content", "")

            # 处理 content 可能是列表的情况
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", str(item)))
                    else:
                        text_parts.append(str(item))
                content = "\n".join(text_parts)

            return ToolResult(
                success=not is_error,
                output=content if content else "(无输出)",
                error=result.get("error") if is_error else None,
                metadata={
                    "mcp_server": self._client.name,
                    "mcp_tool": self._tool_name,
                },
            )
        except MCPError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"MCP 工具调用失败: {e}",
                metadata={"mcp_server": self._client.name, "mcp_tool": self._tool_name},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"MCP 工具执行异常: {e}",
                metadata={"mcp_server": self._client.name, "mcp_tool": self._tool_name},
            )
