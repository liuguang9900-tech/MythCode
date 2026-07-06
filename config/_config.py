"""
配置解析模块
- 加载 YAML 配置文件
- 支持环境变量替换 ${VAR}
- Pydantic 数据校验
- 命令行参数覆盖
"""

import os
import re
from pathlib import Path
from typing import Optional, Any

import yaml
from pydantic import BaseModel, Field, field_validator


# ============================================================
# Pydantic 配置模型
# ============================================================

class ModelConfig(BaseModel):
    """大模型配置"""
    provider: str = "openai"
    name: str = "gpt-4o"
    api_key: str = ""
    api_base: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=1)
    timeout: int = Field(default=120, ge=1)

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_env(cls, v: str) -> str:
        return _resolve_env_var(v)


class AgentConfig(BaseModel):
    """Agent 核心参数"""
    max_iterations: int = Field(default=30, ge=1, le=200)
    context_window: int = Field(default=128000, ge=4096)
    history_max_turns: int = Field(default=20, ge=1)              # 50→20：减少历史堆积
    summary_threshold: float = Field(default=0.7, ge=0.1, le=1.0)  # 0.8→0.7：更早触发压缩
    workspace_summary: bool = True
    workspace_summary_depth: int = Field(default=1, ge=1, le=3)   # 新增：目录树深度
    workspace_summary_max_items: int = Field(default=30, ge=5)    # 新增：目录树最大项数
    parallel_tool_execution: bool = True
    max_parallel_tools: int = Field(default=5, ge=1, le=20)
    max_tool_result_tokens: int = Field(default=2000, ge=100)     # 4000→2000：减少工具结果占用
    preserve_important_messages: bool = True


class SafetyConfig(BaseModel):
    """安全策略配置"""
    project_root: str = "."
    require_approval: bool = True
    dangerous_commands: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)


class ToolsConfig(BaseModel):
    """工具配置"""
    file_max_size_mb: float = Field(default=10.0, gt=0)
    file_encoding: str = "utf-8"
    command_timeout: int = Field(default=120, ge=1)
    command_max_output: int = Field(default=100000, ge=1)
    search_max_results: int = Field(default=50, ge=1)
    search_respect_gitignore: bool = True


class TimeTravelConfig(BaseModel):
    """时空回溯配置"""
    enabled: bool = True
    max_snapshots: int = Field(default=100, ge=1)
    snapshot_dir: str = ".agent_snapshots"
    auto_snapshot: bool = True


class PersistenceConfig(BaseModel):
    """对话持久化配置"""
    persist_conversation: bool = True
    storage_dir: str = ".mythcoder"


class UIConfig(BaseModel):
    """UI 配置"""
    theme: str = "dark"
    show_tool_calls: bool = True
    show_thinking: bool = False
    syntax_theme: str = "monokai"
    max_output_lines: int = Field(default=500, ge=10)


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) 配置"""
    enabled: bool = True
    config_file: str = ".mcp.json"
    startup_timeout: int = Field(default=30, ge=1)
    tool_call_timeout: int = Field(default=60, ge=1)


class WebConfig(BaseModel):
    """Web 工具配置"""
    enabled: bool = True
    fetch_timeout: int = Field(default=30, ge=1)
    fetch_max_content_tokens: int = Field(default=10000, ge=100)
    search_engine: str = "duckduckgo"
    google_api_key: str = ""
    google_cse_id: str = ""
    bing_api_key: str = ""
    user_agent: str = "MythCoder/0.1"


class CostConfig(BaseModel):
    """费用追踪配置"""
    track_cross_session: bool = True
    daily_budget: float = Field(default=0.0, ge=0.0)
    monthly_budget: float = Field(default=0.0, ge=0.0)
    warning_threshold: float = Field(default=0.8, ge=0.1, le=1.0)


class AppConfig(BaseModel):
    """应用总配置"""
    model: ModelConfig = Field(default_factory=ModelConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    time_travel: TimeTravelConfig = Field(default_factory=TimeTravelConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    cost: CostConfig = Field(default_factory=CostConfig)


# ============================================================
# 环境变量解析
# ============================================================

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_var(value: str) -> str:
    """递归解析字符串中的 ${VAR} 环境变量引用"""
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    # 循环解析直到没有变化（处理嵌套引用）
    prev = None
    while prev != value:
        prev = value
        value = _ENV_VAR_PATTERN.sub(_replace, value)
    return value


def _resolve_env_in_dict(data: dict) -> dict:
    """递归解析字典中所有字符串值的环境变量"""
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = _resolve_env_var(value)
        elif isinstance(value, dict):
            data[key] = _resolve_env_in_dict(value)
        elif isinstance(value, list):
            data[key] = [
                _resolve_env_var(item) if isinstance(item, str) else item
                for item in value
            ]
    return data


# ============================================================
# 配置加载
# ============================================================

def _find_config_path(config_path: Optional[str] = None) -> Path:
    """查找配置文件路径

    查找顺序（优先级从高到低）：
    1. --config 指定的路径
    2. 当前工作目录 ./config.yaml
    3. 用户主目录 ~/.mythcoder/config.yaml
    4. 包内置默认配置 config/config.yaml
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 查找顺序：当前目录 > 用户目录 > 包内置
    search_paths = [
        Path.cwd() / "config.yaml",
        Path.home() / ".mythcoder" / "config.yaml",
        Path(__file__).parent / "config.yaml",
    ]
    for p in search_paths:
        if p.exists():
            return p

    raise FileNotFoundError(
        "未找到 config.yaml。可执行 `MythCoder --init` 在当前目录生成模板配置，"
        "或通过 --config 指定路径。"
    )


def load_config(
    config_path: Optional[str] = None,
    cli_overrides: Optional[dict[str, Any]] = None,
) -> AppConfig:
    """
    加载并解析配置。

    Args:
        config_path: 配置文件路径，为 None 时自动查找
        cli_overrides: 命令行参数覆盖字典，如 {"model.name": "gpt-4"}

    Returns:
        校验后的 AppConfig 实例
    """
    path = _find_config_path(config_path)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    # 解析环境变量
    raw = _resolve_env_in_dict(raw)

    # 命令行参数覆盖（支持点号分隔的嵌套 key）
    if cli_overrides:
        for key, value in cli_overrides.items():
            _set_nested(raw, key.split("."), value)

    return AppConfig(**raw)


def _set_nested(data: dict, keys: list[str], value: Any) -> None:
    """按点号路径设置嵌套字典值"""
    for key in keys[:-1]:
        if key not in data:
            data[key] = {}
        data = data[key]
    data[keys[-1]] = value


# ============================================================
# 全局配置单例
# ============================================================

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置单例（需先调用 load_config 初始化）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def init_config(
    config_path: Optional[str] = None,
    cli_overrides: Optional[dict[str, Any]] = None,
) -> AppConfig:
    """初始化全局配置"""
    global _config
    _config = load_config(config_path, cli_overrides)
    return _config


def reload_config() -> AppConfig:
    """重新加载配置（热重载）"""
    global _config
    _config = load_config()
    return _config
