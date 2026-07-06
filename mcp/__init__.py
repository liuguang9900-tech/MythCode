"""
MCP (Model Context Protocol) 支持。
- client.py: MCPClient 单服务器客户端
- manager.py: MCPManager 管理多服务器
- wrapper.py: MCPToolWrapper 包装 MCP 工具为 BaseTool
"""

from mcp.client import MCPClient
from mcp.manager import MCPManager
from mcp.wrapper import MCPToolWrapper

__all__ = ["MCPClient", "MCPManager", "MCPToolWrapper"]
