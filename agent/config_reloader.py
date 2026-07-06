"""
配置热重载器 — 监听配置文件变化并自动重载。
"""

import asyncio
from pathlib import Path
from typing import Optional, Any
from utils.debug import get_debug_manager


class ConfigReloader:
    """配置热重载器"""

    def __init__(self, agent):
        self.agent = agent
        self._debug = get_debug_manager()
        self._watcher: Optional[Any] = None

    def setup(self) -> None:
        """设置配置文件监听"""
        try:
            from agent.file_watcher import FileWatcher
        except ImportError:
            return

        self._watcher = FileWatcher(self.agent.workspace_root)

        # 监听 config.yaml
        self._watcher.register_handler("config.yaml", self._on_config_changed)
        self._watcher.register_handler("*.yaml", self._on_config_changed)

        # 监听 settings.json
        self._watcher.register_handler(".mythcoder/settings.json", self._on_settings_changed)
        self._watcher.register_handler(".mythcoder/settings.local.json", self._on_settings_changed)

        # 监听 CLAUDE.md
        self._watcher.register_handler("CLAUDE.md", self._on_claude_md_changed)
        self._watcher.register_handler(".claude/CLAUDE.md", self._on_claude_md_changed)
        self._watcher.register_handler("CLAUDE.local.md", self._on_claude_md_changed)

        # 监听规则文件
        self._watcher.register_handler(".claude/rules/*.md", self._on_rules_changed)

        # 监听技能文件
        self._watcher.register_handler(".claude/skills/*.md", self._on_skills_changed)

        # 监听输出样式文件
        self._watcher.register_handler(".claude/styles/*.json", self._on_styles_changed)

        # 监听自定义命令文件
        self._watcher.register_handler(".claude/commands/*.md", self._on_commands_changed)

    def start(self) -> None:
        """启动配置监听"""
        if self._watcher:
            self._watcher.start()
            self._debug.log("agent", "配置热重载已启动")

    def stop(self) -> None:
        """停止配置监听"""
        if self._watcher:
            self._watcher.stop()

    def _on_config_changed(self, file_path: str) -> None:
        """config.yaml 变化"""
        self._debug.log("agent", f"配置文件变化: {file_path}，重新加载配置")
        try:
            self.agent.reload_config()
        except Exception as e:
            self._debug.log("agent", f"重载配置失败: {e}")

    def _on_settings_changed(self, file_path: str) -> None:
        """settings.json 变化"""
        self._debug.log("agent", f"设置文件变化: {file_path}，重新加载设置")
        try:
            if hasattr(self.agent, "settings"):
                self.agent.settings.clear_cache()
                # 重新加载权限规则
                self.agent.permission_engine._deny_rules.clear()
                self.agent.permission_engine._ask_rules.clear()
                self.agent.permission_engine._allow_rules.clear()
                self.agent.permission_engine.load_from_settings(self.agent.settings)
        except Exception as e:
            self._debug.log("agent", f"重载设置失败: {e}")

    def _on_claude_md_changed(self, file_path: str) -> None:
        """CLAUDE.md 变化"""
        self._debug.log("agent", f"CLAUDE.md 变化: {file_path}")
        try:
            if hasattr(self.agent.context, "_claude_md_loader"):
                self.agent.context._claude_md_loader._cache = None
        except Exception as e:
            self._debug.log("agent", f"重载 CLAUDE.md 失败: {e}")

    def _on_rules_changed(self, file_path: str) -> None:
        """规则文件变化"""
        self._debug.log("agent", f"规则文件变化: {file_path}")
        try:
            if hasattr(self.agent, "rules"):
                self.agent.rules.load(force_reload=True)
        except Exception as e:
            self._debug.log("agent", f"重载规则失败: {e}")

    def _on_skills_changed(self, file_path: str) -> None:
        """技能文件变化"""
        self._debug.log("agent", f"技能文件变化: {file_path}")
        try:
            if hasattr(self.agent, "skills"):
                self.agent.skills.load_all(force_reload=True)
        except Exception as e:
            self._debug.log("agent", f"重载技能失败: {e}")

    def _on_styles_changed(self, file_path: str) -> None:
        """输出样式文件变化"""
        self._debug.log("agent", f"样式文件变化: {file_path}")
        try:
            if hasattr(self.agent, "output_style_manager"):
                self.agent.output_style_manager.reload()
        except Exception as e:
            self._debug.log("agent", f"重载样式失败: {e}")

    def _on_commands_changed(self, file_path: str) -> None:
        """自定义命令文件变化"""
        self._debug.log("agent", f"自定义命令文件变化: {file_path}")
        try:
            from commands.loader import CustomCommandLoader
            from commands.registry import registry
            loader = CustomCommandLoader(self.agent.workspace_root)
            for cmd in loader.load_all():
                try:
                    registry.register(cmd)
                except ValueError:
                    pass  # 已注册，跳过
        except Exception as e:
            self._debug.log("agent", f"重载自定义命令失败: {e}")
