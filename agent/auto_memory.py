"""
自动记忆管理器 — LLM 可在对话中写入记忆，下次对话自动加载。

存储路径：~/.mythcoder/projects/<workspace_hash>/memory/
每个记忆一个 JSON 文件，包含 title、content、timestamp、tags。
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional


class AutoMemoryManager:
    """自动记忆管理器"""

    def __init__(self, workspace_root: str):
        workspace_hash = hashlib.sha256(
            str(Path(workspace_root).resolve()).encode()
        ).hexdigest()[:16]
        self.storage_dir = Path.home() / ".mythcoder" / "projects" / workspace_hash / "memory"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_all(self) -> list[dict]:
        """获取所有记忆，按时间倒序"""
        memories = []
        if not self.storage_dir.exists():
            return memories

        for f in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["_id"] = f.stem
                memories.append(data)
            except (json.JSONDecodeError, OSError):
                continue

        # 按创建时间倒序排列
        memories.sort(key=lambda m: m.get("_sort_key", 0), reverse=True)
        return memories

    def add(self, title: str, content: str, tags: Optional[list[str]] = None) -> str:
        """添加一条记忆，返回记忆 ID"""
        mem_id = hashlib.sha256(
            f"{title}:{time.time()}".encode()
        ).hexdigest()[:12]

        data = {
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "_sort_key": time.time(),
        }

        filepath = self.storage_dir / f"{mem_id}.json"
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return mem_id

    def delete(self, mem_id: str) -> bool:
        """删除指定记忆"""
        filepath = self.storage_dir / f"{mem_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def search(self, query: str) -> list[dict]:
        """搜索记忆（简单关键词匹配）"""
        results = []
        query_lower = query.lower()
        for mem in self.get_all():
            title = mem.get("title", "").lower()
            content = mem.get("content", "").lower()
            tags = " ".join(mem.get("tags", [])).lower()
            if query_lower in title or query_lower in content or query_lower in tags:
                results.append(mem)
        return results

    def get_context_for_prompt(self, max_memories: int = 5) -> str:
        """
        获取用于注入 system prompt 的记忆上下文。
        返回最近 N 条记忆的格式化文本。
        """
        memories = self.get_all()[:max_memories]
        if not memories:
            return ""

        lines = ["## 自动记忆 (Auto Memory)", ""]
        for mem in memories:
            title = mem.get("title", "无标题")
            content = mem.get("content", "")
            lines.append(f"- **{title}**: {content[:300]}")
        return "\n".join(lines)

    def clear(self) -> None:
        """清除所有记忆"""
        for f in self.storage_dir.glob("*.json"):
            f.unlink()
