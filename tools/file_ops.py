"""
文件操作工具：Read_File / Write_File / Edit_File
"""

import os
from pathlib import Path
from typing import Optional

from tools.base import BaseTool, ToolResult
from tools.sandbox import get_sandbox
from config import get_config


class ReadFileTool(BaseTool):
    """读取文件内容，支持指定行号范围"""

    name = "read_file"
    description = "读取文件文本内容，返回带行号格式。大文件用 offset/limit 分段读取。仅支持 UTF-8 文本。"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "文件路径",
            "required": True,
        },
        "offset": {
            "type": "integer",
            "description": "起始行号（从1开始）",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "最大读取行数",
            "required": False,
        },
    }

    async def execute(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> ToolResult:
        sandbox = get_sandbox()
        cfg = get_config()

        try:
            resolved = sandbox.resolve_path(file_path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if not resolved.exists():
            return ToolResult(
                success=False, output="", error=f"文件不存在: {file_path}"
            )
        if not resolved.is_file():
            return ToolResult(
                success=False, output="", error=f"路径不是文件: {file_path}"
            )

        # 大小检查
        size_mb = resolved.stat().st_size / (1024 * 1024)
        if size_mb > cfg.tools.file_max_size_mb:
            return ToolResult(
                success=False,
                output="",
                error=f"文件过大 ({size_mb:.1f}MB)，超过限制 ({cfg.tools.file_max_size_mb}MB)。请使用 offset/limit 分段读取。",
            )

        try:
            with open(resolved, "r", encoding=cfg.tools.file_encoding) as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"无法以 {cfg.tools.file_encoding} 编码读取文件，可能是二进制文件",
            )

        total_lines = len(lines)

        # 处理行号范围（未指定 limit 时默认最多读 500 行，避免大文件撑爆上下文）
        start = max(0, (offset or 1) - 1)
        if limit:
            end = min(total_lines, start + limit)
        else:
            end = min(total_lines, start + 500)

        selected = lines[start:end]

        # 添加行号前缀（紧凑格式，节省 token）
        output_lines = []
        for i, line in enumerate(selected, start=start + 1):
            output_lines.append(f"{i}|{line.rstrip()}")

        output = "\n".join(output_lines)
        if not output:
            output = "(文件为空)"

        # 如果只读取了部分行，提示 LLM 还有更多内容
        if end < total_lines:
            output += f"\n\n(共 {total_lines} 行，已显示 {start + 1}-{end}，如需更多用 offset={end + 1} 继续读取)"

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "path": str(resolved),
                "total_lines": total_lines,
                "shown_lines": len(selected),
                "range": f"{start + 1}-{end}",
            },
        )


class WriteFileTool(BaseTool):
    """写入文件（创建或覆盖）"""

    name = "write_file"
    description = "创建新文件或完全覆盖已有文件。自动创建父目录。修改现有文件优先用 edit_file。"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "文件路径",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "文件内容",
            "required": True,
        },
    }

    async def execute(self, file_path: str, content: str) -> ToolResult:
        sandbox = get_sandbox()

        try:
            resolved = sandbox.resolve_path(file_path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if sandbox.is_protected_path(str(resolved)):
            return ToolResult(
                success=False,
                output="",
                error=f"安全限制：禁止修改受保护路径 '{file_path}'",
            )

        # 读取原始内容用于生成 diff（文件不存在则为空）
        from utils.diff_utils import read_file_safe, generate_unified_diff
        original_content = read_file_safe(resolved)

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            return ToolResult(success=False, output="", error=f"写入失败: {e}")

        # 生成 diff
        diff_text = generate_unified_diff(
            original_content, content, file_path=file_path
        )

        line_count = content.count("\n") + (1 if content else 0)
        return ToolResult(
            success=True,
            output=f"文件已写入: {resolved}\n行数: {line_count}, 大小: {len(content)} 字符",
            metadata={
                "path": str(resolved),
                "lines": line_count,
                "size": len(content),
                "diff": diff_text,
                "is_new_file": not original_content,
            },
        )


class EditFileTool(BaseTool):
    """精确字符串替换编辑"""

    name = "edit_file"
    description = "精确字符串替换编辑文件。old_string 必须唯一匹配，缩进须精确。replace_all=true 替换所有匹配。"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "文件路径",
            "required": True,
        },
        "old_string": {
            "type": "string",
            "description": "要替换的原始字符串（须精确匹配）",
            "required": True,
        },
        "new_string": {
            "type": "string",
            "description": "替换后的新字符串",
            "required": True,
        },
        "replace_all": {
            "type": "boolean",
            "description": "是否替换所有匹配项（默认false）",
            "required": False,
        },
    }

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ToolResult:
        sandbox = get_sandbox()

        try:
            resolved = sandbox.resolve_path(file_path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if sandbox.is_protected_path(str(resolved)):
            return ToolResult(
                success=False,
                output="",
                error=f"安全限制：禁止修改受保护路径 '{file_path}'",
            )

        if not resolved.exists():
            return ToolResult(
                success=False, output="", error=f"文件不存在: {file_path}"
            )

        try:
            with open(resolved, "r", encoding="utf-8") as f:
                original = f.read()
        except UnicodeDecodeError:
            return ToolResult(
                success=False, output="", error="无法读取文件，可能是二进制文件"
            )

        if old_string not in original:
            return ToolResult(
                success=False,
                output="",
                error="old_string 在文件中未找到匹配项，请检查内容是否精确匹配（包括缩进和换行）",
            )

        count = original.count(old_string)
        if count > 1 and not replace_all:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"old_string 在文件中匹配到 {count} 处。"
                    f"请提供更多上下文使匹配唯一，或设置 replace_all=true 替换所有匹配项。"
                ),
            )

        if replace_all:
            modified = original.replace(old_string, new_string)
            replaced_count = count
        else:
            modified = original.replace(old_string, new_string, 1)
            replaced_count = 1

        try:
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(modified)
        except OSError as e:
            return ToolResult(success=False, output="", error=f"写入失败: {e}")

        # 生成 diff
        from utils.diff_utils import generate_unified_diff
        diff_text = generate_unified_diff(
            original, modified, file_path=file_path
        )

        return ToolResult(
            success=True,
            output=f"文件已编辑: {resolved}\n替换了 {replaced_count} 处匹配",
            metadata={
                "path": str(resolved),
                "replacements": replaced_count,
                "replace_all": replace_all,
                "diff": diff_text,
            },
        )


