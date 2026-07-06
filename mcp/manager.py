"""
MCPManager — 管理多个 MCP 服务器。
从 .mcp.json 加载配置，启动服务器，注册工具到 ToolRegistry。
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from mcp.client import MCPClient
from mcp.wrapper import MCPToolWrapper
from tools.registry import registry as tool_registry
from utils.debug import get_debug_manager


class MCPManager:
    """MCP 服务器管理器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self._clients: dict[str, MCPClient] = {}
        self._debug = get_debug_manager()
        self._config: dict = {}

    def load_config(self) -> dict:
        """加载 .mcp.json 配置文件"""
        config_path = self.workspace_root / ".mcp.json"
        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            return self._config
        except (json.JSONDecodeError, OSError) as e:
            self._debug.log("agent", f"加载 .mcp.json 失败: {e}")
            return {}

    async def start_all(self) -> None:
        """启动所有配置的 MCP 服务器"""
        if not self._config:
            self.load_config()

        servers = self._config.get("mcpServers", {})
        if not servers:
            return

        tasks = []
        for name, config in servers.items():
            tasks.append(self._start_client(name, config))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _start_client(self, name: str, config: dict) -> None:
        """启动单个 MCP 客户端"""
        try:
            transport = config.get("transport", "stdio")
            command = config.get("command")
            args = config.get("args", [])
            url = config.get("url")
            env = config.get("env", {})
            cwd = config.get("cwd")

            # 构建 command 列表
            if command and args:
                full_command = [command] + args
            elif command:
                full_command = [command]
            else:
                full_command = []

            client = MCPClient(
                name=name,
                transport=transport,
                command=full_command if transport == "stdio" else None,
                url=url,
                env=env,
                cwd=cwd,
            )

            await asyncio.wait_for(client.connect(), timeout=30.0)
            self._clients[name] = client
            self._debug.log("agent", f"MCP 服务器 {name} 启动成功")
        except asyncio.TimeoutError:
            self._debug.log("agent", f"MCP 服务器 {name} 启动超时")
        except Exception as e:
            self._debug.log("agent", f"MCP 服务器 {name} 启动失败: {e}")

    async def register_tools(self, registry=tool_registry) -> int:
        """将所有 MCP 服务器的工具注册到 ToolRegistry。返回注册的工具数量。"""
        count = 0
        for name, client in self._clients.items():
            if not client.is_connected:
                continue
            try:
                tools = await client.list_tools()
                for tool_schema in tools:
                    try:
                        wrapper = MCPToolWrapper(client, tool_schema)
                        registry.register(wrapper)
                        count += 1
                    except ValueError:
                        # 工具已注册，跳过
                        pass
                self._debug.log("agent", f"MCP 服务器 {name} 注册了 {len(tools)} 个工具")
            except Exception as e:
                self._debug.log("agent", f"MCP 服务器 {name} 注册工具失败: {e}")
        return count

    async def stop_all(self) -> None:
        """停止所有 MCP 服务器"""
        tasks = [client.disconnect() for client in self._clients.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._clients.clear()

    def get_clients(self) -> list[MCPClient]:
        """获取所有已连接的客户端"""
        return list(self._clients.values())

    def get_client(self, name: str) -> Optional[MCPClient]:
        """获取指定名称的客户端"""
        return self._clients.get(name)

    @property
    def server_count(self) -> int:
        return len(self._clients)
