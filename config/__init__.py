"""
配置包 — 向后兼容的 re-export。
所有原有 `from config import X` 的导入保持不变。
"""

from config._config import (
    # Pydantic 模型
    ModelConfig,
    AgentConfig,
    SafetyConfig,
    ToolsConfig,
    TimeTravelConfig,
    PersistenceConfig,
    UIConfig,
    AppConfig,
    # 函数
    _resolve_env_var,
    _resolve_env_in_dict,
    _find_config_path,
    load_config,
    _set_nested,
    get_config,
    init_config,
    reload_config,
)

from config.settings import SettingsManager

__all__ = [
    "ModelConfig",
    "AgentConfig",
    "SafetyConfig",
    "ToolsConfig",
    "TimeTravelConfig",
    "PersistenceConfig",
    "UIConfig",
    "AppConfig",
    "_resolve_env_var",
    "_resolve_env_in_dict",
    "_find_config_path",
    "load_config",
    "_set_nested",
    "get_config",
    "init_config",
    "reload_config",
    "SettingsManager",
]
