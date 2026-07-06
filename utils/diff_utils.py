"""
Diff 工具 — 生成 unified diff 并格式化渲染。
用于 edit_file/write_file 工具的变更预览。
"""

import difflib
from pathlib import Path
from typing import List, Optional


def generate_unified_diff(
    original_content: str,
    new_content: str,
    file_path: str = "",
    context_lines: int = 3,
) -> str:
    """
    生成 unified diff 文本。

    Args:
        original_content: 原始文件内容（空字符串表示新建文件）
        new_content: 修改后的内容
        file_path: 文件路径（用于 diff 头部显示）
        context_lines: 上下文行数

    Returns:
        unified diff 文本；若无变化返回空字符串
    """
    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # 如果内容以换行结尾，splitlines(keepends=True) 会保留；否则需要处理
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}" if original_content else "/dev/null",
        tofile=f"b/{file_path}",
        n=context_lines,
    )

    diff_text = "".join(diff)
    return diff_text


def read_file_safe(file_path: Path) -> str:
    """安全读取文件内容，文件不存在或无法读取时返回空字符串"""
    try:
        if not file_path.exists() or not file_path.is_file():
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return ""


def count_diff_changes(diff_text: str) -> dict:
    """
    统计 diff 中的变更行数。

    Returns:
        {"added": int, "removed": int}
    """
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"added": added, "removed": removed}


def format_diff_for_display(diff_text: str) -> str:
    """
    将 diff 文本格式化为带颜色的 Rich 标记文本。

    用于 ui/console.py 的 print_diff_preview 函数。
    """
    if not diff_text:
        return "[dim](无变更)[/dim]"

    lines = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            lines.append(f"[bold]{line}[/bold]")
        elif line.startswith("@@"):
            lines.append(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            lines.append(f"[green]{line}[/green]")
        elif line.startswith("-"):
            lines.append(f"[red]{line}[/red]")
        else:
            lines.append(line)

    return "\n".join(lines)
