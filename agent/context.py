"""
上下文管理器 — 系统 Prompt + 对话历史 + 工作区状态合并。
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import get_config
from agent.memory import ConversationMemory
from agent.claude_md import CLAUDEMdLoader
from utils.agentignore import get_ignore_manager


# ============================================================
# 系统 Prompt 模板
# ============================================================

# ============================================================
# 系统 Prompt 模板（模块化常量，便于维护）
# ============================================================

# 核心身份与工作原则
_PROMPT_IDENTITY = """你是一个自主 AI 编程智能体，帮助开发者完成软件工程任务。

## 工作原则
1. 先理解再行动：修改代码前先阅读相关文件。
2. 最小改动：只做必要的修改，不过度工程化。
3. 安全第一：危险命令需确认；不修改受保护路径。
4. 诚实透明：不确定时明确告知，不编造。
"""

# 工具使用规范（精简版，详细参数见工具 schema）
_PROMPT_TOOLS = """## 工具使用
- 找文件名用 glob，找内容用 search_code，看目录用 list_directory
- 修改文件优先用 edit_file（精确替换），新建文件用 write_file
- 编辑前先 read_file 确认内容和缩进
- 复杂任务用 todo_write 跟踪进度
- 命令非交互式，超时120s，危险命令需确认
- 扩展工具（需要时调用）：todo_write(任务清单)、task(子代理)、web_fetch/web_search(网络)、read_image(图片)、notebook_edit(Notebook)
"""

# 代码风格指南
_PROMPT_CODE_STYLE = """## 代码风格
- 遵循项目现有风格（缩进、命名、注释）
- Python 添加类型注解，复杂逻辑加中文注释
- 不引入未要求的新依赖
"""

# Git 工作流
_PROMPT_GIT = """## Git
- commit: 中文，格式 `<类型>: <描述>`（feat/fix/refactor/docs/test/chore）
- 不自动 push，除非用户明确要求
"""

# 输出规范
_PROMPT_OUTPUT = """## 输出
- Markdown 格式，代码块标注语言
- 引用代码用 `path:line` 格式
- 操作前说明意图，操作后说明结果
"""

# 环境信息模板
_PROMPT_ENV = """## 当前工作环境
- 工作目录: {workspace_root}
- 操作系统: {os_name}
- 当前时间: {current_time}

