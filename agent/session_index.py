"""
会话索引管理器 — 管理所有会话的元数据索引。
存储位置：~/.mythcoder/sessions.json
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional


class SessionIndex:
    """会话索引管理器"""

    def __init__(self):
        self._index_dir = Path.home() / ".mythcoder"
        self._index_file = self._index_dir / "sessions.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        """加载索引文件"""
        if not self._index_file.exists():
            return {"sessions": []}
        try:
            with open(self._index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"sessions": []}

    def _save(self, data: dict) -> None:
        """保存索引文件（原子写入）"""
        self._ensure_dir()
        tmp_path = self._index_file.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self._index_file)

    def register_session(
        self,
        session_id: str,
        name: str,
        workspace: str,
        step_count: int = 0,
    ) -> None:
        """注册或更新会话"""
        data = self._load()
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        # 查找已有记录
        for session in data["sessions"]:
            if session["id"] == session_id:
                session["name"] = name
                session["workspace"] = workspace
                session["saved_at"] = now
                session["step_count"] = step_count
                self._save(data)
                return

        # 新记录
        data["sessions"].append({
            "id": session_id,
            "name": name,
            "workspace": workspace,
            "saved_at": now,
            "step_count": step_count,
        })

        # 限制最多保留 100 条
        if len(data["sessions"]) > 100:
            data["sessions"] = data["sessions"][-100:]

        self._save(data)

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取指定会话"""
        data = self._load()
        for session in data["sessions"]:
            if session["id"] == session_id:
                return session
        return None

    def get_latest(self, workspace: Optional[str] = None) -> Optional[dict]:
        """获取最新会话（可按 workspace 过滤）"""
        data = self._load()
        sessions = data["sessions"]
        if workspace:
            sessions = [s for s in sessions if s.get("workspace") == workspace]
        if not sessions:
            return None
        return sessions[-1]  # 按时间排序，最后一条是最新的

    def list_sessions(self, workspace: Optional[str] = None) -> list[dict]:
        """列出所有会话"""
        data = self._load()
        sessions = data["sessions"]
        if workspace:
            sessions = [s for s in sessions if s.get("workspace") == workspace]
        return sessions

    def remove_session(self, session_id: str) -> bool:
        """删除会话记录"""
        data = self._load()
        original_len = len(data["sessions"])
        data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]
        if len(data["sessions"]) < original_len:
            self._save(data)
            return True
        return False

    @staticmethod
    def generate_id() -> str:
        """生成新的会话 ID"""
        return uuid.uuid4().hex[:12]
