"""
IDE IPC 协议定义 — JSON-RPC over Unix Socket。
"""

from enum import Enum


class IDEEvent(str, Enum):
    """IDE 事件类型"""
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    DIFF_READY = "diff_ready"
    FILE_MODIFIED = "file_modified"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    ERROR = "error"


class IDECommand(str, Enum):
    """IDE 命令类型"""
    OPEN_FILE = "open_file"
    SHOW_DIFF = "show_diff"
    JUMP_TO_LINE = "jump_to_line"
    APPLY_EDIT = "apply_edit"
    GET_ACTIVE_FILE = "get_active_file"
    GET_SELECTION = "get_selection"


# 事件数据结构
EVENT_SCHEMAS = {
    IDEEvent.TOOL_CALL_STARTED: {"tool_name": str, "args": dict},
    IDEEvent.TOOL_CALL_COMPLETED: {"tool_name": str, "success": bool, "output": str},
    IDEEvent.DIFF_READY: {"file_path": str, "diff": str},
    IDEEvent.FILE_MODIFIED: {"file_path": str, "action": str},
}

# 命令数据结构
COMMAND_SCHEMAS = {
    IDECommand.OPEN_FILE: {"file_path": str, "line": int},
    IDECommand.SHOW_DIFF: {"file_path": str, "diff": str},
    IDECommand.JUMP_TO_LINE: {"file_path": str, "line": int, "column": int},
    IDECommand.APPLY_EDIT: {"file_path": str, "old_text": str, "new_text": str},
}
