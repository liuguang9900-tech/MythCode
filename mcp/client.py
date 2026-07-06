"""
MCP Client — 单个 MCP 服务器的客户端。
支持 stdio 和 SSE 两种传输方式。
"""

import asyncio
import json
import os
from typing import Optional, Any
from pathlib import Path

from utils.debug import get_debug_manager


class MCPClient:
    """MCP 单服务器客户端"""

    def __init__(
        self,
        name: str,
        transport: str = "stdio",
        command: Optional[list[str]] = None,
        url: Optional[str] = None,
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
    ):
        self.name = name
        self.transport = transport
        self.command = command or []
        self.url = url
        self.env = env or {}
        self.cwd = cwd
        self._debug = get_debug_manager()

        # stdio 传输状态
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()

        # SSE 传输状态
        self._http_client = None
        self._sse_response = None

        self._connected = False
        self._tools_cache: list[dict] = []

    async def connect(self) -> None:
        """启动子进程或建立 SSE 连接"""
        if self._connected:
            return

        if self.transport == "stdio":
            await self._connect_stdio()
        elif self.transport == "sse":
            await self._connect_sse()
        else:
            raise ValueError(f"不支持的传输方式: {self.transport}")

        # 发送 initialize 请求
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "MythCoder", "version": "0.1.0"},
        })

        # 发送 initialized 通知
        await self._send_notification("notifications/initialized", {})

        self._connected = True
        self._debug.log("agent", f"MCP 服务器 {self.name} 已连接")

    async def _connect_stdio(self) -> None:
        """启动 stdio 子进程"""
        if not self.command:
            raise ValueError("stdio 传输需要 command 参数")

        env = {**os.environ, **self.env}
        cwd = self.cwd or str(Path.cwd())

        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

        # 启动 stdout 读取任务
        self._reader_task = asyncio.create_task(self._read_stdout())

        # 启动 stderr 日志任务
        asyncio.create_task(self._read_stderr())

    async def _connect_sse(self) -> None:
        """建立 SSE 连接"""
        try:
            import httpx
        except ImportError:
            raise RuntimeError("SSE 传输需要 httpx，请安装: pip install httpx")

        self._http_client = httpx.AsyncClient(timeout=60.0)

    async def _read_stdout(self) -> None:
        """读取子进程 stdout，按行解析 JSON-RPC 响应"""
        while self._process and self._process.returncode is None:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                    await self._handle_message(msg)
                except json.JSONDecodeError:
                    self._debug.log("agent", f"MCP {self.name} stdout 非 JSON: {line_str[:100]}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._debug.log("agent", f"MCP {self.name} 读取 stdout 异常: {e}")

    async def _read_stderr(self) -> None:
        """读取子进程 stderr，输出到调试日志"""
        while self._process and self._process.returncode is None:
            try:
                line = await self._process.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if line_str:
                    self._debug.log("agent", f"MCP {self.name} stderr: {line_str[:200]}")
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def _handle_message(self, msg: dict) -> None:
        """处理收到的 JSON-RPC 消息"""
        if "id" in msg:
            # 响应消息
            msg_id = msg["id"]
            future = self._pending.get(msg_id)
            if future and not future.done():
                if "error" in msg:
                    future.set_exception(MCPError(msg["error"]))
                else:
                    future.set_result(msg.get("result"))
                self._pending.pop(msg_id, None)
        # 通知消息暂不处理

    async def _send_request(self, method: str, params: dict) -> Any:
        """发送 JSON-RPC 请求并等待响应"""
        if self.transport == "stdio":
            return await self._stdio_request(method, params)
        else:
            return await self._sse_request(method, params)

    async def _send_notification(self, method: str, params: dict) -> None:
        """发送 JSON-RPC 通知（无响应）"""
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        if self.transport == "stdio":
            await self._stdio_send(msg)
        # SSE 通知暂不处理

    async def _stdio_request(self, method: str, params: dict) -> Any:
        """stdio 传输：发送请求并等待响应"""
        if not self._process or self._process.returncode is not None:
            raise MCPError({"code": -32000, "message": "MCP 进程未运行"})

        self._request_id += 1
        msg_id = self._request_id
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        await self._stdio_send(msg)

        try:
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise MCPError({"code": -32000, "message": f"MCP 请求超时: {method}"})

    async def _stdio_send(self, msg: dict) -> None:
        """向子进程 stdin 写入 JSON-RPC 消息"""
        if not self._process or not self._process.stdin:
            return
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._write_lock:
            self._process.stdin.write(data)
            await self._process.stdin.drain()

    async def _sse_request(self, method: str, params: dict) -> Any:
        """SSE 传输：发送 HTTP POST 请求"""
        if not self._http_client or not self.url:
            raise MCPError({"code": -32000, "message": "SSE 未连接"})

        self._request_id += 1
        msg_id = self._request_id
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}

        try:
            resp = await self._http_client.post(self.url, json=msg)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise MCPError(data["error"])
            return data.get("result")
        except Exception as e:
            raise MCPError({"code": -32000, "message": f"SSE 请求失败: {e}"})

    async def list_tools(self) -> list[dict]:
        """调用 tools/list 获取工具列表"""
        result = await self._send_request("tools/list", {})
        tools = result.get("tools", []) if result else []
        self._tools_cache = tools
        return tools

    async def call_tool(self, name: str, args: dict) -> dict:
        """调用 tools/call 执行工具"""
        result = await self._send_request("tools/call", {"name": name, "arguments": args})
        return result or {}

    async def list_resources(self) -> list[dict]:
        """调用 resources/list 获取资源列表"""
        result = await self._send_request("resources/list", {})
        return result.get("resources", []) if result else []

    async def read_resource(self, uri: str) -> str:
        """调用 resources/read 读取资源"""
        result = await self._send_request("resources/read", {"uri": uri})
        if result and result.get("contents"):
            contents = result["contents"]
            if contents and isinstance(contents, list):
                return contents[0].get("text", "")
        return ""

    async def disconnect(self) -> None:
        """关闭连接"""
        self._connected = False

        # 取消所有等待中的请求
        for future in self._pending.values():
            if not future.done():
                future.set_exception(MCPError({"code": -32000, "message": "连接关闭"}))
        self._pending.clear()

        # 取消读取任务
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        # 关闭子进程
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass

        # 关闭 HTTP 客户端
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception:
                pass

        self._debug.log("agent", f"MCP 服务器 {self.name} 已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected


class MCPError(Exception):
    """MCP 协议错误"""

    def __init__(self, error: dict):
        self.code = error.get("code", -1)
        self.message = error.get("message", "未知错误")
        super().__init__(f"MCP Error [{self.code}]: {self.message}")