class ReadImageTool(BaseTool):
    """读取图片文件，返回 base64 编码供多模态 LLM 使用"""

    name = "read_image"
    description = "读取图片文件(PNG/JPEG/GIF/WebP/BMP)返回base64，供多模态LLM查看。最大20MB。"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "图片文件路径",
            "required": True,
        },
        "max_size": {
            "type": "integer",
            "description": "最大边长(像素)，超过则等比缩放。0不缩放",
            "required": False,
        },
    }

    _SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    _MIME_MAP = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    _MAX_SIZE_MB = 20

    async def execute(
        self,
        file_path: str,
        max_size: int = 0,
    ) -> ToolResult:
        sandbox = get_sandbox()

        try:
            resolved = sandbox.resolve_path(file_path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
        if not resolved.is_file():
            return ToolResult(success=False, output="", error=f"路径不是文件: {file_path}")

        ext = resolved.suffix.lower()
        if ext not in self._SUPPORTED_EXTS:
            return ToolResult(
                success=False,
                output="",
                error=f"不支持的图片格式: {ext}。支持的格式: {', '.join(self._SUPPORTED_EXTS)}",
            )

        # 大小检查
        size_mb = resolved.stat().st_size / (1024 * 1024)
        if size_mb > self._MAX_SIZE_MB:
            return ToolResult(
                success=False,
                output="",
                error=f"图片过大 ({size_mb:.1f}MB)，超过限制 ({self._MAX_SIZE_MB}MB)",
            )

        import base64

        try:
            with open(resolved, "rb") as f:
                image_data = f.read()
        except IOError as e:
            return ToolResult(success=False, output="", error=f"读取图片失败: {e}")

        # 如果需要缩放
        if max_size and max_size > 0:
            try:
                image_data = self._resize_image(image_data, max_size, ext)
            except Exception:
                # 缩放失败则使用原图
                pass

        b64_data = base64.b64encode(image_data).decode("utf-8")
        mime = self._MIME_MAP.get(ext, "image/png")
        data_url = f"data:{mime};base64,{b64_data}"

        return ToolResult(
            success=True,
            output=f"图片已读取: {resolved.name} ({size_mb:.2f}MB, {mime})",
            metadata={
                "path": str(resolved),
                "size_bytes": len(image_data),
                "mime": mime,
                "data_url": data_url,
                "is_image": True,
            },
        )

    @staticmethod
    def _resize_image(image_data: bytes, max_size: int, ext: str) -> bytes:
        """等比缩放图片到最大边长"""
        import io

        try:
            from PIL import Image
        except ImportError:
            return image_data

        img = Image.open(io.BytesIO(image_data))
        w, h = img.size
        if max(w, h) <= max_size:
            return image_data

        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        output = io.BytesIO()
        fmt = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".gif": "GIF",
            ".webp": "WEBP",
            ".bmp": "BMP",
        }.get(ext, "PNG")
        img.save(output, format=fmt)
        return output.getvalue()
