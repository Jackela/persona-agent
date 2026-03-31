# Contributing to Persona-Agent

感谢你的贡献！请阅读以下指南以确保代码质量和一致性。

## 开发流程

### 分支策略

**⚠️ 重要：** 所有 PR 必须指向 `dev` 分支，而不是 `main` 或 `master`！

```bash
# 1. 从 dev 分支创建功能分支
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name

# 2. 开发并提交更改
git add .
git commit -m "feat: add new feature"

# 3. 推送到你的 fork
git push origin feature/your-feature-name

# 4. 创建 PR 到 dev 分支
```

### PR 标题规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**类型 (type):**
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档更新
- `style`: 代码格式 (不影响代码功能)
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试
- `build`: 构建系统
- `ci`: CI/CD 相关
- `chore`: 其他

**示例:**
- `feat: add mood detection for angry users`
- `fix: resolve memory store connection issue`
- `docs: update README with new config options`

## 代码质量要求

### 1. 格式化

所有代码必须使用 Black 格式化：

```bash
black src tests
```

### 2. 代码检查

使用 Ruff 进行代码检查：

```bash
ruff check src tests --fix
```

### 3. 类型检查

所有代码必须通过 mypy 严格类型检查：

```bash
mypy src --strict
```

### 4. 测试

- 所有新功能必须包含测试
- 测试覆盖率必须 ≥ 70%
- 所有测试必须通过

```bash
pytest --cov=src/persona_agent --cov-fail-under=65
```

### 5. 安全检查

- 使用 bandit 检查安全问题
- 禁止使用 `eval()` 等危险函数
- 依赖必须定期更新

```bash
bandit -r src
safety check
```

## CI 检查

所有 PR 必须通过以下 CI 检查：

1. ✅ **Branch Protection** - PR 必须指向 dev 分支
2. ✅ **Lint & Format** - Black + Ruff
3. ✅ **Type Check** - mypy strict mode
4. ✅ **Test Suite** - pytest with 70% coverage
5. ✅ **Security Audit** - bandit + safety
6. ✅ **Architecture Check** - 循环导入检查
7. ✅ **Build** - 包构建验证
8. ✅ **Documentation** - README 完整性

## 提交前检查清单

- [ ] 代码已格式化 (`black`)
- [ ] 代码检查通过 (`ruff`)
- [ ] 类型检查通过 (`mypy`)
- [ ] 所有测试通过 (`pytest`)
- [ ] 覆盖率 ≥ 70%
- [ ] 安全检查通过 (`bandit`)
- [ ] PR 标题符合规范
- [ ] PR 指向 dev 分支

## 设置开发环境

```bash
# 克隆仓库
git clone https://github.com/yourusername/persona-agent.git
cd persona-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

## 获取帮助

- 查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解项目架构
- 查看 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) 了解实现细节
- 创建 Issue 讨论新功能
- 在 PR 中 @mention 维护者

## 行为准则

- 尊重他人
- 接受建设性批评
- 关注对社区最有利的事情
- 友善对待其他贡献者
