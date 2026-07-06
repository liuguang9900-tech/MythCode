#!/usr/bin/env python3
"""
MythCoder — 本地自主 AI 编程智能体 CLI 入口。

用法:
    MythCoder                          # 全新对话
    MythCoder -r latest                 # 恢复上次对话继续
    MythCoder -x "帮我重构这个函数"      # 单次执行模式
    MythCoder --workspace /path/to/project  # 指定工作目录
    MythCoder --model gpt-4o           # 指定模型
"""

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_env_file() -> None:
    """
    加载 .env 文件到 os.environ（不覆盖已存在的环境变量）。
    依次查找：当前工作目录、用户主目录 ~/.mythcoder/.env。
    """
    search_paths = [
        Path.cwd() / ".env",
        Path.home() / ".mythcoder" / ".env",
    ]
    for env_path in search_paths:
        if not env_path.exists():
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith("#"):
                        continue
                    # 解析 KEY=VALUE
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # 去除可能的引号包裹
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    # 不覆盖已存在的环境变量
                    if key and key not in os.environ:
                        os.environ[key] = value
        except IOError:
            pass


# 在导入 config 之前加载 .env
_load_env_file()

from config import init_config, get_config
from tools.init_tools import register_all_tools
from tools.sandbox import get_sandbox
from agent.loop import AgentLoop
from agent.memory import ConversationMemory
from agent.context import ContextManager
from llm.client import LLMClient
from ui.console import (
    console, print_welcome, print_help, print_config_info,
    print_tools_list, print_tool_call, print_tool_result,
    print_approval_request, print_error, print_info,
    print_rewind_steps, print_rewind_result,
    print_restored_conversation, print_json_output,
)
from ui.prompt import create_session, get_prompt_message
from ui.display import StreamDisplay
from utils.debug import get_debug_manager
from commands import register_all_commands
from commands.registry import registry as command_registry


# ============================================================
# SIGINT 中断处理
# ============================================================

_current_agent = None
_sigint_count = 0


def _sigint_handler(signum, frame):
    """Ctrl+C 中断处理：第一次取消当前任务，第二次强制退出"""
    global _sigint_count
    _sigint_count += 1
    if _sigint_count == 1:
        if _current_agent:
            _current_agent.cancel_current()
        console.print("\n[yellow]⏸  正在中断... (再按一次 Ctrl+C 强制退出)[/yellow]")
    else:
        console.print("\n[dim]强制退出[/dim]")
        sys.exit(1)


def _reset_sigint():
    """重置 SIGINT 计数器（每次 agent.run() 完成后调用）"""
    global _sigint_count
    _sigint_count = 0


# ============================================================
# CLI 参数解析
# ============================================================

def _get_version() -> str:
    """读取版本号：优先从已安装包元数据，其次从 pyproject.toml"""
    # 1. 从已安装包的元数据读取（pip install 后可用）
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version("mythcoder")
        except PackageNotFoundError:
            pass
    except ImportError:
        pass

    # 2. 从源码目录的 pyproject.toml 读取（开发模式）
    try:
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("version ="):
                    return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return "0.0.0"


