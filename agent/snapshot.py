"""
隐式快照系统 — 写操作前自动备份文件，支持回滚还原。

设计：
  .agent_snapshots/
  ├── manifest.json          # 快照索引
  └── files/
      └── {snapshot_id}/
          └── {relative_path}   # 文件副本

跨平台兼容：纯文件操作，macOS/WSL 均无问题。
"""

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from config import get_config


class SnapshotManager:
    """快照管理器 — 文件备份与还原"""

    def __init__(self, workspace_root: str = "."):
        cfg = get_config()
        self.enabled = cfg.time_travel.enabled
        self.max_snapshots = cfg.time_travel.max_snapshots
        self.workspace_root = Path(workspace_root).resolve()
        self.snapshot_dir = self.workspace_root / cfg.time_travel.snapshot_dir
        self.files_dir = self.snapshot_dir / "files"
        self.manifest_path = self.snapshot_dir / "manifest.json"
        self._manifest: dict = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """延迟加载 manifest"""
        if self._loaded:
            return
        self._loaded = True
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self._manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._manifest = {}

    def _save_manifest(self) -> None:
        """持久化 manifest"""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2, ensure_ascii=False)

    def take_snapshot(self, step_id: int, file_paths: list[str]) -> Optional[str]:
        """
        对指定文件列表创建快照。

        Args:
            step_id: 关联的步骤 ID
            file_paths: 需要备份的文件路径列表（相对于 workspace_root）

        Returns:
            snapshot_id 或 None（功能禁用时）
        """
        if not self.enabled:
            return None

        self._ensure_loaded()

        snapshot_id = f"step_{step_id}_{int(time.time() * 1000)}"
        snapshot_files_dir = self.files_dir / snapshot_id

        backed_up = {}
        for rel_path in file_paths:
            src = self.workspace_root / rel_path
            if not src.is_file():
                continue
            dst = snapshot_files_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                backed_up[rel_path] = str(dst)
            except OSError:
                continue

        if not backed_up:
            return None

        self._manifest[snapshot_id] = {
            "step_id": step_id,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": backed_up,
        }
        self._save_manifest()
        self._prune_old_snapshots()
        return snapshot_id

    def take_full_snapshot(self, step_id: int) -> Optional[str]:
        """
        对整个工作区做文件清单快照（记录哈希而非完整副本）。
        用于 execute_command 等无法预知影响范围的场景。

        Returns:
            snapshot_id 或 None
        """
        if not self.enabled:
            return None

        self._ensure_loaded()

        snapshot_id = f"step_{step_id}_{int(time.time() * 1000)}"
        file_hashes = {}

        for root, dirs, files in os.walk(str(self.workspace_root)):
            # 跳过快照目录自身和 .git
            dirs[:] = [d for d in dirs if d not in (".git", ".agent_snapshots", "__pycache__", "node_modules", ".venv")]
            for fname in files:
                fpath = Path(root) / fname
                try:
                    rel = str(fpath.relative_to(self.workspace_root))
                    file_hashes[rel] = self._file_hash(fpath)
                except (OSError, ValueError):
                    continue

        self._manifest[snapshot_id] = {
            "step_id": step_id,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "full_hash",
            "files": file_hashes,
        }
        self._save_manifest()
        self._prune_old_snapshots()
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> list[str]:
        """
        将快照中的文件硬覆盖回原位。

        Returns:
            已还原的文件路径列表
        """
        self._ensure_loaded()

        entry = self._manifest.get(snapshot_id)
        if entry is None:
            return []

        restored = []
        snapshot_type = entry.get("type", "file_copy")

        if snapshot_type == "full_hash":
            # 基于哈希对比还原
            for rel_path, old_hash in entry["files"].items():
                fpath = self.workspace_root / rel_path
                try:
                    current_hash = self._file_hash(fpath) if fpath.exists() else ""
                except OSError:
                    continue
                if current_hash != old_hash:
                    # 无法精确还原（没有完整副本），标记为需要关注
                    restored.append(f"{rel_path} (哈希不匹配，无法精确还原)")
            return restored

        # 文件副本模式：直接覆盖
        snapshot_files_dir = self.files_dir / snapshot_id
        if not snapshot_files_dir.exists():
            return []

        for rel_path, backup_path in entry.get("files", {}).items():
            src = Path(backup_path)
            dst = self.workspace_root / rel_path
            if not src.exists():
                restored.append(f"{rel_path} (快照文件缺失)")
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                restored.append(rel_path)
            except OSError:
                restored.append(f"{rel_path} (还原失败)")

        return restored

    def delete_snapshots_after(self, step_id: int) -> None:
        """删除指定步骤之后的所有快照"""
        self._ensure_loaded()

        to_delete = []
        for sid, entry in self._manifest.items():
            if entry.get("step_id", 0) > step_id:
                to_delete.append(sid)

        for sid in to_delete:
            self._delete_snapshot(sid)

    def verify_snapshot(self, snapshot_id: str) -> bool:
        """校验快照完整性"""
        self._ensure_loaded()

        entry = self._manifest.get(snapshot_id)
        if entry is None:
            return False

        snapshot_type = entry.get("type", "file_copy")
        if snapshot_type == "full_hash":
            return True  # 哈希快照始终有效

        snapshot_files_dir = self.files_dir / snapshot_id
        if not snapshot_files_dir.exists():
            return False

        for backup_path in entry.get("files", {}).values():
            if not Path(backup_path).exists():
                return False
        return True

    def get_snapshots_for_step(self, step_id: int) -> list[str]:
        """获取指定步骤关联的所有快照 ID"""
        self._ensure_loaded()
        return [
            sid for sid, entry in self._manifest.items()
            if entry.get("step_id") == step_id
        ]

    def _delete_snapshot(self, snapshot_id: str) -> None:
        """删除单个快照"""
        snapshot_files_dir = self.files_dir / snapshot_id
        if snapshot_files_dir.exists():
            shutil.rmtree(snapshot_files_dir, ignore_errors=True)
        self._manifest.pop(snapshot_id, None)
        self._save_manifest()

    def _prune_old_snapshots(self) -> None:
        """清理超出数量限制的旧快照"""
        if len(self._manifest) <= self.max_snapshots:
            return

        # 按 step_id 排序，删除最旧的
        sorted_ids = sorted(
            self._manifest.keys(),
            key=lambda sid: self._manifest[sid].get("step_id", 0),
        )
        to_delete = sorted_ids[:len(sorted_ids) - self.max_snapshots]
        for sid in to_delete:
            self._delete_snapshot(sid)

    @staticmethod
    def _file_hash(filepath: Path) -> str:
        """计算文件 SHA256 哈希"""
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
        except OSError:
            return ""
        return hasher.hexdigest()
