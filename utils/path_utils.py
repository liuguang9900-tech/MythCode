"""
跨平台路径处理工具 — 基于 Pathlib 的统一路径操作。
确保 macOS (M4) 和 Windows WSL2 下行为一致。
"""

import os
import platform
from pathlib import Path
from typing import Union


def normalize_path(path: Union[str, Path]) -> Path:
    """
    标准化路径：展开 ~、解析相对路径、统一分隔符。
    跨平台兼容。
    """
    if isinstance(path, str):
        path = os.path.expanduser(path)
    return Path(path).resolve()


def is_subpath(path: Union[str, Path], parent: Union[str, Path]) -> bool:
    """检查 path 是否在 parent 目录下"""
    try:
        normalize_path(path).relative_to(normalize_path(parent))
        return True
    except ValueError:
        return False


def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> str:
    """获取相对路径，跨平台安全"""
    try:
        rel = normalize_path(path).relative_to(normalize_path(base))
        return str(rel)
    except ValueError:
        return str(normalize_path(path))


def is_wsl() -> bool:
    """检测是否在 WSL 环境中运行"""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def get_platform_info() -> dict:
    """获取平台信息"""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "is_wsl": is_wsl(),
        "home": str(Path.home()),
    }
