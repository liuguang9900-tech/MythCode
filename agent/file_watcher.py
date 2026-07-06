"""
文件监听器 — 基于 watchdog。
监听文件变化，触发注册的处理器。
"""

import asyncio
import fnmatch
from pathlib import Path
from typing import Callable, Optional, Any
from utils.debug import get_debug_manager


class FileWatcher:
    """文件监听器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self._debug = get_debug_manager()
        self._observer: Optional[Any] = None
        self._handlers: list[dict] = []  # [{"pattern": str, "handler": Callable}]
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    def register_handler(self, pattern: str, handler: Callable[[str], None]) -> None:
        """注册文件变化处理器

        Args:
            pattern: 文件路径 glob 模式（如 "*.yaml", ".claude/rules/*.md"）
            handler: 处理函数，接收文件路径参数
        """
        self._handlers.append({"pattern": pattern, "handler": handler})

    def start(self) -> None:
        """启动文件监听"""
        if self._running:
            return

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
        except ImportError:
            self._debug.log("agent", "watchdog 未安装，文件监听功能不可用")
            return

        self._loop = asyncio.get_event_loop()

        class _Handler(FileSystemEventHandler):
            def __init__(self, watcher: FileWatcher):
                self.watcher = watcher

            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._dispatch(event.src_path)

            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._dispatch(event.src_path)

        self._observer = Observer()
        self._observer.schedule(_Handler(self), str(self.workspace_root), recursive=True)
        self._observer.start()
        self._running = True
        self._debug.log("agent", "文件监听已启动")

    def stop(self) -> None:
        """停止文件监听"""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._running = False
        self._debug.log("agent", "文件监听已停止")

    def _dispatch(self, file_path: str) -> None:
        """分发文件变化事件到匹配的处理器"""
        try:
            rel_path = str(Path(file_path).relative_to(self.workspace_root))
        except ValueError:
            return

        for handler_info in self._handlers:
            pattern = handler_info["pattern"]
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(file_path, pattern):
                handler = handler_info["handler"]
                try:
                    if asyncio.iscoroutinefunction(handler):
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(handler(file_path), self._loop)
                    else:
                        handler(file_path)
                except Exception as e:
                    self._debug.log("agent", f"文件监听处理器异常: {e}")

    @property
    def is_running(self) -> bool:
        return self._running
