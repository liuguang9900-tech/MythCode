# ============================================================
# MythCoder Makefile — 常用开发命令
# ============================================================

.PHONY: help install dev-install build test test-cov lint format type-check security clean docker-build docker-run release

PYTHON ?= python3
VERSION ?= $(shell grep 'version = ' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装包
	$(PYTHON) -m pip install -e .

dev-install: ## 安装开发依赖
	$(PYTHON) -m pip install -e ".[dev,all]"
	pre-commit install

build: ## 构建分发包
	$(PYTHON) -m build

test: ## 运行测试
	pytest tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	pytest tests/ -v --cov=agent --cov=tools --cov=llm --cov=config --cov-report=html --cov-report=term-missing

lint: ## 代码检查
	ruff check .

format: ## 代码格式化
	ruff format .
	ruff check --fix .
	isort .

type-check: ## 类型检查
	mypy agent/ tools/ llm/ config/ --ignore-missing-imports

security: ## 安全扫描
	bandit -r agent/ tools/ llm/ commands/ mcp/ -f json -o bandit-report.json
	pip-audit

docker-build: ## 构建 Docker 镜像
	docker build -t mythcoder:$(VERSION) .

docker-run: ## 运行 Docker 容器
	docker run -it --rm \
		-v $(PWD)/workspace:/workspace \
		-v $(PWD)/.env:/workspace/.env:ro \
		mythcoder:$(VERSION)

release: ## 发布新版本（需要 VERSION=x.y.z）
	@test -n "$(VERSION)" || (echo "用法: make release VERSION=x.y.z" && exit 1)
	@echo "发布版本 $(VERSION)"
	sed -i.bak 's/version = ".*"/version = "$(VERSION)"/' pyproject.toml && rm -f pyproject.toml.bak
	git add pyproject.toml
	git commit -m "chore: bump version to $(VERSION)"
	git tag v$(VERSION)
	git push origin v$(VERSION)
	@echo "✓ 已推送 tag v$(VERSION)，GitHub Actions 将自动发布到 PyPI"

clean: ## 清理构建产物
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✓ 清理完成"
