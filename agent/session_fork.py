"""
会话分叉器 — 从任意步骤创建新会话分支。
"""

import json
import shutil
from pathlib import Path
from typing import Optional


class SessionForker:
    """会话分叉器"""

    def __init__(self, workspace_root: str, session_index):
        self.workspace_root = Path(workspace_root).resolve()
        self.session_index = session_index
        self.conversations_dir = self.workspace_root / ".mythcoder" / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)

    def fork_from_step(self, agent, step_id: int, name: str) -> Optional[str]:
        """
        从指定步骤创建新会话分支。

        Args:
            agent: AgentLoop 实例
            step_id: 分叉点步骤 ID
            name: 新会话名称

        Returns:
            新会话 ID，失败返回 None
        """
        from agent.session_index import SessionIndex

        # 检查步骤是否存在
        target_record = agent.session_map.get_step(step_id)
        if target_record is None:
            return None

        # 生成新会话 ID
        new_session_id = SessionIndex.generate_id()

        # 保存当前会话状态
        agent.save_conversation()

        # 复制当前会话状态到新文件
        current_session_id = agent._session_id or "default"
        current_file = self._get_conversation_file(current_session_id)
        new_file = self._get_conversation_file(new_session_id)

        if current_file.exists():
            shutil.copy2(current_file, new_file)
        else:
            # 如果当前会话文件不存在，直接保存当前状态
            self._save_conversation_to_file(agent, new_session_id)

        # 加载新会话并执行 rewind 到指定步骤
        data = self._load_conversation_file(new_session_id)
        if data is None:
            return None

        # 恢复 agent 状态到新会话
        old_session_id = agent._session_id
        agent._session_id = new_session_id

        # 恢复 memory 和 session_map
        from agent.session_map import StepRecord
        mem_data = data.get("memory", {})
        agent.memory.messages = mem_data.get("messages", [])
        agent.memory.summary = mem_data.get("summary", None)

        sm_data = data.get("session_map", {})
        agent.session_map.clear()
        agent.session_map._current_step_id = sm_data.get("current_step_id", 0)
        for step_data in sm_data.get("steps", []):
            record = StepRecord(
                step_id=step_data["step_id"],
                user_input=step_data["user_input"],
                summary=step_data["summary"],
                snapshot_ids=step_data.get("snapshot_ids", []),
                messages_snapshot=step_data.get("messages_snapshot", []),
                tool_calls=step_data.get("tool_calls", []),
                files_modified=step_data.get("files_modified", []),
                timestamp=step_data.get("timestamp", ""),
            )
            agent.session_map._steps[record.step_id] = record

        # 执行回溯到指定步骤
        agent.rewind_to_step(step_id)

        # 保存新会话
        self._save_conversation_to_file(agent, new_session_id)

        # 注册到索引
        self.session_index.register_session(
            session_id=new_session_id,
            name=name,
            workspace=str(self.workspace_root),
            step_count=len(agent.session_map.get_all_steps()),
        )

        # 恢复原会话 ID（不切换当前会话）
        agent._session_id = old_session_id

        # 重新加载原会话
        if old_session_id:
            self._load_and_restore(agent, old_session_id)

        return new_session_id

    def switch_to(self, agent, session_id: str) -> Optional[dict]:
        """
        切换到指定会话。

        Args:
            agent: AgentLoop 实例
            session_id: 目标会话 ID

        Returns:
            恢复摘要信息，失败返回 None
        """
        # 保存当前会话
        agent.save_conversation()

        # 加载目标会话
        data = self._load_conversation_file(session_id)
        if data is None:
            return None

        agent._session_id = session_id

        # 恢复 memory
        from agent.session_map import StepRecord
        mem_data = data.get("memory", {})
        agent.memory.messages = mem_data.get("messages", [])
        agent.memory.summary = mem_data.get("summary", None)

        # 恢复 session_map
        sm_data = data.get("session_map", {})
        agent.session_map.clear()
        agent.session_map._current_step_id = sm_data.get("current_step_id", 0)
        for step_data in sm_data.get("steps", []):
            record = StepRecord(
                step_id=step_data["step_id"],
                user_input=step_data["user_input"],
                summary=step_data["summary"],
                snapshot_ids=step_data.get("snapshot_ids", []),
                messages_snapshot=step_data.get("messages_snapshot", []),
                tool_calls=step_data.get("tool_calls", []),
                files_modified=step_data.get("files_modified", []),
                timestamp=step_data.get("timestamp", ""),
            )
            agent.session_map._steps[record.step_id] = record

        steps = agent.session_map.get_all_steps()
        return {
            "step_count": len(steps),
            "message_count": len(agent.memory.messages),
            "saved_at": data.get("saved_at", "未知"),
            "session_id": session_id,
        }

    def _get_conversation_file(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.conversations_dir / f"{session_id}.json"

    def _save_conversation_to_file(self, agent, session_id: str) -> None:
        """保存会话到指定文件"""
        import time
        data = {
            "version": 1,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": str(self.workspace_root),
            "memory": {
                "messages": agent.memory.messages,
                "summary": agent.memory.summary,
            },
            "session_map": {
                "current_step_id": agent.session_map.current_step_id,
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
                    for s in agent.session_map.get_all_steps()
                ],
            },
        }
        file_path = self._get_conversation_file(session_id)
        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(file_path)

    def _load_conversation_file(self, session_id: str) -> Optional[dict]:
        """加载会话文件"""
        file_path = self._get_conversation_file(session_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _load_and_restore(self, agent, session_id: str) -> None:
        """加载并恢复会话"""
        data = self._load_conversation_file(session_id)
        if data is None:
            return

        from agent.session_map import StepRecord
        agent._session_id = session_id
        mem_data = data.get("memory", {})
        agent.memory.messages = mem_data.get("messages", [])
        agent.memory.summary = mem_data.get("summary", None)

        sm_data = data.get("session_map", {})
        agent.session_map.clear()
        agent.session_map._current_step_id = sm_data.get("current_step_id", 0)
        for step_data in sm_data.get("steps", []):
            record = StepRecord(
                step_id=step_data["step_id"],
                user_input=step_data["user_input"],
                summary=step_data["summary"],
                snapshot_ids=step_data.get("snapshot_ids", []),
                messages_snapshot=step_data.get("messages_snapshot", []),
                tool_calls=step_data.get("tool_calls", []),
                files_modified=step_data.get("files_modified", []),
                timestamp=step_data.get("timestamp", ""),
            )
            agent.session_map._steps[record.step_id] = record
