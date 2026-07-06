# 版本管理策略

MythCoder 遵循 [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)。

## 版本号格式

```
MAJOR.MINOR.PATCH
```

- **MAJOR**：不兼容的 API 变更
- **MINOR**：向后兼容的新功能
- **PATCH**：向后兼容的 Bug 修复

## 当前阶段

| 版本 | 阶段 | 说明 |
|------|------|------|
| 0.x.x | Alpha/Beta | 开发阶段，API 可能不稳定 |
| 1.0.0 | GA | 首个正式版本，API 稳定 |
| 1.x.x | Stable | 稳定版本，向后兼容 |

## 向后兼容性承诺

### 从 1.0.0 开始
- **配置文件**：`config.yaml` 格式保持向后兼容，新增字段提供默认值
- **命令行参数**：已发布的参数不删除，废弃参数至少保留 2 个版本
- **Python API**：公开类/函数签名保持兼容
- **斜杠命令**：已发布命令不删除，废弃命令至少保留 2 个版本

### 废弃流程
1. 在版本 X.Y.0 标记为 `@deprecated`
2. 在文档中声明将在 X.Y+2.0 删除
3. 在 X.Y+2.0 版本删除

## 发布流程

### 1. 准备发布
```bash
# 更新 CHANGELOG.md
vim CHANGELOG.md

# 更新版本号
make release VERSION=0.2.0
```

### 2. 自动发布（CI/CD）
- 推送 `v0.2.0` tag 触发 GitHub Actions
- 自动构建 wheel + sdist
- 自动发布到 PyPI
- 自动创建 GitHub Release

### 3. 手动验证
```bash
# 验证安装
pip install mythcoder==0.2.0
MythCoder --version
MythCoder --init
MythCoder
```

## 版本里程碑

| 版本 | 目标 | 预计 |
|------|------|------|
| 0.2.0 | 生产化改造完成（安全+日志+CI） | 2026-06 |
| 0.3.0 | 可观测性完善（metrics+tracing） | 2026-07 |
| 1.0.0 | GA 发布，API 稳定 | 2026-08 |

## 配置版本迁移

`config.yaml` 和持久化数据支持版本迁移：

- `config.yaml`：新增字段提供默认值，无需手动迁移
- 持久化数据：`agent/persistence.py` 检查 `version` 字段，未来版本将实现迁移函数
