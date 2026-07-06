"""
自定义斜杠命令 — 从 .claude/commands/ 和 ~/.mythcoder/commands/ 加载。
支持 Markdown frontmatter 和占位符替换。
"""

import re
import subprocess
from pathlib import Path
from typing import Optional
import yaml

from commands.base import BaseCommand


class CustomCommand(BaseCommand):
    """自定义命令包装器"""

    def __init__(
        self,
        name: str,
        description: str,
        template: str,
        aliases: Optional[list[str]] = None,
        arguments: Optional[list[dict]] = None,
    ):
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.template = template
        self.arguments = arguments or []

    async def execute(self, args: str, agent) -> Optional[str]:
        """执行自定义命令"""
        # 渲染模板
        rendered = self._render_template(args)

        # 将渲染后的文本作为用户输入传给 agent
        response = await agent.run(rendered)
        return None

    def _render_template(self, args: str) -> str:
        """渲染模板，替换占位符"""
        result = self.template

        # 替换 $ARGUMENTS（完整参数）
        result = result.replace("$ARGUMENTS", args)

        # 替换 $1, $2, ... （位置参数）
        arg_parts = args.split() if args else []
        for i, part in enumerate(arg_parts, 1):
            result = result.replace(f"${i}", part)

        # 清理未匹配的 $N
        result = re.sub(r"\$\d+", "", result)

        # 执行 `!command` shell 注入（安全实现：使用 shlex 分割，禁止 shell=True）
        def _run_shell(match):
            cmd_str = match.group(1).strip()
            try:
                import shlex
                args_list = shlex.split(cmd_str)
                if not args_list:
                    return ""
                proc = subprocess.run(
                    args_list,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                return (proc.stdout or "").strip() or f"(无输出: {cmd_str})"
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, OSError) as e:
                return f"(执行失败: {type(e).__name__})"

        result = re.sub(r"`!([^`]+)`", _run_shell, result)

        return result.strip()


class CustomCommandLoader:
    """自定义命令加载器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()

    def load_all(self) -> list[CustomCommand]:
        """加载所有自定义命令"""
        commands = []
        # 项目级命令
        project_dir = self.workspace_root / ".claude" / "commands"
        commands.extend(self._load_from_dir(project_dir))

        # 用户级命令
        user_dir = Path.home() / ".mythcoder" / "commands"
        commands.extend(self._load_from_dir(user_dir))

        return commands

    def _load_from_dir(self, dir_path: Path) -> list[CustomCommand]:
        """从目录加载命令"""
        commands = []
        if not dir_path.exists():
            return commands

        for md_file in sorted(dir_path.glob("*.md")):
            cmd = self._parse_command_file(md_file)
            if cmd:
                commands.append(cmd)

        return commands

    def _parse_command_file(self, path: Path) -> Optional[CustomCommand]:
        """解析命令文件"""
        try:
            text = path.read_text(encoding="utf-8")

            # 解析 frontmatter
            description = path.stem  # 默认用文件名
            aliases = []
            arguments = []
            content = text

            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        if isinstance(frontmatter, dict):
                            description = frontmatter.get("description", description)
                            aliases = frontmatter.get("aliases", []) or []
                            arguments = frontmatter.get("arguments", []) or []
                    except yaml.YAMLError:
                        pass
                    content = parts[2].strip()

            return CustomCommand(
                name=path.stem,
                description=description,
                template=content,
                aliases=aliases,
                arguments=arguments,
            )
        except (OSError, UnicodeDecodeError):
            return None
