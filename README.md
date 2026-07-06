# MythCoder

> 生产级 AI 编程智能体 — 在终端中运行的自主 Coding Agent

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Beta-yellow.svg)]()
[![Tests](https://img.shields.io/badge/Tests-176%20passed-brightgreen.svg)]()
[![Code Quality](https://img.shields.io/badge/Code%20Quality-ruff%20%2B%20mypy%20%2B%20black-blue.svg)]()
[![Security](https://img.shields.io/badge/Security-bandit%20%2B%20pip--audit-red.svg)]()

MythCoder 是一个运行在终端中的生产级自主 AI 编程智能体，基于 ReAct（Reasoning + Acting）循环实现。它能自主阅读代码、编写修改文件、执行命令、搜索代码库，帮助开发者完成软件工程任务。

## 目录

- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [安装](#安装)
- [打包分发](#打包分发)
- [配置](#配置)
- [使用方法](#使用方法)
- [工具系统](#工具系统)
- [斜杠命令](#斜杠命令)
- [权限系统](#权限系统)
- [MCP 支持](#mcp-支持)
- [子代理](#子代理)
- [计划模式](#计划模式)
- [技能系统](#技能系统)
- [自定义命令](#自定义命令)
- [时空回溯](#时空回溯)
- [会话管理](#会话管理)
- [费用追踪](#费用追踪)
- [输出样式](#输出样式)
- [IDE 集成](#ide-集成)
- [多模态支持](#多模态支持)
- [Streaming JSON 输出](#streaming-json-输出)
- [配置热重载](#配置热重载)
- [生产化特性](#生产化特性)
- [部署运维](#部署运维)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [版本管理](#版本管理)
- [Changelog](#changelog)

---

## 核心特性

- **ReAct 自主决策循环** — LLM 自主推理 → 调用工具 → 观察结果 → 继续推理，直到完成任务
- **13 个内置工具** — 文件读写、命令执行、代码搜索、目录浏览、任务管理、子代理、网页抓取、网络搜索、Notebook 编辑、图片读取
- **29 个斜杠命令** — 涵盖会话管理、代码审查、Git 操作、配置管理、费用追踪等
- **MCP 协议支持** — 通过 Model Context Protocol 动态加载外部工具服务器
- **子代理系统** — 启动独立子 Agent 处理复杂子任务（explore/plan/general-purpose）
- **计划模式** — 先规划再执行，审批通过后自动切换到执行模式
- **技能系统** — 可复用的提示模板，按文件路径自动激活
- **自定义命令** — 用 Markdown 文件定义自己的斜杠命令
- **时空回溯** — 文件快照 + 对话历史双重回滚，支持从任意步骤分叉新会话
- **并行工具调用** — 无依赖的工具调用自动并行执行，加速任务完成
- **多作用域配置** — User / Project / Local 三级配置合并
- **权限引擎** — 5 种权限模式，支持工具特定规则匹配
- **费用追踪** — 跨会话 Token 用量和费用统计，支持日/月预算告警
- **多模态支持** — 读取图片文件，支持视觉模型分析
- **Streaming JSON** — JSON Lines 格式实时输出事件流，便于程序集成
- **配置热重载** — 修改配置文件后自动生效，无需重启
- **IDE 集成** — Unix Socket IPC 桥，支持 VSCode/JetBrains/Cursor

### 生产级能力

- **安全加固** — 命令注入防护、路径穿越拦截、异常信息脱敏、bandit 安全扫描
- **LLM 重试机制** — 指数退避重试（429/5xx/超时）、fallback 模型自动切换
- **结构化日志** — JSON 格式、trace_id 链路追踪、文件轮转、敏感字段脱敏
- **审计日志** — 权限拒绝、危险命令拦截、bypass 模式启用等安全事件记录
- **并发安全** — asyncio.Lock / threading.RLock / fcntl 文件锁全方位保护
- **CI/CD 流水线** — GitHub Actions 多版本矩阵测试、安全扫描、自动发布
- **代码质量** — ruff + black + mypy + isort + pre-commit hooks
- **依赖管理** — 版本锁定、pip-audit 漏洞扫描、Dependabot 自动更新
- **容器化部署** — Dockerfile 多阶段构建、docker-compose、systemd service
- **测试覆盖** — 176 个单元测试，覆盖核心模块

---

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url> MythCoder
cd MythCoder

# 2. 安装依赖
pip install -e .

# 3. 配置 API 密钥
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
echo 'MYTHCODER_API_KEY=sk-your-key-here' > .env

# 4. 启动
python app.py
# 或安装后直接运行
mythcoder
```

启动后进入交互式 REPL，输入自然语言描述你的任务：

```
> 帮我看看这个项目的目录结构
> 重构 src/utils.py 中的 parse_config 函数，增加错误处理
> 运行测试并修复失败的用例
```

---

## 安装

### 系统要求

- Python >= 3.10
- pip / pipenv / poetry（任选）

### 从源码安装

```bash
git clone <repo-url> MythCoder
cd MythCoder
pip install -e .

# 安装开发依赖（可选）
pip install -e ".[dev]"
```

### 运行时依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| litellm | >=1.40.0 | 多模型统一调用 |
| openai | >=1.30.0 | OpenAI 兼容 API |
| tiktoken | >=0.7.0 | Token 计数 |
| rich | >=13.7.0 | 终端 UI 渲染 |
| prompt-toolkit | >=3.0.43 | 交互式输入 |
| pygments | >=2.17.0 | 代码高亮 |
| pyyaml | >=6.0 | YAML 配置解析 |
| pydantic | >=2.5.0 | 配置模型验证 |
| pathspec | >=0.12.0 | .gitignore 匹配 |
| colorama | >=0.4.6 | 终端颜色（Windows） |

### 可选依赖

MythCoder 支持按需安装可选功能，避免不必要的依赖：

| 分组 | 包含 | 用途 |
|------|------|------|
| `[web]` | httpx, beautifulsoup4, lxml | 网页抓取与搜索（web_fetch / web_search） |
| `[notebook]` | nbformat | Jupyter Notebook 编辑 |
| `[watch]` | watchdog | 文件监听（配置热重载） |
| `[mcp]` | httpx | MCP 协议 SSE 传输 |
| `[all]` | 以上全部 | 全部可选功能一次性安装 |
| `[dev]` | pytest, build, twine | 开发测试与打包发布 |

```bash
# 仅安装 Web 工具依赖
pip install -e ".[web]"

# 安装全部可选功能
pip install -e ".[all]"

# 开发者安装（含测试与打包工具）
pip install -e ".[dev]"
```

---

## 打包分发

MythCoder 已配置完整的 Python 包打包方案，无需向他人分发源码，可直接生成 wheel 包或发布到 PyPI。

### 构建分发包

#### 1. 安装构建工具

```bash
pip install build twine
```

#### 2. 生成分发包

在项目根目录执行：

```bash
python3 -m build
```

构建完成后，`dist/` 目录会生成两个文件：

| 文件 | 类型 | 大小 | 说明 |
|------|------|------|------|
| `mythcoder-0.1.0-py3-none-any.whl` | wheel | ~170K | **推荐分发**，预编译二进制包 |
| `mythcoder-0.1.0.tar.gz` | sdist | ~160K | 源码包，兼容性更好 |

#### 3. 分发给他人

**方式一：直接发送 wheel 文件**

把 `dist/mythcoder-0.1.0-py3-none-any.whl` 发给他人，对方执行：

```bash
pip install mythcoder-0.1.0-py3-none-any.whl

# 如需 Web/Notebook 等可选功能
pip install mythcoder-0.1.0-py3-none-any.whl[all]

# 启动
MythCoder
```

**方式二：通过内网 PyPI / 私有源**

```bash
# 上传到私有源
twine upload --repository-url https://your-pypi-server/ dist/*

# 其他人安装
pip install --index-url https://your-pypi-server/ mythcoder
```

**方式三：发布到官方 PyPI**

```bash
twine upload dist/*
```

发布后任何人都可以直接安装：

```bash
pip install mythcoder
```

### 验证安装

```bash
MythCoder --version      # 应输出 MythCoder v0.1.0
MythCoder --help         # 查看帮助
MythCoder                # 启动交互式 REPL
```

### 打包配置说明

打包配置位于 `pyproject.toml`，关键配置项：

```toml
[project]
name = "mythcoder"           # PyPI 包名
version = "0.1.0"            # 版本号

[project.scripts]
MythCoder = "app:main"       # 安装后生成的命令行入口

[tool.setuptools.packages.find]
include = [                   # 打包的 Python 模块
    "agent*", "tools*", "llm*",
    "ui*", "utils*", "commands*",
    "config*", "mcp*", "ide*",
]

[tool.setuptools.package-data]
config = ["config.yaml"]      # 打包内置默认配置文件
```

### 版本号管理

版本号在 `pyproject.toml` 中统一维护。运行时通过 `importlib.metadata` 读取已安装包的版本：

```python
from importlib.metadata import version
print(version("mythcoder"))  # 0.1.0
```

发版流程：

1. 修改 `pyproject.toml` 中的 `version` 字段
2. 更新 `CHANGELOG.md`（如有）
3. 执行 `python3 -m build` 重新打包
4. 执行 `twine upload dist/*` 发布

### 清理构建产物

```bash
rm -rf dist/ build/ *.egg-info/
```

---

## 配置

### 配置文件

MythCoder 使用多层级配置，优先级从低到高：

1. **代码默认值**（`config/_config.py`）
2. **配置文件**（`config.yaml`，可通过 `--config` 指定路径）
3. **CLI 参数**（`--model`、`--max-turns` 等）
4. **`--settings` 内联 JSON**（最高优先级）

### 快速初始化配置（推荐）

通过 `pip install` 安装后，执行以下命令在当前目录生成模板配置：

```bash
MythCoder --init
```

会在当前目录生成两个文件：

| 文件 | 用途 |
|------|------|
| `.env` | 存放 API 密钥等敏感信息（**请勿提交到 Git**） |
| `config.yaml` | 模型与 Agent 参数配置 |

生成后按提示编辑即可：

```bash
# 1. 编辑 .env，填入你的 API 密钥
vim .env

# 2. 按需修改 config.yaml 中的模型配置
vim config.yaml

# 3. 启动
MythCoder
```

### 配置文件查找顺序

MythCoder 按以下顺序查找配置文件（找到即停止）：

1. `--config` 参数指定的路径
2. **当前工作目录** `./config.yaml`（项目级配置）
3. **用户主目录** `~/.mythcoder/config.yaml`（全局配置）
4. **包内置默认配置**（随 pip 安装，作为兜底）

`.env` 文件按同样的顺序查找：`./.env` → `~/.mythcoder/.env`。

> **场景说明**：
> - **单项目使用**：在项目根目录执行 `MythCoder --init`，配置跟随项目走
> - **全局通用**：在 `~/.mythcoder/` 下放置配置，所有目录共享同一套配置
> - **多模型切换**：不同项目目录放不同 `config.yaml`，进入对应目录启动即可

### 环境变量

在 `.env` 文件中配置（`MythCoder --init` 会自动生成模板）：

```bash
# DeepSeek API Key（必填）
MYTHCODER_API_KEY=sk-your-deepseek-api-key

# 可选：其他模型供应商
# OPENAI_API_KEY=sk-your-openai-api-key
# ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
# ZHIPU_API_KEY=your-zhipu-api-key
```

`.env` 文件在程序启动时自动加载，不会覆盖已存在的环境变量。

### 切换模型

**方式一：修改 config.yaml**（永久生效）

```yaml
model:
  provider: "openai"
  name: "gpt-4o"                          # 改成你想用的模型
  api_key: "${OPENAI_API_KEY}"            # 对应 .env 中的密钥变量名
  api_base: "https://api.openai.com/v1"   # 对应供应商的 API 地址
```

**方式二：命令行参数**（临时覆盖）

```bash
MythCoder --model gpt-4o
MythCoder --model claude-3-5-sonnet
```

**方式三：环境变量**（适合 CI/CD）

```bash
export MYTHCODER_API_KEY=sk-xxx
export MYTHCODER_MODEL=gpt-4o
MythCoder
```

### 常见模型配置示例

<details>
<summary>DeepSeek（默认）</summary>

```yaml
model:
  provider: "openai"
  name: "deepseek-v4-pro"
  api_key: "${MYTHCODER_API_KEY}"
  api_base: "https://api.deepseek.com/v1"
```
</details>

<details>
<summary>OpenAI GPT-4o</summary>

```yaml
model:
  provider: "openai"
  name: "gpt-4o"
  api_key: "${OPENAI_API_KEY}"
  api_base: "https://api.openai.com/v1"
```
</details>

<details>
<summary>通义千问（阿里云）</summary>

```yaml
model:
  provider: "openai"
  name: "qwen-max"
  api_key: "${DASHSCOPE_API_KEY}"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```
</details>

<details>
<summary>智谱 GLM-4</summary>

```yaml
model:
  provider: "openai"
  name: "glm-4-plus"
  api_key: "${ZHIPU_API_KEY}"
  api_base: "https://open.bigmodel.cn/api/paas/v4"
```
</details>

<details>
<summary>本地模型（Ollama）</summary>

```yaml
model:
  provider: "openai"
  name: "llama3:70b"
  api_key: "ollama"                       # Ollama 不需要真实密钥
  api_base: "http://localhost:11434/v1"
```
</details>

### config.yaml 完整配置

```yaml
# 大模型配置
model:
  provider: "openai"                    # 供应商（openai/anthropic/deepseek 等）
  name: "deepseek-v4-pro"              # 模型名称
  api_key: "${MYTHCODER_API_KEY}"      # 从环境变量读取
  api_base: "https://api.deepseek.com/v1"
  temperature: 0.2
  max_tokens: 8192
  timeout: 120

# Agent 核心参数
agent:
  max_iterations: 30                    # ReAct 循环最大迭代次数
  context_window: 128000                # 上下文窗口大小
  history_max_turns: 20                 # 保留的最大对话轮数
  summary_threshold: 0.7                # 触发摘要压缩的比例
  workspace_summary: true               # 注入工作区文件树摘要
  workspace_summary_depth: 1            # 目录树深度
  workspace_summary_max_items: 30       # 目录树最大项数
  max_tool_result_tokens: 2000          # 工具结果最大 token
  preserve_important_messages: true     # 压缩时保留重要消息
  parallel_tool_execution: true         # 并行工具执行
  max_parallel_tools: 5                 # 最大并行数

# 安全策略
safety:
  project_root: "."
  require_approval: true
  dangerous_commands:                   # 危险命令正则
    - "rm\\s+(-rf?\\s+)?/"
    - "sudo\\s+rm"
    - "git\\s+push\\s+--force"
    # ...
  protected_paths:                      # 禁止修改的路径
    - "~/.ssh"
    - "~/.aws"
    - "/etc/passwd"
  allowed_commands:                     # 白名单命令
    - "ls"
    - "cat"
    - "git\\s+status"
    # ...

# 工具配置
tools:
  file_max_size_mb: 10
  file_encoding: "utf-8"
  command_timeout: 120
  command_max_output: 100000
  search_max_results: 50
  search_respect_gitignore: true

# 时空回溯
time_travel:
  enabled: true
  max_snapshots: 100
  snapshot_dir: ".agent_snapshots"
  auto_snapshot: true

# 对话持久化
persistence:
  persist_conversation: true
  storage_dir: ".mythcoder"

# UI 配置
ui:
  theme: "dark"
  show_tool_calls: true
  show_thinking: false
  syntax_theme: "monokai"
  max_output_lines: 500

# MCP 配置
mcp:
  enabled: true
  config_file: ".mcp.json"
  startup_timeout: 30
  tool_call_timeout: 60

# Web 工具配置
web:
  enabled: true
  fetch_timeout: 30
  fetch_max_content_tokens: 10000
  search_engine: "duckduckgo"           # duckduckgo / google / bing
  user_agent: "MythCoder/0.1"

# 费用追踪
cost:
  track_cross_session: true
  daily_budget: 0.0                     # 日预算（美元），0=不限制
  monthly_budget: 0.0                   # 月预算
  warning_threshold: 0.8                # 预算告警阈值
```

### 多作用域设置

除了 `config.yaml`，还支持 JSON 格式的多作用域设置文件：

| 作用域 | 路径 | 说明 |
|--------|------|------|
| User | `~/.mythcoder/settings.json` | 用户级，所有项目共享 |
| Project | `.mythcoder/settings.json` | 项目级，可提交到 Git |
| Local | `.mythcoder/settings.local.json` | 本地级，不提交到 Git |

合并策略：数组合并（拼接去重）、对象深度合并、标量覆盖。

```json
{
  "permissions": {
    "allow": ["read_file", "Bash(git status)", "Edit(src/**/*.py)"],
    "deny": ["Bash(rm -rf:*)", "Edit(.env)"],
    "ask": ["execute_command", "write_file"]
  },
  "hooks": {
    "PreToolUse": [{"matcher": "write_file", "command": "python3 lint.py", "timeout": 10}],
    "PostToolUse": [{"matcher": "edit_file", "command": "python3 format.py"}]
  }
}
```

---

## 使用方法

### 交互式 REPL（默认）

```bash
mythcoder                          # 全新对话
mythcoder -r latest                # 恢复上次对话
mythcoder -r <session-id>          # 恢复指定会话
mythcoder --name "重构任务"         # 命名会话
mythcoder --workspace /path/to/project  # 指定工作目录
mythcoder --model gpt-4o           # 指定模型
```

### 单次执行模式

```bash
mythcoder -x "帮我重构这个函数"
mythcoder -x "运行测试" --max-turns 10
```

### 非交互输出模式

适用于 CI/CD 或程序集成：

```bash
# 纯文本输出
mythcoder -x "列出所有 TODO" -p --output-format text

# JSON 格式输出
mythcoder -x "分析项目结构" -p --output-format json

# Streaming JSON Lines（实时事件流）
mythcoder -x "修复 bug" -p --output-format stream-json
```

### CLI 参数完整列表

| 参数 | 短选项 | 默认值 | 说明 |
|------|--------|--------|------|
| `--version` | `-V` | — | 显示版本号 |
| `--workspace` | `-w` | `.` | 工作目录 |
| `--model` | `-m` | 配置文件值 | 模型名称 |
| `--config` | — | `config.yaml` | 配置文件路径 |
| `--resume` | `-r` | — | 恢复会话（`latest` 或 session-id） |
| `--exec` | `-x` | — | 单次执行模式 |
| `--name` | `-n` | — | 会话名称 |
| `--print` | `-p` | `false` | 非交互输出模式 |
| `--output-format` | — | `text` | 输出格式：text/json/stream-json |
| `--max-turns` | — | 配置文件值 | 最大推理迭代次数 |
| `--debug` | — | — | 调试模式：all 或 llm,tools,agent |
| `--add-dir` | — | — | 额外工作目录（可多次指定） |
| `--safe-mode` | — | `false` | 安全模式（禁用 CLAUDE.md/hooks/skills） |
| `--permission-mode` | — | `default` | 权限模式 |
| `--settings` | — | — | JSON 设置文件或内联 JSON |
| `--no-approval` | — | `false` | 跳过所有确认（不推荐） |
| `--verbose` | `-v` | `false` | 详细日志 |

### 权限模式

| 模式 | 说明 |
|------|------|
| `default` | 正常询问，写操作需确认 |
| `acceptEdits` | 自动批准文件编辑，安全命令自动执行 |
| `plan` | 只读模式，拒绝所有写操作 |
| `auto` | 自动批准所有操作 |
| `bypassPermissions` | 跳过所有权限检查 |

```bash
mythcoder --permission-mode acceptEdits
mythcoder --permission-mode plan -x "分析这个项目的架构"
```

---

## 工具系统

MythCoder 内置 13 个工具，采用按需加载机制：首轮仅加载 7 个核心工具以节省 Token，扩展工具在 LLM 调用时自动激活。

### 核心工具（始终加载）

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容，返回带行号格式，支持 offset/limit 分段读取 |
| `write_file` | 创建新文件或完全覆盖已有文件，自动创建父目录 |
| `edit_file` | 精确字符串替换编辑，old_string 须唯一匹配 |
| `execute_command` | 执行 shell 命令（非交互式，超时 120s） |
| `glob` | 按 glob 模式查找文件路径，支持 `**` 递归匹配 |
| `search_code` | 在代码中搜索文本或正则，返回匹配文件和行内容 |
| `list_directory` | 以 tree 风格列出目录结构 |

### 扩展工具（按需加载）

| 工具 | 说明 |
|------|------|
| `todo_write` | 替换式更新任务清单（pending/in_progress/completed） |
| `task` | 启动子代理处理独立子任务（explore/plan/general-purpose） |
| `web_fetch` | 抓取 URL 网页内容，可选按 prompt 用 LLM 处理 |
| `web_search` | 在互联网上搜索信息，返回结构化结果 |
| `notebook_edit` | 编辑 Jupyter Notebook 单元格（替换/插入/删除） |
| `read_image` | 读取图片文件返回 base64，供多模态 LLM 查看 |

### 工具按需加载

为减少 Token 消耗，首轮对话仅向 LLM 提供 7 个核心工具的 Schema（节省 77% Token）。当 LLM 尝试调用扩展工具时，自动激活该工具并在后续轮次中可用。系统 Prompt 中会提示扩展工具的存在。

---

## 斜杠命令

在交互式 REPL 中输入 `/` 开头的命令：

### 会话管理

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/exit` | 退出程序 |
| `/status` | 显示当前会话状态 |
| `/sessions` | 列出所有会话 |
| `/switch <id>` | 切换到指定会话 |
| `/fork <step_id> <name>` | 从指定步骤创建新会话分支 |
| `/rewind` | 时空回溯：回滚到历史步骤 |
| `/compact` | 压缩对话上下文，释放 Token 空间 |

### 配置管理

| 命令 | 说明 |
|------|------|
| `/config` | 显示当前配置 |
| `/model [name]` | 查看或切换模型 |
| `/tools` | 列出可用工具 |
| `/permissions` | 管理权限规则 |
| `/memory` | 查看自动记忆 |
| `/add-dir <path>` | 运行时添加额外工作目录 |
| `/style [name]` | 切换输出样式（default/compact/verbose/minimal） |

### 代码与 Git

| 命令 | 说明 |
|------|------|
| `/review` | 代码审查：分析 git diff 并提供审查意见 |
| `/security-review` | 安全审查：检查代码中的安全漏洞 |
| `/commit [--amend\|--fixup <hash>]` | 自动生成 commit message 并提交 |
| `/pr [--create] [--base <branch>]` | 生成或创建 Pull Request |
| `/branch [list\|create\|switch\|delete]` | Git 分支管理 |
| `/merge <source> [--ff\|abort\|status\|resolve]` | Git 合并，支持冲突解决 |
| `/bug` | 收集上下文并生成 bug 报告 |

### 计划与技能

| 命令 | 说明 |
|------|------|
| `/plan [new\|approve\|reject\|list\|show\|execute]` | 计划管理 |
| `/skill [list\|activate\|deactivate]` | 技能管理 |

### 其他

| 命令 | 说明 |
|------|------|
| `/init` | 分析项目并生成 CLAUDE.md 上下文文件 |
| `/doctor` | 诊断系统配置和连接状态 |
| `/cost [total\|today\|month\|sessions\|budget]` | Token 用量和费用统计 |
| `/upgrade` | 检查 MythCoder 更新 |
| `/ide` | 显示 IDE 集成状态 |

---

## 权限系统

### 权限模式

通过 `--permission-mode` 或 `/permissions` 命令设置：

```
default          → 写操作需确认，安全命令自动执行
acceptEdits      → 自动批准文件编辑
plan             → 只读模式，所有写操作被拒绝
auto             → 自动批准所有操作
bypassPermissions → 跳过所有权限检查
```

### 规则配置

在 `settings.json` 中配置工具特定规则：

```json
{
  "permissions": {
    "allow": [
      "read_file",
      "Bash(git status)",
      "Bash(git diff:*)",
      "Edit(src/**/*.py)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Edit(.env)",
      "Edit(**/secrets.*)"
    ],
    "ask": [
      "execute_command",
      "write_file"
    ]
  }
}
```

规则格式：`ToolName` 或 `ToolName(arg_pattern)`

- `Bash(git push:*)` — 匹配 git push 开头的命令
- `Edit(src/**/*.py)` — 匹配 src 目录下的 Python 文件编辑
- `WebFetch(domain:github.com)` — 匹配特定域名的网页抓取

### 会话级"总是允许"

在工具确认提示时输入 `a`，后续相同类型的操作将自动批准：

```
> [y] 执行 / [n] 取消 / [a] 总是允许 > a
已记住：后续相同类型的操作将自动批准
```

---

## MCP 支持

MythCoder 支持 [Model Context Protocol](https://modelcontextprotocol.io/)，可以动态加载外部工具服务器。

### 配置

在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token"
      }
    }
  }
}
```

### 支持的传输方式

- **stdio** — 通过子进程 stdin/stdout 通信（默认）
- **SSE** — 通过 HTTP Server-Sent Events 通信

### 工具命名空间

MCP 工具注册后命名为 `mcp__<server>__<tool>`，例如 `mcp__filesystem__read_file`。

---

## 子代理

通过 `task` 工具启动子代理处理独立子任务。子代理拥有独立的上下文窗口，不影响主对话。

### 子代理类型

| 类型 | 说明 | 权限 |
|------|------|------|
| `explore` | 只读探索，适合代码分析、架构理解 | PLAN 模式（只读） |
| `plan` | 方案设计，适合制定实现计划 | PLAN 模式（只读） |
| `general-purpose` | 通用任务，可使用所有工具 | AUTO 模式 |

### 使用示例

子代理由 LLM 自动调用，你也可以在对话中引导：

```
> 请用子代理探索一下 src/ 目录的架构，然后给我一个重构方案
```

LLM 会自动启动 `explore` 类型子代理进行代码分析，然后基于结果制定方案。

### 递归深度限制

子代理最多递归 2 层（子代理可以再启动子代理，但不超过 2 层）。

---

## 计划模式

Plan Mode 让 AI 先规划再执行，适合复杂任务。

### 工作流程

1. 切换到 plan 模式：`/permissions plan` 或 `--permission-mode plan`
2. 输入任务描述，AI 生成计划文档（不执行任何写操作）
3. 审批计划：`/plan approve`
4. 自动切换到 acceptEdits 模式执行计划
5. 查看进度：`/plan show`

### 计划文件

计划存储在 `.mythcoder/plans/<plan_id>.md`，格式为 YAML frontmatter + Markdown：

```markdown
---
id: plan_abc123
status: approved
created_at: 2024-01-01T00:00:00
steps:
  - id: 1
    description: 读取配置文件
    status: completed
  - id: 2
    description: 修改解析逻辑
    status: pending
---

# 重构计划

## 步骤 1：读取配置文件
...

## 步骤 2：修改解析逻辑
...
```

---

## 技能系统

技能是可复用的提示模板，可以按文件路径自动激活。

### 技能文件格式

在 `.claude/skills/` 或 `~/.mythcoder/skills/` 目录下创建 `.md` 文件：

```markdown
---
name: python-testing
description: Python 测试专家
paths: ["**/test_*.py", "**/conftest.py"]
auto_activate: true
---

你是 Python 测试专家。在编写测试时遵循以下原则：
- 使用 pytest 框架
- 遵循 AAA 模式（Arrange-Act-Assert）
- 每个测试函数只测试一个行为
- 使用 fixtures 管理测试数据
```

### 自动激活

当 LLM 调用工具操作的文件路径匹配技能的 `paths` 模式时，技能自动激活，其内容注入到系统 Prompt 中。

### 手动管理

```
/skill list              # 列出所有技能
/skill activate <name>   # 手动激活技能
/skill deactivate <name> # 停用技能
```

---

## 自定义命令

用 Markdown 文件定义自己的斜杠命令。

### 命令文件格式

在 `.claude/commands/` 或 `~/.mythcoder/commands/` 目录下创建 `.md` 文件：

```markdown
---
description: 生成 API 文档
aliases: [doc, docs]
arguments: "[module] 要生成文档的模块名"
---

请为模块 $ARGUMENTS 生成 API 文档：

1. 读取模块所有公开函数和类
2. 为每个函数生成 docstring
3. 创建 docs/$1.md 文档文件

参考项目的文档风格：`!cat docs/style.md`
```

### 占位符

| 占位符 | 说明 |
|--------|------|
| `$ARGUMENTS` | 命令后的所有参数 |
| `$1`, `$2` ... | 按位置的第 N 个参数 |
| `` `!command` `` | 执行 shell 命令并注入结果 |

### 使用

```
/gen-docs src/utils
# 等同于让 AI 执行 gen-docs.md 中的提示，$ARGUMENTS = "src/utils"
```

---

## 时空回溯

MythCoder 提供文件和对话的双重回滚能力。

### 文件快照

- 写操作前自动创建文件快照（存储在 `.agent_snapshots/`）
- 最多保留 100 个快照，超出后清理最旧的
- 可通过 `/rewind` 回滚到任意历史步骤

### 对话回溯

```
/rewind              # 显示可回溯的步骤列表
/rewind <step_id>    # 回溯到指定步骤
```

回溯后：
- 文件恢复到该步骤结束时的状态
- 对话历史截断到该步骤
- 后续步骤的快照保留（可以再次前进）

### 会话分叉

```
/fork <step_id> "实验性重构"  # 从指定步骤创建新会话分支
```

分叉后：
- 原会话保持不变
- 新会话继承分叉点的文件状态和对话历史
- 可以在两个会话间切换：`/switch <session_id>`

---

## 会话管理

### 会话存储

会话存储在 `.mythcoder/conversations/<session_id>.json`，包含：
- 完整对话历史
- 工具调用记录
- 文件修改记录
- 快照引用

### 会话操作

```
/sessions              # 列出所有会话
/switch <session_id>   # 切换会话
/clear                 # 清空当前对话历史
```

### 恢复会话

```bash
mythcoder -r latest              # 恢复最近的会话
mythcoder -r <session_id>        # 恢复指定会话
mythcoder -c                     # 同 -r latest（兼容旧参数）
```

---

## 费用追踪

### 跨会话费用统计

费用数据存储在 `~/.mythcoder/costs.json`，跨所有项目共享。

```
/cost              # 显示当前会话费用 + 跨会话累计
/cost total        # 跨会话总计
/cost today        # 今日费用
/cost month        # 本月费用
/cost sessions     # 列出最近 10 个会话的费用
/cost budget       # 预算使用情况
```

### 预算告警

在 `config.yaml` 中设置预算：

```yaml
cost:
  track_cross_session: true
  daily_budget: 1.0        # 日预算 1 美元
  monthly_budget: 20.0     # 月预算 20 美元
  warning_threshold: 0.8   # 80% 时告警
```

当费用达到预算的 80% 时显示警告，达到 100% 时显示错误提示。

### 支持的模型价格

内置常见模型的价格（每百万 Token）：

| 模型 | 输入 | 输出 |
|------|------|------|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| claude-3-5-sonnet | $3.00 | $15.00 |
| deepseek-chat | $0.14 | $0.28 |
| glm-4 | $0.50 | $0.50 |

---

## 输出样式

通过 `/style` 命令切换输出样式：

| 样式 | 说明 |
|------|------|
| `default` | 默认样式，显示工具调用和结果摘要 |
| `compact` | 紧凑样式，最少输出 |
| `verbose` | 详细样式，完整输出工具参数和结果 |
| `minimal` | 极简样式，仅显示必要信息 |

```
/style              # 列出所有样式
/style compact      # 切换到紧凑样式
/style verbose      # 切换到详细样式
```

### 自定义样式

在 `.claude/styles/` 目录下创建 JSON 样式文件：

```json
{
  "name": "my-style",
  "description": "自定义样式",
  "tool_call_format": "→ {tool_name}({args_preview})",
  "tool_result_format": "✓ {result_preview}",
  "show_tool_args": true,
  "show_tool_result": true,
  "truncate_tool_args": 80,
  "truncate_tool_result": 200,
  "color": {
    "tool_call": "cyan",
    "tool_result": "green",
    "tool_error": "red"
  }
}
```

---

## IDE 集成

MythCoder 通过 Unix Socket IPC 与 IDE 通信，支持文件跳转、差异展示等。

### 支持的 IDE

- VSCode / Cursor（通过 `VSCODE_PID` 环境变量检测）
- JetBrains IDE（通过 `JETBRAINS_IDE` 环境变量检测）

### 使用

```
/ide                # 显示 IDE 连接状态
```

当 IDE 连接时，文件编辑操作会自动在 IDE 中打开差异视图。

---

## 多模态支持

MythCoder 支持多模态 LLM（如 GPT-4o、Claude 3.5 Sonnet）的视觉能力。

### 读取图片

使用 `read_image` 工具读取图片文件，返回 base64 编码供 LLM 分析：

```
> 帮我看看 /tmp/screenshot.png 这个截图里的错误信息
```

LLM 会自动调用 `read_image` 读取图片，然后基于图片内容进行分析。

### 支持的图片格式

PNG、JPEG、GIF、WebP、BMP（最大 20MB）

### 图片缩放

通过 `max_size` 参数控制图片大小，超过最大边长会等比缩放：

```
read_image(file_path="screenshot.png", max_size=1024)
```

---

## Streaming JSON 输出

`stream-json` 输出模式以 JSON Lines 格式实时输出事件流，便于程序集成。

### 使用

```bash
mythcoder -x "分析项目" -p --output-format stream-json
```

### 事件类型

每行一个 JSON 对象，`type` 字段标识事件类型：

```json
{"type": "text_delta", "content": "正在分析"}
{"type": "tool_call", "name": "list_directory", "args": {"path": "."}}
{"type": "tool_result", "name": "list_directory", "success": true, "output": "...", "metadata": {}}
{"type": "thinking", "content": "需要进一步查看..."}
{"type": "compression", "info": {"tokens_saved": 500, "old_message_count": 10, "new_message_count": 4}}
{"type": "result", "response": "项目分析完成...", "stats": {"steps": 5, "prompt_tokens": 3000, "completion_tokens": 1500}}
{"type": "error", "error": "错误描述"}
```

### 程序集成示例

```python
import subprocess
import json

proc = subprocess.Popen(
    ["mythcoder", "-x", "修复 bug", "-p", "--output-format", "stream-json"],
    stdout=subprocess.PIPE, text=True
)

for line in proc.stdout:
    event = json.loads(line)
    if event["type"] == "text_delta":
        print(event["content"], end="", flush=True)
    elif event["type"] == "result":
        print(f"\n完成! 消耗 {event['stats']['total_tokens']} tokens")
```

---

## 配置热重载

MythCoder 监听配置文件变化，修改后自动生效，无需重启。

### 监听的文件

| 文件 | 重载行为 |
|------|----------|
| `config.yaml` | 重新加载配置，同步到各组件 |
| `.mythcoder/settings.json` | 重新加载权限规则和钩子 |
| `.mythcoder/settings.local.json` | 同上 |
| `CLAUDE.md` | 清除缓存，下次构建 Prompt 时重新加载 |
| `.claude/rules/*.md` | 重新加载项目规则 |
| `.claude/skills/*.md` | 重新加载技能 |
| `.claude/styles/*.json` | 重新加载输出样式 |
| `.claude/commands/*.md` | 重新加载自定义命令 |

---

## 生产化特性

### 安全加固

#### 命令注入防护

所有命令执行均使用 `shlex.split` + `subprocess.run`（列表参数），禁止 `shell=True`：

```python
# ✅ 安全：列表参数
args = shlex.split(cmd_str)
proc = subprocess.run(args, capture_output=True, timeout=10)

# ❌ 禁止：shell=True
proc = subprocess.run(cmd_str, shell=True)  # 代码中已移除
```

涉及文件：`commands/custom.py`、`agent/hooks.py`

#### 路径穿越拦截

沙箱模块阻止所有路径穿越攻击：

```python
# tools/sandbox.py
def resolve_path(self, path: str) -> Path:
    p = Path(path).resolve()
    for root in self.all_roots:
        try:
            p.relative_to(root)  # 必须在允许的 root 内
            return p
        except ValueError:
            continue
    raise PermissionError(f"安全限制：路径不在允许的目录内")
```

#### 异常信息脱敏

LLM 异常信息自动过滤敏感字段，防止 API Key 泄露：

```python
# llm/client.py
def _sanitize_error(error: Exception) -> str:
    msg = str(error)
    msg = re.sub(r"api_key[=:]\s*['\"]?[^\s'\"]+['\"]?", "api_key=***", msg)
    msg = re.sub(r"sk-[a-zA-Z0-9]{20,}", "sk-***", msg)
    msg = re.sub(r"authorization[=:]\s*['\"]?bearer\s+[^\s'\"]+['\"]?", "authorization=***", msg)
    return msg
```

#### 安全扫描

CI 流水线集成 `bandit`（SAST 静态扫描）和 `pip-audit`（依赖漏洞扫描）：

```bash
make security    # 本地运行安全扫描
```

### LLM 重试机制

支持指数退避重试和 fallback 模型自动切换：

```python
# llm/client.py
client = LLMClient(config)

# 设置 fallback 模型（主模型失败时切换）
fallback = ModelConfig(provider="anthropic", name="claude-3-5-sonnet", ...)
client.set_fallback(fallback)

# 重试策略：
# - 429 Too Many Requests → 重试
# - 5xx Server Error → 重试
# - 网络超时 → 重试
# - 认证错误 → 不重试，直接切换 fallback
# - 最多重试 3 次，指数退避（1s → 2s → 4s）
```

### 结构化日志

生产级 JSON 结构化日志，可接入 ELK/Loki/Datadog：

```python
from utils.logger import get_logger, set_trace_id

logger = get_logger("agent")
set_trace_id("req-abc123")  # 贯穿请求链路

logger.info("LLM 调用完成", extra={"model": "gpt-4o", "tokens": 1500})
```

日志输出格式（JSON Lines）：

```json
{"timestamp": "2026-06-22T10:30:00Z", "level": "INFO", "logger": "agent", "message": "LLM 调用完成", "trace_id": "req-abc123", "model": "gpt-4o", "tokens": 1500}
```

日志文件自动轮转：
- 路径：`~/.mythcoder/logs/mythcoder.log`
- 单文件上限：10MB
- 保留份数：10 份
- 格式：JSON Lines（文件）/ 彩色文本（控制台）

### 审计日志

独立审计日志文件，记录所有安全相关事件：

```python
from utils.audit import audit_logger

# 自动记录的事件：
# - PERMISSION_DENIED：权限拒绝
# - DANGEROUS_COMMAND_BLOCKED：危险命令拦截
# - BYPASS_MODE_ENABLED：bypass 模式启用
# - PROTECTED_PATH_ACCESS：受保护路径访问
# - CONFIG_CHANGED：配置变更
# - TOOL_EXECUTED：工具执行记录
```

审计日志路径：`~/.mythcoder/audit.log`（5MB 轮转，保留 20 份）

### 并发安全

全方位锁保护，防止并发竞态条件：

| 组件 | 锁类型 | 保护对象 |
|------|--------|----------|
| `ConversationMemory` | `asyncio.Lock` | messages 列表 |
| `ToolRegistry` | `threading.RLock` | _tools 字典 |
| `CostTracker` | `fcntl.flock` | costs.json 文件 |
| `AgentLoop` | `asyncio.Lock` | _current_tool_calls 等共享状态 |
| `MCPClient` | `asyncio.Lock` | stdin 写入 |

### 代码质量工具

项目配置了完整的代码质量工具链：

```bash
make lint        # ruff 代码检查
make format      # black + isort 格式化
make type-check  # mypy 类型检查
```

配置文件：`pyproject.toml` 中的 `[tool.ruff]`、`[tool.black]`、`[tool.isort]`、`[tool.mypy]` 章节

Pre-commit hooks（`.pre-commit-config.yaml`）：
- ruff（lint + format）
- black（代码格式化）
- isort（import 排序）
- mypy（类型检查）
- bandit（安全扫描）
- 基础检查（尾随空格、YAML 校验、大文件检测等）

```bash
# 安装 pre-commit hooks
pip install pre-commit
pre-commit install

# 手动运行
pre-commit run --all-files
```

### CI/CD 流水线

GitHub Actions 自动化流水线（`.github/workflows/`）：

#### CI 流水线（`ci.yml`）

| Job | 说明 |
|-----|------|
| `lint` | ruff + black + isort + mypy 代码质量检查 |
| `security` | bandit SAST 扫描 + pip-audit 依赖漏洞扫描 |
| `test` | Python 3.10/3.11/3.12 × Ubuntu/macOS 矩阵测试 |
| `build` | 构建 wheel + sdist，twine check 校验 |

触发条件：push 到 main/develop 分支，或 PR

#### Release 流水线（`release.yml`）

- 触发条件：推送 `v*` tag
- 自动构建并发布到 PyPI
- 自动创建 GitHub Release（含 changelog）

```bash
# 发布新版本
make release VERSION=0.2.0
```

#### Dependabot

自动依赖更新 PR（`.github/dependabot.yml`）：
- Python 依赖：每周检查
- GitHub Actions 版本：每周检查

### 测试覆盖

```bash
make test        # 运行测试
make test-cov    # 运行测试并生成覆盖率报告
```

当前测试覆盖：

| 测试文件 | 覆盖模块 | 测试数 |
|----------|----------|--------|
| `test_llm_client.py` | LLM 重试、脱敏、fallback | 15 |
| `test_registry.py` | 工具注册、并发安全、分组加载 | 16 |
| `test_security.py` | 沙箱、命令注入防护、脱敏 | 12 |
| `test_logging.py` | 结构化日志、trace_id、脱敏 | 13 |
| `test_cost_tracker.py` | 费用追踪、预算检查、持久化 | 9 |
| `test_core.py` | 配置、沙箱、记忆、上下文等 | 60+ |
| `test_context.py` | 系统提示词内容 | 8 |
| 其他 | Diff、Glob、Todo 等 | 40+ |

**总计：176 个测试通过**

---

## 部署运维

### Docker 部署

#### 构建镜像

```bash
make docker-build    # 或
docker build -t mythcoder:latest .
```

#### 运行容器

```bash
# 交互模式
docker run -it --rm \
    -v $(pwd)/workspace:/workspace \
    -v $(pwd)/.env:/workspace/.env:ro \
    mythcoder:latest

# 或使用 docker-compose
docker-compose run mythcoder
```

#### Dockerfile 特性

- **多阶段构建**：builder 阶段编译，runtime 阶段仅含运行时依赖
- **非 root 用户**：使用 `mythcoder` 用户运行，安全性更高
- **健康检查**：内置 `HEALTHCHECK` 指令
- **镜像精简**：基于 `python:3.12-slim`，最终镜像约 200MB

#### Docker Compose

```yaml
# docker-compose.yml
services:
  mythcoder:
    build: .
    volumes:
      - ./workspace:/workspace
      - mythcoder_config:/home/mythcoder/.mythcoder
    environment:
      - MYTHCODER_API_KEY=${MYTHCODER_API_KEY}
    stdin_open: true
    tty: true

  # 可选：本地模型服务
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    profiles: ["local-model"]
```

### systemd 服务

将 MythCoder 作为系统服务运行：

```bash
# 安装服务
sudo cp deploy/systemd/mythcoder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mythcoder
sudo systemctl start mythcoder

# 查看日志
journalctl -u mythcoder -f
```

systemd service 特性：
- **自动重启**：崩溃后 5 秒自动重启
- **资源限制**：内存上限 2G，CPU 配额 200%
- **安全沙箱**：`ProtectSystem=strict`、`NoNewPrivileges=true` 等安全选项
- **日志集成**：标准输出写入 journald

### Makefile 常用命令

```bash
make help         # 显示所有命令
make install      # 安装包
make dev-install  # 安装开发依赖
make build        # 构建分发包
make test         # 运行测试
make test-cov     # 测试 + 覆盖率
make lint         # 代码检查
make format       # 代码格式化
make type-check   # 类型检查
make security     # 安全扫描
make docker-build # 构建 Docker 镜像
make docker-run   # 运行 Docker 容器
make release      # 发布新版本
make clean        # 清理构建产物
```

---

## 项目结构

```
MythCoder/
├── app.py                      # CLI 入口
├── config.yaml                 # 默认配置文件
├── pyproject.toml              # 项目元数据和依赖
├── .env                        # 环境变量（不提交到 Git）
│
├── agent/                      # Agent 核心
│   ├── loop.py                 # ReAct 主循环
│   ├── context.py              # 上下文管理器（系统 Prompt 构建）
│   ├── memory.py               # 对话历史管理（滑动窗口 + 摘要压缩）
│   ├── permissions.py          # 权限引擎
│   ├── hooks.py                # 钩子系统
│   ├── plan_manager.py         # 计划管理器
│   ├── skills.py               # 技能管理器
│   ├── subagent.py             # 子代理运行器
│   ├── session_fork.py         # 会话分叉
│   ├── session_index.py        # 会话索引
│   ├── session_map.py          # 步骤映射
│   ├── snapshot.py             # 文件快照管理
│   ├── persistence.py          # 对话持久化
│   ├── auto_memory.py          # 自动记忆
│   ├── claude_md.py            # CLAUDE.md 加载器
│   ├── rules.py                # 规则管理器
│   ├── todo.py                 # TODO 任务管理
│   ├── cost_tracker.py         # 跨会话费用追踪
│   ├── output_style.py         # 输出样式管理
│   ├── file_watcher.py         # 文件监听
│   ├── config_reloader.py      # 配置热重载
│   └── subagent_prompts.py     # 子代理 Prompt 模板
│
├── tools/                      # 工具系统
│   ├── registry.py             # 工具注册中心（支持按需加载）
│   ├── base.py                 # 工具基类
│   ├── init_tools.py           # 工具注册入口
│   ├── file_ops.py             # 文件操作（read/write/edit/read_image）
│   ├── directory_ops.py        # 目录操作
│   ├── command_ops.py          # 命令执行
│   ├── search_ops.py           # 代码搜索
│   ├── glob_ops.py             # Glob 匹配
│   ├── todo_ops.py             # TODO 管理
│   ├── task_ops.py             # 子代理工具
│   ├── web_ops.py              # Web 工具（fetch/search）
│   ├── notebook_ops.py         # Notebook 编辑
│   └── sandbox.py              # 沙箱安全
│
├── commands/                   # 斜杠命令
│   ├── registry.py             # 命令注册中心
│   ├── base.py                 # 命令基类
│   ├── loader.py               # 自定义命令加载器
│   ├── custom.py               # 自定义命令包装器
│   ├── help.py                 # /help
│   ├── clear.py                # /clear
│   ├── exit.py                 # /exit
│   ├── config_cmd.py           # /config
│   ├── tools_cmd.py            # /tools
│   ├── model.py                # /model
│   ├── rewind.py               # /rewind
│   ├── compact.py              # /compact
│   ├── cost.py                 # /cost
│   ├── init.py                 # /init
│   ├── doctor.py               # /doctor
│   ├── review.py               # /review, /security-review
│   ├── commit.py               # /commit, /pr
│   ├── branch_cmd.py           # /branch
│   ├── merge_cmd.py            # /merge
│   ├── bug.py                  # /bug
│   ├── status.py               # /status
│   ├── upgrade.py              # /upgrade
│   ├── ide.py                  # /ide
│   ├── permissions_cmd.py      # /permissions
│   ├── memory_cmd.py           # /memory
│   ├── add_dir.py              # /add-dir
│   ├── plan_cmd.py             # /plan
│   ├── skill_cmd.py            # /skill
│   ├── sessions_cmd.py         # /sessions
│   ├── switch_cmd.py           # /switch
│   ├── fork_cmd.py             # /fork
│   └── style_cmd.py            # /style
│
├── mcp/                        # MCP 协议集成
│   ├── client.py               # MCP 客户端（stdio/SSE）
│   ├── manager.py              # MCP 服务器管理
│   └── wrapper.py              # MCP 工具包装器
│
├── ide/                        # IDE 集成
│   ├── bridge.py               # IPC 通信桥
│   ├── handler.py              # 事件处理器
│   └── protocol.py             # 协议定义
│
├── llm/                        # LLM 客户端
│   ├── client.py               # LiteLLM 封装
│   └── token_counter.py        # Token 计数器
│
├── ui/                         # 用户界面
│   ├── console.py              # 终端输出（Rich）
│   ├── display.py              # 流式渲染
│   └── prompt.py               # 交互式输入
│
├── utils/                      # 工具函数
│   ├── agentignore.py          # .agentignore/.gitignore 管理
│   ├── debug.py                # 调试管理器
│   ├── git_utils.py            # Git 操作助手
│   ├── diff_utils.py           # Diff 工具
│   ├── glob_utils.py           # Glob 工具
│   ├── html_utils.py           # HTML 解析工具
│   ├── logger.py               # 日志配置
│   └── path_utils.py           # 路径工具
│
├── config/                     # 配置管理
│   ├── _config.py              # Pydantic 配置模型
│   ├── settings.py             # 多作用域设置管理
│   └── __init__.py             # 配置导出
│
└── tests/                      # 测试
    └── test_core.py            # 核心测试
```

---

## 开发指南

### 环境搭建

```bash
git clone <repo-url> MythCoder
cd MythCoder

# 安装开发依赖（含 ruff/black/mypy/pre-commit 等）
make dev-install

# 或手动安装
pip install -e ".[dev,all]"
pre-commit install
```

### 开发工作流

```bash
# 1. 编写代码
vim agent/loop.py

# 2. 格式化代码
make format

# 3. 代码检查
make lint

# 4. 类型检查
make type-check

# 5. 运行测试
make test

# 6. 测试 + 覆盖率
make test-cov

# 7. 安全扫描
make security
```

### 运行测试

```bash
make test                    # 运行所有测试
make test-cov                # 测试 + 覆盖率报告
pytest tests/test_llm_client.py -v    # 运行特定测试
```

### 调试模式

```bash
MythCoder --debug all                    # 全部调试日志
MythCoder --debug llm,tools              # 特定模块调试
MythCoder --verbose                      # 详细输出
```

### 查看日志

```bash
# 实时查看日志
tail -f ~/.mythcoder/logs/mythcoder.log | jq .

# 查看审计日志
tail -f ~/.mythcoder/audit.log | jq .

# 按 trace_id 过滤
cat ~/.mythcoder/logs/mythcoder.log | jq 'select(.trace_id == "abc123")'
```

### 添加新工具

1. 在 `tools/` 目录下创建新文件
2. 继承 `BaseTool`，实现 `name`、`description`、`parameters`、`execute()`
3. 在 `tools/init_tools.py` 中注册

```python
from tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具说明"
    parameters = {
        "input": {
            "type": "string",
            "description": "输入参数",
            "required": True,
        },
    }

    async def execute(self, input: str) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, output=f"处理了: {input}")
```

### 添加新命令

1. 在 `commands/` 目录下创建新文件
2. 继承 `BaseCommand`，实现 `name`、`description`、`execute()`
3. 在 `commands/__init__.py` 中注册

```python
from commands.base import BaseCommand

class MyCommand(BaseCommand):
    name = "my-cmd"
    description = "我的命令"

    async def execute(self, args: str, agent) -> None:
        # 实现命令逻辑
        pass
```

### 添加 MCP 服务器

在 `.mcp.json` 中添加服务器配置，MythCoder 启动时自动加载：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "node",
      "args": ["path/to/server.js"],
      "env": {"API_KEY": "xxx"}
    }
  }
}
```

---

## 版本管理

MythCoder 遵循 [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)。

### 当前阶段

| 版本 | 阶段 | 说明 |
|------|------|------|
| 0.x.x | Beta | 开发阶段，API 可能不稳定 |
| 1.0.0 | GA | 首个正式版本，API 稳定 |

### 发布流程

```bash
# 1. 更新 CHANGELOG.md
vim CHANGELOG.md

# 2. 发布版本（自动 bump 版本号 + tag + push）
make release VERSION=0.2.0

# 3. GitHub Actions 自动构建并发布到 PyPI
# 4. GitHub Release 自动创建（含 changelog）
```

### 向后兼容性

- **配置文件**：`config.yaml` 新增字段提供默认值，无需手动迁移
- **命令行参数**：已发布参数不删除，废弃参数保留 2 个版本
- **斜杠命令**：已发布命令不删除，废弃命令保留 2 个版本
- **Python API**：公开类/函数签名保持兼容

详细策略见 [VERSIONING.md](VERSIONING.md)。

---

## Changelog

完整的版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

### 最近变更（v0.1.0 → Unreleased）

#### 安全加固
- 修复 `commands/custom.py` 的 `shell=True` 命令注入漏洞
- 修复 `agent/hooks.py` 的路径拼接漏洞
- LLM 异常信息脱敏：自动过滤 API Key、Authorization 等敏感字段
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

#### 并发安全
- `ConversationMemory` 增加 `asyncio.Lock` 保护并发修改
- `ToolRegistry` 增加 `threading.RLock` 保护并发注册
- `CostTracker` 增加文件锁（`fcntl.flock`）防止并发写入冲突

#### CI/CD
- 新增 GitHub Actions CI 流水线（lint + test + security + build）
- 支持 Python 3.10/3.11/3.12 多版本矩阵测试
- 新增 Release 流水线（tag 触发自动发布 PyPI + GitHub Release）
- 配置 Dependabot 自动依赖更新

#### 部署运维
- 新增 `Dockerfile`（多阶段构建，非 root 用户，健康检查）
- 新增 `docker-compose.yml`（含可选 Ollama 本地模型服务）
- 新增 `Makefile`（install/test/build/release 等常用命令）
- 新增 `systemd` service 模板（安全沙箱，资源限制，自动重启）

#### 代码质量
- 配置 `ruff` + `black` + `isort` + `mypy` + `pre-commit`
- 新增 176 个单元测试

---

## License

MIT License - 详见 [LICENSE](LICENSE) 文件。
