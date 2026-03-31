# CI/CD 配置说明

## 📋 概述

本项目采用 **严格** 的 CI/CD 流程，灵感来源于优秀的 vibe coding 项目 [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)。

## 🔒 严格的质量门禁

### 1. 分支保护
- ❌ **禁止直接向 main/master 提交 PR**
- ✅ 所有更改必须通过 `dev` 分支
- ✅ PR 必须通过所有检查才能合并

### 2. 代码质量检查 (8项)

| 检查项 | 工具 | 严格程度 |
|--------|------|----------|
| 代码格式化 | Black | ❌ 失败即阻止 |
| 代码规范 | Ruff | ❌ 失败即阻止 |
| 类型检查 | MyPy (strict) | ❌ 失败即阻止 |
| 单元测试 | pytest | ❌ 失败即阻止 |
| 测试覆盖率 | ≥70% | ❌ 失败即阻止 |
| 安全审计 | Bandit + Safety | ⚠️ 警告但不阻止 |
| 架构检查 | 循环导入检测 | ❌ 失败即阻止 |
| 构建验证 | Build + Twine | ❌ 失败即阻止 |

### 3. 工作流文件

#### `ci.yml` - 主 CI 流程
```
block-main-pr (分支保护)
    ↓
lint (格式化检查) ────┐
    ↓                  │
typecheck (类型检查) ─┤
    ↓                  │
test (测试) ◄─────────┘
    ↓
security (安全审计)
    ↓
build (构建验证)
    ↓
docs (文档检查)
    ↓
lint-workflows (工作流检查)
```

**Jobs:**
- `block-main-pr`: 阻止直接向 main 的 PR
- `lint`: Black + Ruff 代码检查
- `typecheck`: MyPy 严格类型检查
- `test`: pytest 多版本测试 (Python 3.11, 3.12)
- `security`: Bandit 安全扫描 + Safety 漏洞检查
- `architecture`: 循环导入检测 + 包结构验证
- `build`: 构建验证 + 安装测试
- `docs`: README 完整性检查
- `lint-workflows`: actionlint 工作流检查

#### `pr-checks.yml` - PR 检查
- PR 标题规范检查 (Conventional Commits)
- PR 大小检查 (超过 500 行警告)

#### `release.yml` - 发布
- 标签版本与 pyproject.toml 版本匹配验证
- 自动创建 GitHub Release
- 构建产物上传

### 4. Pre-commit Hooks

本地提交前自动运行：
```yaml
- 文件格式检查 (trailing-whitespace, end-of-file-fixer)
- Black 格式化
- Ruff 代码检查
- MyPy 类型检查
- Bandit 安全检查
- JSON/YAML 验证
```

安装：
```bash
pip install pre-commit
pre-commit install
```

## 🚀 如何贡献

### 开发流程

1. **Fork 仓库**
2. **从 dev 分支创建功能分支**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   ```

3. **开发并提交**
   ```bash
   # 代码格式化
   black src tests
   
   # 代码检查
   ruff check src tests --fix
   
   # 类型检查
   mypy src --strict
   
   # 运行测试
   pytest --cov=src/persona_agent --cov-fail-under=65
   
   # 提交 (使用规范格式)
   git commit -m "feat: add new feature"
   ```

4. **推送到你的 fork**
   ```bash
   git push origin feature/my-feature
   ```

5. **创建 PR 到 dev 分支**

### PR 标题规范

```
<type>(<scope>): <description>
```

类型：
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档
- `style`: 格式
- `refactor`: 重构
- `perf`: 性能
- `test`: 测试
- `ci`: CI/CD

## 📊 徽章

README 中显示以下徽章：
- Python 版本
- 许可证
- 代码风格 (Black)
- CI 状态
- 覆盖率 (Codecov)
- Ruff 代码质量

## 🛠️ 本地开发

### 必需工具

```bash
pip install -e ".[dev]"
```

开发依赖包括：
- black (格式化)
- ruff (代码检查)
- mypy (类型检查)
- pytest (测试)
- pytest-cov (覆盖率)
- pre-commit (提交前检查)

### 本地运行 CI 检查

```bash
# 完整检查
make ci

# 或分别运行
black --check src tests
ruff check src tests
mypy src --strict
pytest --cov=src/persona_agent --cov-fail-under=65
bandit -r src
safety check
```

## 📁 文件结构

```
.github/
├── workflows/
│   ├── ci.yml              # 主 CI 流程
│   ├── pr-checks.yml       # PR 检查
│   └── release.yml         # 发布流程
├── CODEOWNERS              # 代码所有者
├── .pre-commit-config.yaml # 预提交钩子
└── CONTRIBUTING.md         # 贡献指南
```

## 🔐 安全实践

1. **依赖安全**: Safety 检查已知漏洞
2. **代码安全**: Bandit 扫描安全问题
3. **密钥检测**: Pre-commit 检测私钥
4. **构建安全**: 验证构建产物

## 📈 最佳实践参考

本项目 CI 设计参考：
- [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) - 严格的 TypeScript CI
- [FastAPI](https://github.com/tiangolo/fastapi) - Python 项目最佳实践
- [Pydantic](https://github.com/pydantic/pydantic) - 严格的类型检查

## ❓ 常见问题

### Q: 为什么 PR 被阻止？
A: 检查 CI 日志，常见原因：
- 代码未格式化 (`black --check` 失败)
- 代码检查未通过 (`ruff check` 失败)
- 类型错误 (`mypy` 失败)
- 测试失败或覆盖率不足 70%

### Q: 如何修复失败的检查？
A: 本地运行相同命令：
```bash
black src tests
ruff check src tests --fix
mypy src --strict
pytest
```

### Q: 可以忽略某些检查吗？
A: 不可以。所有检查都是强制性的，确保安全性和代码质量。

---

**💡 提示**: 在创建 PR 前，确保所有本地检查都通过，可以大大加快合并速度！
