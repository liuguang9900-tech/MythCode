# Changelog

All notable changes to MythCoder will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — 生产化改造（Phase 1-4）

#### 安全加固
- 修复 `commands/custom.py` 的 `shell=True` 命令注入漏洞，改用 `shlex.split` + `subprocess.run`
- 修复 `agent/hooks.py` 的路径拼接漏洞，改用 `create_subprocess_exec`
- LLM 异常信息脱敏：自动过滤 `api_key`、`Authorization`、`sk-xxx` 等敏感字段
- 引入 `bandit` 安全扫描到 CI 流水线
- 引入 `pip-audit` 依赖漏洞扫描

#### 可靠性提升
- LLM 客户端增加指数退避重试（429/5xx/网络超时，最多 3 次）
- 支持 fallback 模型配置（主模型失败自动切换备用模型）
- MCP 子进程异常隔离，初始化失败不影响主循环

#### 日志系统
- 实现生产级结构化日志系统（JSON 格式，可接入 ELK/Loki）
- 支持 `trace_id` 贯穿请求链路
- 日志文件自动轮转（10MB/文件，保留 10 份）
- 敏感字段自动脱敏
- 默认写入 `~/.mythcoder/logs/mythcoder.log`

#### 并发安全
- `ConversationMemory` 增加 `asyncio.Lock` 保护并发修改
- `ToolRegistry` 增加 `threading.RLock` 保护并发注册
- `CostTracker` 增加文件锁（`fcntl.flock`）防止并发写入冲突
- 原子文件替换（临时文件 + rename）

#### CI/CD
- 新增 GitHub Actions CI 流水线（lint + test + security + build）
- 支持 Python 3.10/3.11/3.12 多版本矩阵测试
- 支持 macOS 和 Ubuntu 双平台测试
- 覆盖率上传 Codecov
- 新增 Release 流水线（tag 触发自动发布 PyPI + GitHub Release）
- 配置 Dependabot 自动依赖更新

#### 代码质量
- 配置 `ruff`（lint + format）
- 配置 `black`（代码格式化）
- 配置 `isort`（import 排序）
- 配置 `mypy`（类型检查）
- 配置 `pre-commit` hooks
- 配置 `coverage` 覆盖率门槛（60%）

#### 部署运维
- 新增 `Dockerfile`（多阶段构建，非 root 用户，健康检查）
- 新增 `docker-compose.yml`（含可选 Ollama 本地模型服务）
- 新增 `Makefile`（install/test/build/release 等常用命令）
- 新增 `systemd` service 模板（安全沙箱，资源限制，自动重启）

#### 打包分发
- 完善 `pyproject.toml` 打包配置
- 支持可选依赖分组（web/notebook/watch/mcp/all/dev）
- 内置默认 `config.yaml` 作为兜底配置
- 新增 `--init` 命令一键生成模板配置
- 配置查找支持 `~/.mythcoder/` 全局配置
- 版本号从 `importlib.metadata` 读取

### Changed
- 启动命令从 `mythcoder` 改为 `MythCoder`
- 首页 UI 重新设计（专业极简风格）
- 配置查找顺序：`--config` → `./config.yaml` → `~/.mythcoder/config.yaml` → 包内置
- `.env` 查找顺序：`./.env` → `~/.mythcoder/.env`

### Deprecated
- `-c/--continue` 参数已废弃，请使用 `-r latest`

## [0.1.0] - 2026-06-15

### Added — 初始版本
- ReAct 自主决策循环
- 13 个内置工具（文件读写、命令执行、代码搜索等）
- 29 个斜杠命令
- MCP 协议支持
- 子代理系统（explore/plan/general-purpose）
- 计划模式
- 技能系统
- 自定义命令
- 时空回溯
- 并行工具调用
- 上下文管理（滑动窗口 + 摘要压缩）
- 费用追踪
- 输出样式
- IDE 集成
- 多模态支持
- Streaming JSON 输出
- 配置热重载
