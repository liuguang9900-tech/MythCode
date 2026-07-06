"""
对话持久化管理器 — 将对话状态保存到 .mythcoder/conversation.json。
支持退出时自动保存、启动时自动恢复。
"""

import json
import time
from pathlib import Path
from typing import Optional

from config import get_config


class ConversationPersistence:
    """对话持久化管理器"""

    def __init__(self, workspace_root: str):
        cfg = get_config()
        storage_dir = cfg.persistence.storage_dir
        self.storage_path = Path(workspace_root) / storage_dir
        self.file_path = self.storage_path / "conversation.json"

    def save(self, memory, session_map) -> None:
        """
        序列化并保存对话状态。
        空对话不保存。
        """
        if not memory.messages:
            return

        self.storage_path.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": str(self.storage_path.parent.resolve()),
            "memory": {
                "messages": memory.messages,
                "summary": memory.summary,
            },
            "session_map": {
                "current_step_id": session_map.current_step_id,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "user_input": s.user_input,
                        "summary": s.summary,
                        "snapshot_ids": s.snapshot_ids,
                        "messages_snapshot": s.messages_snapshot,
                        "tool_calls": s.tool_calls,
                        "files_modified": s.files_modified,
                        "timestamp": s.timestamp,
                    }
                    for s in session_map.get_all_steps()
                ],
            },
        }

        # 原子写入：先写临时文件，再 rename
        tmp_path = self.file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self.file_path)

    def load(self) -> Optional[dict]:
        """
        从磁盘加载对话状态。
        返回 None 表示无存档或存档损坏。
        """
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        if data.get("version") != 1:
            return None

        return data

    def exists(self) -> bool:
        return self.file_path.exists()

    def delete(self) -> None:
        """删除存档文件"""
        if self.file_path.exists():
            self.file_path.unlink()
