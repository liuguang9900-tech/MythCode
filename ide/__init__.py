"""
IDE 集成包 — IPC 通信桥。
"""

from ide.bridge import IDEBridge
from ide.protocol import IDEEvent, IDECommand

__all__ = ["IDEBridge", "IDEEvent", "IDECommand"]
