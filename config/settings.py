"""
多作用域设置管理器 — 支持 User、Project、Local 三个作用域。

优先级（从低到高）：
  1. User:   ~/.mythcoder/settings.json
  2. Project: .mythcoder/settings.json
  3. Local:   .mythcoder/settings.local.json

合并策略：
  - 数组合并（拼接去重）
  - 对象深度合并
  - 标量覆盖
"""

import json
import os
from pathlib import Path
from typing import Optional, Any


class SettingsManager:
    """多作用域设置管理器"""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self._cache: Optional[dict] = None
        self._cache_mtimes: dict[str, float] = {}

    def get_user_path(self) -> Path:
        """用户级设置路径"""
        return Path.home() / ".mythcoder" / "settings.json"

    def get_project_path(self) -> Path:
        """项目级设置路径"""
        return self.workspace_root / ".mythcoder" / "settings.json"

    def get_local_path(self) -> Path:
        """本地设置路径（不提交到 git）"""
        return self.workspace_root / ".mythcoder" / "settings.local.json"

    def load(self, force_reload: bool = False) -> dict:
        """
        加载所有作用域的设置并合并。

        Returns:
            合并后的设置字典
        """
        if not force_reload and self._cache is not None:
            if not self._has_changed():
                return self._cache

        result = {}

        # 1. User 作用域（最低优先级）
        user_settings = self._read_json(self.get_user_path())
        if user_settings:
            result = self._deep_merge(result, user_settings)

        # 2. Project 作用域
        project_settings = self._read_json(self.get_project_path())
        if project_settings:
            result = self._deep_merge(result, project_settings)

        # 3. Local 作用域（最高优先级）
        local_settings = self._read_json(self.get_local_path())
        if local_settings:
            result = self._deep_merge(result, local_settings)

        self._cache = result
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取指定设置项（支持点号分隔的嵌套 key）。

        Args:
            key: 点号分隔的设置路径，如 "model.temperature"
            default: 默认值

        Returns:
            设置值
        """
        settings = self.load()
        keys = key.split(".")
        current = settings
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def save_user(self, settings: dict) -> None:
        """保存用户级设置"""
        self._write_json(self.get_user_path(), settings)
        self._cache = None

    def save_project(self, settings: dict) -> None:
        """保存项目级设置"""
        self._write_json(self.get_project_path(), settings)
        self._cache = None

    def save_local(self, settings: dict) -> None:
        """保存本地设置"""
        self._write_json(self.get_local_path(), settings)
        self._cache = None

    def update_user(self, key: str, value: Any) -> None:
        """更新用户级设置的单个键"""
        current = self._read_json(self.get_user_path()) or {}
        self._set_nested(current, key.split("."), value)
        self.save_user(current)

    def update_project(self, key: str, value: Any) -> None:
        """更新项目级设置的单个键"""
        current = self._read_json(self.get_project_path()) or {}
        self._set_nested(current, key.split("."), value)
        self.save_project(current)

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache = None
        self._cache_mtimes = {}

    # ============================================================
    # 内部方法
    # ============================================================

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        """读取 JSON 文件"""
        try:
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        """写入 JSON 文件（原子写入）"""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)

    def _has_changed(self) -> bool:
        """检查已缓存的设置文件是否有修改"""
        paths = [self.get_user_path(), self.get_project_path(), self.get_local_path()]
        for path in paths:
            path_str = str(path)
            try:
                if path.exists():
                    mtime = path.stat().st_mtime
                    if path_str not in self._cache_mtimes:
                        return True
                    if mtime > self._cache_mtimes[path_str]:
                        return True
                    self._cache_mtimes[path_str] = mtime
                elif path_str in self._cache_mtimes:
                    return True
            except OSError:
                return True
        return False

    @classmethod
    def _deep_merge(cls, base: dict, override: dict) -> dict:
        """
        深度合并两个字典。
        - 数组合并（拼接去重）
        - 对象深度合并
        - 标量覆盖
        """
        result = dict(base)
        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = cls._deep_merge(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    # 数组合并去重
                    merged = list(result[key])
                    for item in value:
                        if item not in merged:
                            merged.append(item)
                    result[key] = merged
                else:
                    result[key] = value
            else:
                result[key] = value
        return result

    @staticmethod
    def _set_nested(data: dict, keys: list[str], value: Any) -> None:
        """按点号路径设置嵌套字典值"""
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value
