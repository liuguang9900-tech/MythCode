"""
NotebookEditTool — Jupyter Notebook 单元格编辑工具。
"""

from typing import Any
from tools.base import BaseTool, ToolResult


class NotebookEditTool(BaseTool):
    """Notebook 编辑工具 — cell 级别编辑"""

    name = "notebook_edit"
    description = "编辑 Jupyter Notebook 单元格，支持替换/插入/删除操作。"
    parameters = {
        "notebook_path": {
            "type": "string",
            "description": "Notebook 文件路径",
            "required": True,
        },
        "cell_id": {
            "type": "string",
            "description": "目标单元格 ID",
        },
        "cell_type": {
            "type": "string",
            "enum": ["code", "markdown", "raw"],
            "description": "单元格类型",
        },
        "operation": {
            "type": "string",
            "enum": ["replace", "insert_before", "insert_after", "delete"],
            "description": "操作类型",
            "required": True,
        },
        "source": {
            "type": "string",
            "description": "新单元格内容",
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        """执行 Notebook 编辑"""
        try:
            import nbformat
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="需要 nbformat 库: pip install nbformat",
            )

        notebook_path = kwargs.get("notebook_path", "")
        cell_id = kwargs.get("cell_id", "")
        cell_type = kwargs.get("cell_type", "code")
        operation = kwargs.get("operation", "replace")
        source = kwargs.get("source", "")

        if not notebook_path:
            return ToolResult(success=False, output="", error="notebook_path 不能为空")

        # 路径安全检查
        from tools.sandbox import get_sandbox
        sandbox = get_sandbox()
        try:
            resolved = sandbox.resolve_path(notebook_path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if sandbox.is_protected_path(str(resolved)):
            return ToolResult(
                success=False, output="", error=f"安全限制：禁止修改受保护路径"
            )

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {notebook_path}")

        if not str(resolved).endswith(".ipynb"):
            return ToolResult(success=False, output="", error="文件必须是 .ipynb 格式")

        try:
            # 读取 notebook
            nb = nbformat.read(str(resolved), as_version=4)

            # 查找目标单元格
            target_idx = None
            if cell_id:
                for i, cell in enumerate(nb.cells):
                    if cell.get("id") == cell_id:
                        target_idx = i
                        break

            if operation == "delete":
                if target_idx is None:
                    return ToolResult(success=False, output="", error=f"未找到单元格: {cell_id}")
                deleted_cell = nb.cells[target_idx]
                del nb.cells[target_idx]
                action = f"删除单元格 {cell_id}"

            elif operation == "replace":
                if target_idx is None:
                    return ToolResult(success=False, output="", error=f"未找到单元格: {cell_id}")
                new_cell = nbformat.v4.new_cell(
                    cell_type=cell_type,
                    source=source,
                    id=cell_id,
                )
                if cell_type == "code":
                    new_cell = nbformat.v4.new_code_cell(source=source, id=cell_id)
                elif cell_type == "markdown":
                    new_cell = nbformat.v4.new_markdown_cell(source=source, id=cell_id)
                else:
                    new_cell = nbformat.v4.new_raw_cell(source=source, id=cell_id)
                nb.cells[target_idx] = new_cell
                action = f"替换单元格 {cell_id}"

            elif operation in ("insert_before", "insert_after"):
                new_cell_id = cell_id or f"cell_{len(nb.cells)}"
                if cell_type == "code":
                    new_cell = nbformat.v4.new_code_cell(source=source, id=new_cell_id)
                elif cell_type == "markdown":
                    new_cell = nbformat.v4.new_markdown_cell(source=source, id=new_cell_id)
                else:
                    new_cell = nbformat.v4.new_raw_cell(source=source, id=new_cell_id)

                if target_idx is None:
                    # 没有指定位置，追加到末尾
                    nb.cells.append(new_cell)
                    action = f"追加单元格 {new_cell_id}"
                else:
                    insert_idx = target_idx if operation == "insert_before" else target_idx + 1
                    nb.cells.insert(insert_idx, new_cell)
                    action = f"{'插入前' if operation == 'insert_before' else '插入后'}单元格 {new_cell_id}"
            else:
                return ToolResult(success=False, output="", error=f"未知操作: {operation}")

            # 写入文件
            nbformat.write(nb, str(resolved))

            return ToolResult(
                success=True,
                output=f"Notebook 已更新: {action}\n文件: {resolved}\n总单元格数: {len(nb.cells)}",
                metadata={
                    "notebook_path": str(resolved),
                    "operation": operation,
                    "cell_count": len(nb.cells),
                },
            )

        except nbformat.validator.ValidationError as e:
            return ToolResult(success=False, output="", error=f"Notebook 格式错误: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"编辑 Notebook 失败: {e}")
