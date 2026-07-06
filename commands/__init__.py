"""斜杠命令包 — 对标 Claude Code 的完整命令体系。"""

from commands.registry import registry, CommandRegistry
from commands.base import BaseCommand


def register_all_commands(workspace_root: str = "."):
    """注册所有斜杠命令到 CommandRegistry"""
    from commands.help import HelpCommand
    from commands.clear import ClearCommand
    from commands.exit import ExitCommand
    from commands.config_cmd import ConfigCommand
    from commands.tools_cmd import ToolsCommand
    from commands.model import ModelCommand
    from commands.rewind import RewindCommand
    from commands.compact import CompactCommand
    from commands.cost import CostCommand
    from commands.init import InitCommand
    from commands.doctor import DoctorCommand
    from commands.review import ReviewCommand, SecurityReviewCommand
    from commands.commit import CommitCommand, PRCommand
    from commands.bug import BugCommand
    from commands.status import StatusCommand
    from commands.upgrade import UpgradeCommand
    from commands.ide import IDECommand
    from commands.permissions_cmd import PermissionsCommand
    from commands.memory_cmd import MemoryCommand
    from commands.add_dir import AddDirCommand
    from commands.plan_cmd import PlanCommand
    from commands.skill_cmd import SkillCommand
    from commands.sessions_cmd import SessionsCommand
    from commands.switch_cmd import SwitchCommand
    from commands.fork_cmd import ForkCommand
    from commands.branch_cmd import BranchCommand
    from commands.merge_cmd import MergeCommand
    from commands.style_cmd import StyleCommand

    commands = [
        HelpCommand(),
        ClearCommand(),
        ExitCommand(),
        ConfigCommand(),
        ToolsCommand(),
        ModelCommand(),
        RewindCommand(),
        CompactCommand(),
        CostCommand(),
        InitCommand(),
        DoctorCommand(),
        ReviewCommand(),
        SecurityReviewCommand(),
        CommitCommand(),
        PRCommand(),
        BugCommand(),
        StatusCommand(),
        UpgradeCommand(),
        IDECommand(),
        PermissionsCommand(),
        MemoryCommand(),
        AddDirCommand(),
        PlanCommand(),
        SkillCommand(),
        SessionsCommand(),
        SwitchCommand(),
        ForkCommand(),
        BranchCommand(),
        MergeCommand(),
        StyleCommand(),
    ]

    for cmd in commands:
        try:
            registry.register(cmd)
        except ValueError:
            pass  # 已注册，跳过

    # 加载自定义命令
    try:
        from commands.loader import CustomCommandLoader
        loader = CustomCommandLoader(workspace_root)
        for cmd in loader.load_all():
            try:
                registry.register(cmd)
            except ValueError:
                pass
    except Exception:
        pass  # 自定义命令加载失败不影响主流程

    return registry
