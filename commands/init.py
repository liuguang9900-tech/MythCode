"""
/init — 分析项目结构，生成 CLAUDE.md 项目上下文文件。
"""

import os
from pathlib import Path
from commands.base import BaseCommand
from ui.console import console, print_error, print_info
from utils.agentignore import get_ignore_manager


class InitCommand(BaseCommand):
    name = "init"
    description = "分析项目并生成 CLAUDE.md 上下文文件"

    async def execute(self, args: str, agent) -> None:
        workspace = Path(agent.workspace_root)
        output_path = workspace / "CLAUDE.md"

        if output_path.exists() and "--force" not in args:
            console.print(f"[yellow]CLAUDE.md 已存在[/yellow] ({output_path})")
            console.print("[dim]使用 /init --force 强制覆盖[/dim]")
            return

        console.print("[dim]正在分析项目结构...[/dim]")

        # 收集项目信息
        info = _analyze_project(workspace)

        # 构建 prompt 让 LLM 生成 CLAUDE.md
        prompt = f"""请为以下项目生成一个 CLAUDE.md 文件。CLAUDE.md 是给 AI 编程助手看的项目上下文文件，
包含项目的技术栈、架构、编码规范、常用命令等信息。

## 项目信息
- 项目路径: {workspace}
- 检测到的语言: {', '.join(info['languages']) if info['languages'] else '未知'}
- 构建系统: {', '.join(info['build_systems']) if info['build_systems'] else '未知'}
- 框架: {', '.join(info['frameworks']) if info['frameworks'] else '未知'}

## 目录结构
```
{info['tree']}
```

## 要求
请生成一个简洁、实用的 CLAUDE.md，包含：
1. 项目简介
2. 技术栈
3. 项目结构说明
4. 常用命令（构建、测试、运行）
5. 编码规范要点
6. 注意事项

用中文输出，Markdown 格式。直接输出 CLAUDE.md 内容，不要加额外说明。"""

        try:
            console.print("[dim]正在调用 LLM 生成 CLAUDE.md...[/dim]")
            response = await agent.llm.chat_simple(
                system="你是一个专业的技术文档撰写助手。",
                user=prompt,
            )

            # 写入文件
            output_path.write_text(response, encoding="utf-8")
            console.print(f"[green]CLAUDE.md 已生成:[/green] {output_path}")
            console.print("[dim]你可以编辑此文件来完善项目上下文[/dim]")

        except Exception as e:
            print_error(f"生成 CLAUDE.md 失败: {e}")


def _analyze_project(workspace: Path) -> dict:
    """分析项目结构"""
    languages = set()
    build_systems = set()
    frameworks = set()

    # 检测语言和构建系统
    indicators = {
        "pyproject.toml": ("Python", "setuptools/poetry"),
        "setup.py": ("Python", "setuptools"),
        "requirements.txt": ("Python", "pip"),
        "package.json": ("JavaScript/TypeScript", "npm/yarn"),
        "tsconfig.json": ("TypeScript", "TypeScript"),
        "go.mod": ("Go", "Go modules"),
        "Cargo.toml": ("Rust", "Cargo"),
        "Makefile": (None, "Make"),
        "CMakeLists.txt": ("C/C++", "CMake"),
        "Dockerfile": (None, "Docker"),
        "docker-compose.yml": (None, "Docker Compose"),
    }

    for filename, (lang, build) in indicators.items():
        if (workspace / filename).exists():
            if lang:
                languages.add(lang)
            if build:
                build_systems.add(build)

    # 检测框架
    framework_indicators = {
        "next.config.js": "Next.js",
        "vite.config.ts": "Vite",
        "tailwind.config.js": "Tailwind CSS",
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "pytest": "pytest",
    }

    for indicator, framework in framework_indicators.items():
        if list(workspace.glob(f"**/{indicator}")):
            frameworks.add(framework)

    # 生成目录树（限制深度和条目）
    tree_lines = [workspace.name + "/"]
    _walk_tree(workspace, max_depth=3, max_items=60, lines=tree_lines, prefix="", depth=0)

    return {
        "languages": sorted(languages),
        "build_systems": sorted(build_systems),
        "frameworks": sorted(frameworks),
        "tree": "\n".join(tree_lines),
    }


def _walk_tree(directory: Path, max_depth: int, max_items: int,
               lines: list, prefix: str, depth: int) -> None:
    if depth >= max_depth or len(lines) >= max_items:
        return

    try:
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return

    ignore_mgr = get_ignore_manager(str(directory))

    entries = [e for e in entries if not ignore_mgr.is_ignored(e)]

    for i, entry in enumerate(entries):
        if len(lines) >= max_items:
            lines.append(f"{prefix}... (更多文件)")
            return

        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")

        if entry.is_dir():
            ext = "    " if is_last else "│   "
            _walk_tree(entry, max_depth, max_items, lines, prefix + ext, depth + 1)
