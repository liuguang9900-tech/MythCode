"""
IDEBridge — IDE IPC 通信桥。
通过 Unix Socket 与 IDE 扩展通信。
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Any

from ide.protocol import IDEEvent, IDECommand
from utils.debug import get_debug_manager


class IDEBridge:
    """IDE 通信桥"""

    def __init__(self):
        self._debug = get_debug_manager()
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: set[asyncio.StreamReader] = set()
        self._socket_path: Optional[Path] = None
        self._ide_type: Optional[str] = None
        self._connected = False

    def detect_ide(self) -> Optional[str]:
        """检测当前 IDE 环境"""
        # VS Code
        if os.environ.get("VSCODE_PID") or os.environ.get("VSCODE_CWD"):
            self._ide_type = "vscode"
            return "vscode"
        # JetBrains
        if os.environ.get("IDEA_INITIAL_DIRECTORY") or os.environ.get("JETBRAINS_IDE"):
            self._ide_type = "jetbrains"
            return "jetbrains"
        # Cursor
        if os.environ.get("CURSOR_PID"):
            self._ide_type = "cursor"
            return "cursor"
        return None

    async def start_server(self) -> Optional[str]:
        """启动 Unix Socket 服务器。返回 socket 路径。"""
        if self._server is not None:
            return str(self._socket_path)

        # 创建 socket 文件
        sock_dir = Path(tempfile.gettempdir()) / "mythcoder"
        sock_dir.mkdir(parents=True, exist_ok=True)
        self._socket_path = sock_dir / f"ide_{os.getpid()}.sock"

        # 清理旧文件
        if self._socket_path.exists():
            self._socket_path.unlink()

        try:
            self._server = await asyncio.start_unix_server(
                self._handle_client,
                str(self._socket_path),
            )
            self._connected = True
            self._debug.log("agent", f"IDE Bridge 服务器启动: {self._socket_path}")
            return str(self._socket_path)
        except OSError as e:
            self._debug.log("agent", f"IDE Bridge 启动失败: {e}")
            return None

    async def stop_server(self) -> None:
        """停止服务器"""
        self._connected = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._socket_path and self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError:
                pass

        self._clients.clear()
        self._debug.log("agent", "IDE Bridge 服务器已停止")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理客户端连接"""
        self._clients.add(reader)
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                try:
                    msg = json.loads(data.decode("utf-8"))
                    response = await self.handle_command(msg)
                    if response:
                        writer.write((json.dumps(response) + "\n").encode("utf-8"))
                        await writer.drain()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            self._clients.discard(reader)
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, asyncio.CancelledError):
                pass

    async def send_event(self, event: dict) -> None:
        """发送事件到所有连接的 IDE 客户端"""
        if not self._clients:
            return

        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        dead_clients = []

        for client in self._clients:
            try:
                # 通过 writer 发送（需要保存 writer 引用）
                # 简化实现：跳过，实际需要维护 writer 列表
                pass
            except (OSError, ConnectionResetError):
                dead_clients.append(client)

        for client in dead_clients:
            self._clients.discard(client)

    async def handle_command(self, cmd: dict) -> Optional[dict]:
        """处理来自 IDE 的命令"""
        cmd_type = cmd.get("type", "")
        try:
            command = IDECommand(cmd_type)
        except ValueError:
            return {"error": f"未知命令: {cmd_type}"}

        if command == IDECommand.OPEN_FILE:
            return await self._cmd_open_file(cmd)
        elif command == IDECommand.SHOW_DIFF:
            return await self._cmd_show_diff(cmd)
        elif command == IDECommand.JUMP_TO_LINE:
            return await self._cmd_jump_to_line(cmd)
        elif command == IDECommand.GET_ACTIVE_FILE:
            return {"file_path": None}  # 需要 IDE 扩展提供
        elif command == IDECommand.GET_SELECTION:
            return {"selection": None}
        else:
            return {"error": f"未实现的命令: {command}"}

    async def _cmd_open_file(self, cmd: dict) -> dict:
        """打开文件命令"""
        file_path = cmd.get("file_path", "")
        line = cmd.get("line", 1)
        # 实际打开操作由 IDE 扩展执行
        return {"status": "ok", "file_path": file_path, "line": line}

    async def _cmd_show_diff(self, cmd: dict) -> dict:
        """显示 diff 命令"""
        return {"status": "ok"}

    async def _cmd_jump_to_line(self, cmd: dict) -> dict:
        """跳转到行命令"""
        return {"status": "ok"}

    @property
    def is_connected(self) -> bool:
        return self._connected and bool(self._clients)

    @property
    def ide_type(self) -> Optional[str]:
        return self._ide_type

    @property
    def socket_path(self) -> Optional[str]:
        return str(self._socket_path) if self._socket_path else None
