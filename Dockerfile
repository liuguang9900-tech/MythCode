# ============================================================
# MythCoder Dockerfile — 多阶段构建
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制源码
COPY pyproject.toml README.md ./
COPY config/config.yaml ./config/config.yaml
COPY agent/ tools/ llm/ ui/ utils/ commands/ mcp/ ide/ ./

# 构建 wheel 包
RUN pip install --upgrade pip build && \
    python -m build --wheel

# ---------- Stage 2: Runtime ----------
FROM python:3.12-slim AS runtime

# 安装运行时依赖（git 用于 Git 集成功能）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -s /bin/bash mythcoder

# 从 builder 复制 wheel 包并安装
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# 切换到非 root 用户
USER mythcoder
WORKDIR /workspace

# 创建配置目录
RUN mkdir -p ~/.mythcoder/logs

# 默认环境变量
ENV MYTHCODER_LOG_LEVEL=INFO \
    MYTHCODER_LOG_FORMAT=json \
    PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD MythCoder --version || exit 1

# 入口
ENTRYPOINT ["MythCoder"]
CMD ["--help"]