{workspace_summary}"""

# 完整系统 Prompt（由以上模块拼接）
SYSTEM_PROMPT = _PROMPT_IDENTITY + "\n" + _PROMPT_TOOLS + "\n" + _PROMPT_CODE_STYLE + "\n" + _PROMPT_GIT + "\n" + _PROMPT_OUTPUT + "\n" + _PROMPT_ENV


class ContextManager:
    """上下文管理器 — 组装每次 LLM 调用的完整上下文"""

    def __init__(self, memory: ConversationMemory, workspace_root: str = "."):
        self.memory = memory
        self.workspace_root = Path(workspace_root).resolve()
        self.cfg = get_config()
        self.additional_roots: list[Path] = []
        self.disable_claude_md = False
        self.disable_auto_memory = False
        self._auto_memory_mgr = None
        self._rules_mgr = None
        self._todo_mgr = None
        self._skills_mgr = None
        self._plan_mgr = None
        self._subagent_prompt: Optional[str] = None
        self._subagent_type: Optional[str] = None
        self._claude_md_loader = CLAUDEMdLoader(str(self.workspace_root))

    def set_additional_roots(self, roots: list[str]) -> None:
        """设置额外的工作目录"""
        self.additional_roots = [Path(r).resolve() for r in roots]

    def set_auto_memory(self, mgr) -> None:
        """设置自动记忆管理器"""
        self._auto_memory_mgr = mgr

    def set_rules(self, mgr) -> None:
        """设置规则管理器"""
        self._rules_mgr = mgr

    def set_todo(self, mgr) -> None:
        """设置 TODO 管理器"""
        self._todo_mgr = mgr

    def set_skills(self, mgr) -> None:
        """设置技能管理器"""
        self._skills_mgr = mgr

    def set_subagent_prompt(self, prompt: str, task_type: str) -> None:
        """设置子代理专用 prompt"""
        self._subagent_prompt = prompt
        self._subagent_type = task_type

    def set_plan_manager(self, mgr) -> None:
        """设置计划管理器"""
        self._plan_mgr = mgr

    def build_system_prompt(self) -> str:
        """构建系统 Prompt"""
        workspace_summary = ""
        if self.cfg.agent.workspace_summary:
            workspace_summary = self._generate_workspace_summary()

        # 额外工作目录信息
        additional_dirs = ""
        if self.additional_roots:
            dirs = "\n".join(f"- {d}" for d in self.additional_roots)
            additional_dirs = f"\n## 额外工作目录\n{dirs}\n"

        prompt = SYSTEM_PROMPT.format(
            workspace_root=self.workspace_root,
            os_name=self._get_os_name(),
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            workspace_summary=workspace_summary + additional_dirs,
        )

        # 追加 CLAUDE.md 内容
        if not self.disable_claude_md:
            claude_md_content = self._claude_md_loader.load()
            if claude_md_content:
                prompt += f"\n\n## 项目上下文 (CLAUDE.md)\n{claude_md_content}"

        # 追加自动记忆
        if not self.disable_auto_memory and self._auto_memory_mgr:
            memory_context = self._auto_memory_mgr.get_context_for_prompt()
            if memory_context:
                prompt += f"\n\n{memory_context}"

        # 追加项目规则
        if self._rules_mgr:
            rules_context = self._rules_mgr.get_all_context_for_prompt()
            if rules_context:
                prompt += f"\n\n{rules_context}"

        # 追加当前 TODO 任务清单
        if self._todo_mgr:
            todo_context = self._todo_mgr.get_context_for_prompt()
            if todo_context:
                prompt += f"\n\n{todo_context}"

        # 追加技能：使用渐进式披露（仅 name+description），auto_activate 的技能附加完整内容
        if self._skills_mgr:
            skills_context = self._skills_mgr.get_summary_for_prompt()
            if skills_context:
                prompt += f"\n\n{skills_context}"

        # 追加计划上下文
        if self._plan_mgr:
            plan_context = self._plan_mgr.get_plan_context_for_prompt()
            if plan_context:
                prompt += f"\n\n{plan_context}"

        # 子代理专用 prompt 覆盖（如果是子代理）
        if self._subagent_prompt:
            prompt = self._subagent_prompt + "\n\n## 工作目录\n" + str(self.workspace_root)

        return prompt

    def build_messages(self, user_input: str, images: Optional[list[str]] = None) -> list[dict]:
        """
        构建完整的消息列表，用于 LLM 调用。

        Args:
            user_input: 用户文本输入
            images: 可选的图片列表（base64 编码或文件路径）

        Returns:
            [system_msg, ...history, user_msg]
        """
        messages = [
            {"role": "system", "content": self.build_system_prompt()},
        ]

        # 添加对话历史
        messages.extend(self.memory.get_messages())

        # 添加当前用户输入
        if images:
            # 多模态消息：content 为数组，包含文本和图片
            content: list = [{"type": "text", "text": user_input}]
            for img in images:
                content.append(self._build_image_content(img))
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_input})

        return messages

    @staticmethod
    def _build_image_content(image: str) -> dict:
        """
        构建图片内容块。
        支持格式：
        - 文件路径：自动读取并转 base64
        - data:image/xxx;base64,...：直接使用
        - 纯 base64 字符串：自动添加前缀
        """
        import base64
        from pathlib import Path

        # 已是 data URL 格式
        if image.startswith("data:image/"):
            return {"type": "image_url", "image_url": {"url": image}}

        # 文件路径
        if not image.startswith("base64:") and Path(image).exists():
            try:
                with open(image, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                # 推断 MIME
                ext = Path(image).suffix.lower()
                mime_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }
                mime = mime_map.get(ext, "image/png")
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                }
            except IOError:
                pass

        # 纯 base64
        if not image.startswith("base64:"):
            image = "base64:" + image
        b64_data = image[7:]
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64_data}"},
        }

    def _generate_workspace_summary(self) -> str:
        """生成工作区文件树摘要"""
        try:
            depth = getattr(self.cfg.agent, "workspace_summary_depth", 1)
            max_items = getattr(self.cfg.agent, "workspace_summary_max_items", 30)
            tree = self._get_directory_tree(self.workspace_root, max_depth=depth, max_items=max_items)
            return f"## 工作区文件结构\n```\n{tree}\n```"
        except Exception:
            return ""

    def _get_directory_tree(
        self, directory: Path, max_depth: int = 2, max_items: int = 50, prefix: str = ""
    ) -> str:
        """生成目录树字符串"""
        lines = [directory.name + "/"]
        self._walk_tree(directory, max_depth, max_items, lines, "", 0)
        return "\n".join(lines)

    def _walk_tree(
        self, directory: Path, max_depth: int, max_items: int,
        lines: list, prefix: str, depth: int
    ) -> None:
        if depth >= max_depth or len(lines) >= max_items:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        # 使用 .agentignore / .gitignore 规则过滤
        ignore_mgr = get_ignore_manager(str(self.workspace_root), self.cfg.tools.search_respect_gitignore)
        entries = [e for e in entries if not ignore_mgr.is_ignored(e, self.workspace_root)]

        for i, entry in enumerate(entries):
            if len(lines) >= max_items:
                lines.append(f"{prefix}... (更多文件)")
                return

            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")

            if entry.is_dir():
                ext = "    " if is_last else "│   "
                self._walk_tree(entry, max_depth, max_items, lines, prefix + ext, depth + 1)

    @staticmethod
    def _get_os_name() -> str:
        """获取操作系统名称"""
        import platform
        system = platform.system()
        if system == "Darwin":
            return f"macOS {platform.mac_ver()[0]}"
        elif system == "Linux":
            return "Linux"
        elif system == "Windows":
            return "Windows"
        return system