def parse_args():
    parser = argparse.ArgumentParser(
        description="MythCoder - 本地自主 AI 编程智能体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  MythCoder                              # 全新对话
  MythCoder -r latest                    # 恢复上次对话
  MythCoder -x "找到所有 TODO 注释"       # 单次执行
  MythCoder --workspace ~/myproject      # 指定工作目录
  MythCoder dashboard                    # 启动 Token 用量可视化面板
  MythCoder dashboard -p 9090            # 指定端口
  MythCoder --model claude-3-5-sonnet    # 指定模型
  MythCoder -p -x "列出文件"              # 非交互输出
  MythCoder --max-turns 5 -x "分析代码"   # 限制迭代次数
  MythCoder --debug=llm,tools            # 调试模式
  MythCoder --add-dir /path/to/libs      # 额外工作目录
  MythCoder -n "重构会话"                 # 命名会话
  MythCoder --safe-mode                  # 安全模式
  MythCoder --permission-mode plan       # 权限模式
        """,
    )
    # dashboard 子命令：启动 Token 用量可视化面板
    subparsers = parser.add_subparsers(dest="command")
    dash_parser = subparsers.add_parser(
        "dashboard",
        help="启动 Token 用量可视化面板",
        description="启动 Web 可视化面板，展示 Token 用量统计",
    )
    dash_parser.add_argument("-p", "--port", type=int, default=8080, help="端口号 (默认: 8080)")
    dash_parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
    dash_parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    dash_parser.add_argument("--token", default=None, help="访问令牌 (可选)")
    # 版本号
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"MythCoder v{_get_version()}",
        help="显示版本号并退出",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=".",
        help="工作目录路径 (默认: 当前目录)",
    )
    parser.add_argument(
        "-m", "--model",
        default=None,
        help="模型名称 (覆盖配置文件)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径",
    )
    # 恢复会话（替代旧的 -c/--continue）
    parser.add_argument(
        "-r", "--resume",
        default=None,
        nargs="?",
        const="latest",
        help="恢复指定会话 (默认: latest 恢复最新会话)",
    )
    parser.add_argument(
        "-c", "--continue",
        action="store_true",
        default=False,
        dest="continue_conv",
        help="(已废弃) 请使用 -r latest",
    )
    parser.add_argument(
        "-x", "--exec",
        default=None,
        dest="exec_cmd",
        help="单次执行模式: 直接执行一条指令后退出",
    )
    parser.add_argument(
        "-n", "--name",
        default=None,
        help="会话名称",
    )
    # 非交互输出模式
    parser.add_argument(
        "-p", "--print",
        action="store_true",
        default=False,
        dest="print_mode",
        help="非交互输出模式 (配合 -x 使用)",
    )
    parser.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json", "stream-json"],
        help="输出格式: text, json, stream-json (默认: text)",
    )
    # 迭代限制
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="最大推理迭代次数 (覆盖配置文件)",
    )
    # 调试模式
    parser.add_argument(
        "--debug",
        default=None,
        nargs="?",
        const="all",
        help="调试模式: all 或逗号分隔的分类 (llm,tools,agent)",
    )
    # 额外工作目录
    parser.add_argument(
        "--add-dir",
        action="append",
        default=[],
        help="额外工作目录 (可多次指定)",
    )
    # 安全模式
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        default=False,
        help="安全模式: 禁用 CLAUDE.md、hooks、skills、auto-memory",
    )
    # 权限模式
    parser.add_argument(
        "--permission-mode",
        default="default",
        choices=["default", "acceptEdits", "plan", "auto", "bypassPermissions"],
        help="权限模式 (默认: default)",
    )
    # 设置
    parser.add_argument(
        "--settings",
        default=None,
        help="JSON 设置文件路径或内联 JSON 字符串",
    )
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="跳过所有安全确认 (不推荐)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="在当前目录生成模板配置文件 (.env 和 config.yaml)",
    )
    return parser.parse_args()


# ============================================================
# Agent 回调实现
# ============================================================

class AgentCallbacks:
    """将 Agent 事件桥接到 UI 层"""

    def __init__(self, stream_display: StreamDisplay, no_approval: bool = False):
        self.stream = stream_display
        self.no_approval = no_approval
        self.current_tool_name = ""

    async def on_text_chunk(self, text: str):
        """LLM 文本增量 → 流式渲染"""
        if not self.stream.is_active:
            self.stream.start()
        self.stream.add_chunk(text)

    async def on_tool_call(self, name: str, args: dict) -> bool:
        """工具调用 → 显示 + 确认"""
        self.current_tool_name = name

        # 如果正在流式输出，先结束
        if self.stream.is_active:
            self.stream.finish()

        # 检查是否需要用户确认
        requires_approval = args.pop("_requires_approval", False)
        reason = args.pop("_reason", "")

        if requires_approval and not self.no_approval:
            command = args.get("command", "")
            print_approval_request(command, reason)
            try:
                response = input("  > [y] 执行 / [n] 取消 / [a] 总是允许 > ").strip().lower()
                if response in ("a", "always", "总是允许"):
                    # 记录会话级"总是允许"规则
                    if _current_agent is not None:
                        _current_agent.permission_engine.add_session_allow(name, args)
                    console.print("[green]已记住：后续相同类型的操作将自动批准[/green]")
                    return True
                return response in ("y", "yes", "是")
            except (EOFError, KeyboardInterrupt):
                return False

        print_tool_call(name, args)
        return True

    async def on_tool_result(self, name: str, output: str, success: bool, metadata: dict = None):
        """工具结果 → 显示"""
        # 读类工具返回大量内容，不显示任何输出预览
        _READ_TOOLS = {"read_file", "search_code", "list_directory", "glob", "grep"}
        if name in _READ_TOOLS and success:
            return  # 读工具静默处理，不打印结果

        print_tool_result(name, success, output)

        # todo_write 工具执行后渲染 TODO 面板
        if name == "todo_write" and success and _current_agent is not None:
            from ui.console import print_todo_list
            print_todo_list(_current_agent.todo.get_todos())

        # 写操作工具执行后展示 diff 预览
        if name in ("write_file", "edit_file") and success and metadata:
            from ui.console import print_diff_preview
            diff_text = metadata.get("diff", "")
            is_new_file = metadata.get("is_new_file", False)
            file_path = metadata.get("path", name)
            if diff_text or is_new_file:
                print_diff_preview(file_path, diff_text, is_new_file)


class StreamJSONCallbacks:
    """
    stream-json 模式专用回调：每个事件输出一行 JSON（JSON Lines 格式）。
    事件类型：text_delta / tool_call / tool_result / thinking / compression / result
    """

    def __init__(self, no_approval: bool = False):
        self.no_approval = no_approval
        self._text_buffer = ""

    def _emit(self, event: dict) -> None:
        """输出一行 JSON"""
        import json
        print(json.dumps(event, ensure_ascii=False), flush=True)

    async def on_text_chunk(self, text: str):
        """文本增量事件"""
        self._text_buffer += text
        self._emit({
            "type": "text_delta",
            "content": text,
        })

    async def on_tool_call(self, name: str, args: dict) -> bool:
        """工具调用事件"""
        # 弹出内部字段
        args_copy = {k: v for k, v in args.items() if not k.startswith("_")}
        self._emit({
            "type": "tool_call",
            "name": name,
            "args": args_copy,
        })
        # stream-json 模式默认不交互确认
        return True

    async def on_tool_result(self, name: str, output: str, success: bool, metadata: dict = None):
        """工具结果事件"""
        # 截断过长的输出
        result_preview = output
        if output and len(output) > 2000:
            result_preview = output[:2000] + "...(truncated)"
        self._emit({
            "type": "tool_result",
            "name": name,
            "success": success,
            "output": result_preview,
            "metadata": metadata or {},
        })

    async def on_thinking(self, thinking: str):
        """思考过程事件"""
        self._emit({
            "type": "thinking",
            "content": thinking,
        })

    async def on_compression(self, info: dict):
        """压缩通知事件"""
        self._emit({
            "type": "compression",
            "info": info,
        })

    def emit_result(self, response: str, agent) -> None:
        """输出最终结果事件"""
        usage = agent.get_token_usage()
        self._emit({
            "type": "result",
            "response": response,
            "stats": {
                "steps": agent.session_map.current_step_id,
                "messages": len(agent.memory.messages),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "context_usage_pct": usage.get("context_usage_pct", 0),
            },
        })


# ============================================================
# 交互式 REPL
# ============================================================

async def run_repl(agent: AgentLoop, session, callbacks: AgentCallbacks, resume_id: str = None):
    """运行交互式 REPL 循环"""
    # 异步初始化（MCP 等）
    await agent.initialize()
    print_welcome()

    # --resume 参数：恢复指定会话
    if resume_id:
        restored_info = agent.load_conversation(resume_id)
        if restored_info:
            print_restored_conversation(restored_info)
        else:
            print_info(f"没有可恢复的会话: {resume_id}")

    # 兼容旧的 -c 参数
    if agent._continue_conv:
        restored_info = agent.load_conversation("latest")
        if restored_info:
            print_restored_conversation(restored_info)
        else:
            print_info("没有可恢复的对话记录")

    while True:
        try:
            user_input = await session.prompt_async(
                get_prompt_message(),
            )
        except (EOFError, KeyboardInterrupt):
            agent.save_conversation()
            await agent.notify_session_end()
            console.print("\n[dim]再见![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # 处理内置命令
        # 注意：仅当 / 后第一个 token 不含 / 时才视为斜杠命令，
        # 避免把 "/Users/luogang/..." 这类文件路径误判为命令
        if user_input.startswith("/"):
            first_token = user_input.split(maxsplit=1)[0]
            cmd_name = first_token.lower().lstrip("/")
            if "/" not in cmd_name:
                handled = await dispatch_command(user_input, agent)
                if handled == "exit":
                    await agent.notify_session_end()
                    break
                continue
            # cmd_name 含 /：是文件路径，作为普通输入交给 agent

        try:
            response = await agent.run(user_input)
        except asyncio.CancelledError:
            callbacks.stream.finish()
            console.print("\n[yellow](已中断)[/yellow]")
            _reset_sigint()
            continue
        except Exception as e:
            callbacks.stream.finish()
            print_error(f"执行异常: {e}")
            _reset_sigint()
            continue

        _reset_sigint()
        callbacks.stream.finish()

        # 如果 response 已经在流式输出中显示了，不再重复
        if not callbacks.stream.get_text():
            console.print(response)


async def dispatch_command(cmd: str, agent: AgentLoop) -> str | None:
    """
    使用 CommandRegistry 分发斜杠命令。
    返回 "exit" 表示需要退出程序。
    """
    parts = cmd.split(maxsplit=1)
    command_name = parts[0].lower().lstrip("/")
    args = parts[1] if len(parts) > 1 else ""

    cmd_obj = command_registry.get(command_name)
    if cmd_obj is None:
        print_error(f"未知命令: /{command_name}，输入 /help 查看帮助")
        return None

    try:
        result = await cmd_obj.execute(args, agent)
        return result
    except Exception as e:
        print_error(f"命令执行异常: {e}")
        return None


# ============================================================
# 非交互输出模式
# ============================================================

async def run_print_mode(agent: AgentLoop, command: str, output_format: str, callbacks: AgentCallbacks):
    """非交互输出模式：执行指令并以指定格式输出结果"""
    await agent.initialize()

    # stream-json 模式：使用专用回调，实时输出每个事件
    if output_format == "stream-json":
        json_callbacks = StreamJSONCallbacks(no_approval=callbacks.no_approval)
        # 重新绑定 agent 回调
        agent.on_text_chunk = json_callbacks.on_text_chunk
        agent.on_tool_call = json_callbacks.on_tool_call
        agent.on_tool_result = json_callbacks.on_tool_result
        agent.on_thinking = json_callbacks.on_thinking
        agent.on_compression = json_callbacks.on_compression

        try:
            response = await agent.run(command)
        except Exception as e:
            json_callbacks._emit({
                "type": "error",
                "error": str(e),
            })
            agent.save_conversation()
            await agent.notify_session_end()
            sys.exit(1)

        json_callbacks.emit_result(response, agent)
        agent.save_conversation()
        await agent.notify_session_end()
        return

    try:
        response = await agent.run(command)
    except Exception as e:
        callbacks.stream.finish()
        result = {"error": str(e), "success": False}
        print_json_output(result, output_format)
        agent.save_conversation()
        await agent.notify_session_end()
        sys.exit(1)

    callbacks.stream.finish()

    if output_format == "text":
        # 纯文本输出到 stdout
        text = callbacks.stream.get_text() or response
        print(text)
    elif output_format == "json":
        result = {
            "response": response,
            "tool_calls": agent.session_map.get_all_steps()[-1].tool_calls if agent.session_map.get_all_steps() else [],
            "stats": {
                "steps": agent.session_map.current_step_id,
                "messages": len(agent.memory.messages),
            },
        }
        print_json_output(result, "json")

    agent.save_conversation()
    await agent.notify_session_end()


# ============================================================
# 单次执行模式
# ============================================================

async def run_single(agent: AgentLoop, command: str, callbacks: AgentCallbacks):
    """单次执行模式：执行一条指令后退出"""
    await agent.initialize()
    try:
        response = await agent.run(command)
    except Exception as e:
        callbacks.stream.finish()
        print_error(f"执行异常: {e}")
        agent.save_conversation()
        sys.exit(1)

    callbacks.stream.finish()
    agent.save_conversation()
    if not callbacks.stream.get_text():
        console.print(response)


# ============================================================
# 初始化
# ============================================================

def initialize(args):
    """初始化所有组件"""
    # 1. 加载配置
    overrides = {}
    if args.model:
        overrides["model.name"] = args.model
    if args.no_approval:
        overrides["safety.require_approval"] = False
    if args.max_turns is not None:
        overrides["agent.max_iterations"] = args.max_turns

    # 处理 --settings
    if args.settings:
        _apply_settings(args.settings, overrides)

    init_config(args.config, overrides)
    cfg = get_config()

    # 2. 解析工作目录
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print_error(f"工作目录不存在: {workspace}")
        sys.exit(1)
    cfg.safety.project_root = str(workspace)

    # 3. 注册工具和命令
    register_all_tools()
    register_all_commands(str(workspace))

    # 4. 初始化调试管理器
    if args.debug:
        debug_mgr = get_debug_manager()
        debug_mgr.enable(args.debug)

    # 5. 创建核心组件
    stream_display = StreamDisplay()
    callbacks = AgentCallbacks(stream_display, no_approval=args.no_approval)

    agent = AgentLoop(
        workspace_root=str(workspace),
        on_text_chunk=callbacks.on_text_chunk,
        on_tool_call=callbacks.on_tool_call,
        on_tool_result=callbacks.on_tool_result,
        safe_mode=args.safe_mode,
        permission_mode=args.permission_mode,
        session_name=args.name,
        additional_roots=args.add_dir,
    )

    return agent, callbacks, stream_display


def _apply_settings(settings_arg: str, overrides: dict) -> None:
    """解析 --settings 参数并合并到 overrides"""
    settings_data = None
    # 尝试作为文件路径
    settings_path = Path(settings_arg)
    if settings_path.exists() and settings_path.is_file():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print_error(f"无法解析设置文件: {e}")
            return
    else:
        # 尝试作为内联 JSON
        try:
            settings_data = json.loads(settings_arg)
        except json.JSONDecodeError:
            print_error(f"设置参数不是有效的 JSON 或文件路径: {settings_arg}")
            return

    if settings_data and isinstance(settings_data, dict):
        _flatten_settings(settings_data, "", overrides)


def _flatten_settings(data: dict, prefix: str, overrides: dict) -> None:
    """将嵌套 dict 展平为点号分隔的 key"""
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and not isinstance(value, list):
            _flatten_settings(value, full_key, overrides)
        else:
            overrides[full_key] = value


# ============================================================
# 模板配置生成
# ============================================================

_TEMPLATE_ENV = """\
# MythCoder 环境变量配置
# 此文件用于存放 API 密钥等敏感信息，请勿提交到版本控制

# 必填：模型 API 密钥
MYTHCODER_API_KEY=your-api-key-here

# 可选：覆盖默认模型配置
# MYTHCODER_MODEL=deepseek-v4-pro
# MYTHCODER_API_BASE=https://api.deepseek.com/v1
"""

_TEMPLATE_CONFIG = """\
# MythCoder 配置文件
# 完整配置说明请参考 README.md

# --- 大模型配置 ---
model:
  provider: "openai"                      # OpenAI 兼容格式（DeepSeek/Qwen/Kimi 等均适用）
  name: "deepseek-v4-pro"                 # 模型名称
  api_key: "${MYTHCODER_API_KEY}"         # 从环境变量读取（推荐）
  api_base: "https://api.deepseek.com/v1" # API 地址
  temperature: 0.2                        # 生成温度（代码任务建议 0.1-0.3）
  max_tokens: 8192                        # 单次响应最大 Token 数
  timeout: 120                            # 请求超时（秒）

# --- Agent 核心参数 ---
agent:
  max_iterations: 30
  context_window: 128000
  history_max_turns: 20
  summary_threshold: 0.7
  workspace_summary: true
  workspace_summary_depth: 1
  workspace_summary_max_items: 30
  max_tool_result_tokens: 2000
  preserve_important_messages: true

# --- 安全策略 ---
safety:
  project_root: "."
  require_approval: true
  dangerous_commands:
    - "rm\\\\s+(-rf?\\\\s+)?/"
    - "sudo\\\\s+rm"
    - "git\\\\s+push\\\\s+--force"
  protected_paths:
    - "~/.ssh"
    - "~/.aws"
  allowed_commands:
    - "ls"
    - "cat"
    - "git\\\\s+status"

# --- 工具配置 ---
tools:
  file_max_size_mb: 10
  command_timeout: 120
  search_max_results: 50

# --- 时空回溯 ---
time_travel:
  enabled: true
  max_snapshots: 100
  snapshot_dir: ".agent_snapshots"
  auto_snapshot: true

# --- 对话持久化 ---
persistence:
  persist_conversation: true
  storage_dir: ".mythcoder"

# --- UI 配置 ---
ui:
  theme: "dark"
  show_tool_calls: true
  syntax_theme: "monokai"
  max_output_lines: 500
"""


def _generate_template_config() -> None:
    """在当前目录生成模板配置文件"""
    from ui.console import console, print_success, print_info
    from rich.panel import Panel
    from rich import box

    cwd = Path.cwd()
    env_path = cwd / ".env"
    config_path = cwd / "config.yaml"

    created = []
    skipped = []

    # 生成 .env
    if env_path.exists():
        skipped.append((".env", env_path))
    else:
        env_path.write_text(_TEMPLATE_ENV, encoding="utf-8")
        created.append((".env", env_path))

    # 生成 config.yaml
    if config_path.exists():
        skipped.append(("config.yaml", config_path))
    else:
        config_path.write_text(_TEMPLATE_CONFIG, encoding="utf-8")
        created.append(("config.yaml", config_path))

    # 输出结果
    content_lines = []
    if created:
        content_lines.append("[bold green]✓ 已生成以下文件:[/bold green]")
        for name, path in created:
            content_lines.append(f"  • [cyan]{name}[/cyan]  [dim]{path}[/dim]")
    if skipped:
        content_lines.append("")
        content_lines.append("[yellow]⚠ 以下文件已存在，跳过:[/yellow]")
        for name, path in skipped:
            content_lines.append(f"  • [cyan]{name}[/cyan]  [dim]{path}[/dim]")

    content_lines.append("")
    content_lines.append("[bold]下一步:[/bold]")
    content_lines.append(f"  1. 编辑 [cyan].env[/cyan] 填入你的 API 密钥")
    content_lines.append(f"  2. 编辑 [cyan]config.yaml[/cyan] 修改模型配置（如需）")
    content_lines.append(f"  3. 运行 [cyan]MythCoder[/cyan] 启动")

    panel = Panel(
        "\n".join(content_lines),
        title="[bold cyan]MythCoder 配置初始化[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


# ============================================================
# 主入口
# ============================================================

def main():
    global _current_agent

    args = parse_args()

    # dashboard 子命令：启动 Token 用量可视化面板
    if getattr(args, "command", None) == "dashboard":
        from dashboard.server import run_dashboard
        run_dashboard(
            port=args.port,
            host=args.host,
            open_browser=not args.no_browser,
            token=args.token,
        )
        return

    # --init: 生成模板配置后退出
    if args.init:
        _generate_template_config()
        sys.exit(0)

    # 初始化
    try:
        agent, callbacks, stream_display = initialize(args)
    except Exception as e:
        print_error(f"初始化失败: {e}")
        sys.exit(1)

    _current_agent = agent

    # 注册 SIGINT 处理器
    signal.signal(signal.SIGINT, _sigint_handler)

    # 创建 Prompt 会话
    history_file = os.path.expanduser("~/.mythcoder_history")
    session = create_session(history_file)

    # 确定恢复 ID
    resume_id = None
    if args.resume:
        resume_id = args.resume
    elif args.continue_conv:
        resume_id = "latest"

    # 运行
    if args.exec_cmd:
        if args.print_mode:
            asyncio.run(run_print_mode(agent, args.exec_cmd, args.output_format, callbacks))
        else:
            asyncio.run(run_single(agent, args.exec_cmd, callbacks))
    else:
        try:
            asyncio.run(run_repl(agent, session, callbacks, resume_id=resume_id))
        except KeyboardInterrupt:
            agent.save_conversation()
            console.print("\n[dim]再见![/dim]")


if __name__ == "__main__":
    main()
