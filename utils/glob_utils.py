"""
Glob 模式匹配工具 — 支持 ** 递归匹配的文件名模式。
从 agent/rules.py 提取为公共函数，供 glob 工具和规则系统复用。
"""

import re
from pathlib import Path
from typing import List


def glob_to_regex(pattern: str) -> re.Pattern:
    """
    将 glob 模式转换为正则表达式，支持 ** 递归匹配。

    支持的通配符：
    - ** : 匹配零个或多个目录层级（如 src/**/*.py）
    - *  : 匹配除路径分隔符外的任意字符
    - ?  : 匹配单个字符（除路径分隔符）

    Args:
        pattern: glob 模式字符串

    Returns:
        编译后的正则表达式 Pattern 对象
    """
    parts = []
    i = 0
    while i < len(pattern):
        if pattern[i:i+2] == "**":
            # ** 匹配零个或多个目录
            # 如果后面是 /，则 **/ 作为一个整体
            if i + 2 < len(pattern) and pattern[i+2] == "/":
                parts.append(r"(?:.+/)*")
                i += 3  # skip **/
            else:
                parts.append(r".*")
                i += 2
        elif pattern[i] == "*":
            parts.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append(r"[^/]")
            i += 1
        elif pattern[i] in ".^${}()[]|+\\":
            parts.append("\\" + pattern[i])
            i += 1
        else:
            parts.append(pattern[i])
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def match_glob(file_path: str, pattern: str) -> bool:
    """
    检查文件路径是否匹配 glob 模式（支持 **）。

    Args:
        file_path: 相对路径或绝对路径字符串
        pattern: glob 模式

    Returns:
        是否匹配
    """
    return bool(glob_to_regex(pattern).match(file_path))


def find_files(
    root: Path,
    pattern: str,
    ignore_manager=None,
    limit: int = 100,
) -> List[str]:
    """
    在指定根目录下查找匹配 glob 模式的文件。

    Args:
        root: 搜索根目录
        pattern: glob 模式（如 **/*.py、src/**/*.ts）
        ignore_manager: 可选的 IgnoreSpecManager，用于过滤忽略的文件
        limit: 最大返回结果数

    Returns:
        匹配文件的相对路径列表（按字典序排序）
    """
    regex = glob_to_regex(pattern)
    root = root.resolve()
    results: List[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        rel_path = path.relative_to(root)
        rel_str = str(rel_path)

        # 应用忽略规则
        if ignore_manager and ignore_manager.is_ignored(path, root):
            continue

        # 匹配 glob 模式
        if regex.match(rel_str):
            results.append(rel_str)
            if len(results) >= limit:
                break

    results.sort()
    return results
