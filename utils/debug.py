"""
调试管理器 — 分类调试日志开关。
支持 --debug=llm,tools,agent 分类过滤。
"""

import logging
from typing import Optional

logger = logging.getLogger("mythcoder.debug")


class DebugManager:
    """管理调试类别开关"""

    def __init__(self):
        self._categories: set[str] = set()
        self._enabled = False

    def enable(self, categories: str) -> None:
        """
        启用调试模式。

        Args:
            categories: "all" 或逗号分隔的分类名，如 "llm,tools,agent"
        """
        self._enabled = True
        cats = [c.strip() for c in categories.split(",")]
        if "all" in cats:
            self._categories = {"llm", "tools", "agent", "sandbox", "persistence"}
        else:
            self._categories = set(cats)

    def is_enabled(self, category: str) -> bool:
        """检查指定分类的调试是否启用"""
        return self._enabled and category in self._categories

    def log(self, category: str, message: str, *args, **kwargs) -> None:
        """输出调试日志"""
        if self.is_enabled(category):
            logger.debug(f"[{category}] {message}", *args, **kwargs)

    @property
    def enabled_categories(self) -> set[str]:
        return self._categories.copy()


# 全局单例
_debug_manager: Optional[DebugManager] = None


def get_debug_manager() -> DebugManager:
    global _debug_manager
    if _debug_manager is None:
        _debug_manager = DebugManager()
    return _debug_manager
