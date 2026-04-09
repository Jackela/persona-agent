# OpenCode 完全自主开发环境 - 工具清单

## ✅ 已配置 Skills

### 1. browser-use
- **路径**: `~/.config/opencode/skills/browser-use.md`
- **用途**: Python 浏览器自动化
- **能力**: 
  - 打开/浏览网站
  - 截取屏幕截图
  - 执行 JavaScript
  - Python API 调用

### 2. agent-browser
- **路径**: `~/.config/opencode/skills/agent-browser.md`
- **用途**: Rust 浏览器自动化 CLI
- **能力**:
  - 极速响应 (~50ms)
  - Snapshot + refs 机制
  - 批量命令执行
  - 网络拦截 & HAR 记录

### 3. code-review
- **路径**: `~/.config/opencode/skills/code-review.md`
- **用途**: 代码审查
- **能力**:
  - 安全检查
  - 性能分析
  - 代码质量评估
  - 架构审查

### 4. test-generator
- **路径**: `~/.config/opencode/skills/test-generator.md`
- **用途**: 测试生成
- **能力**:
  - 单元测试生成
  - 集成测试生成
  - pytest/Jest 支持
  - 覆盖率分析

### 5. git-master
- **路径**: `~/.config/opencode/skills/git-master.md`
- **用途**: Git 操作
- **能力**:
  - 原子提交
  - Rebase/squash
  - 历史搜索
  - 分支管理

## ✅ 已配置 MCP 工具

### 本地 MCP

#### 1. Playwright MCP
- **命令**: `npx -y @playwright/mcp`
- **用途**: 浏览器自动化 MCP 服务器
- **状态**: ✅ 已启用

#### 2. Fetch MCP
- **命令**: `uvx mcp-server-fetch`
- **用途**: HTTP 请求 MCP 服务器
- **状态**: ✅ 已启用

#### 3. Sequential Thinking MCP
- **命令**: `npx -y @modelcontextprotocol/server-sequential-thinking`
- **用途**: 结构化思考 MCP 服务器
- **状态**: ✅ 已启用

### 远程 MCP

#### 4. Context7
- **URL**: `https://mcp.context7.com/mcp`
- **用途**: 技术文档搜索
- **状态**: ✅ 已启用

#### 5. GitHub MCP
- **URL**: `https://api.githubcopilot.com/mcp/`
- **用途**: GitHub 操作
- **状态**: ✅ 已启用 (需 OAuth)

## ✅ 全局安装的工具

### Node.js 工具
```bash
✅ agent-browser          # Rust 浏览器自动化
✅ browser-use            # Node CLI 浏览器工具
✅ @playwright/mcp        # Playwright MCP 服务器
```

### Python 工具
```bash
✅ browser-use            # Python 包
✅ playwright             # 浏览器控制
✅ chromium               # Playwright 浏览器
```

## 🎯 AI 现在可以自主完成

### 开发工作流
1. ✅ 编写代码 (任何语言)
2. ✅ 运行测试 (pytest, jest, etc.)
3. ✅ 代码审查 (安全检查、性能分析)
4. ✅ Git 操作 (提交、分支、rebase)
5. ✅ 生成测试 (单元测试、集成测试)

### 浏览器自动化
1. ✅ 打开和浏览网站
2. ✅ 填写表单和点击按钮
3. ✅ 截取屏幕截图
4. ✅ 提取网页数据
5. ✅ 执行 JavaScript
6. ✅ 网络请求拦截

### 测试 & 验证
1. ✅ 前端 E2E 测试
2. ✅ API 测试
3. ✅ 截图对比
4. ✅ 性能测试
5. ✅ 回归测试

### 信息搜集
1. ✅ 技术文档搜索 (Context7)
2. ✅ 网页内容抓取
3. ✅ GitHub 代码搜索
4. ✅ API 文档查询

## 📋 配置文件

### 项目级配置
- `.opencode/config.json` - OpenCode 主配置
- `.opencode/skills/*.md` - Skill 文件 (5个)
- `AGENTS.md` - 项目开发指南

### 全局配置
- `~/.config/opencode/opencode.json` - 全局 OpenCode 配置 (可选)

## 🔧 验证命令

```bash
# 检查 agent-browser
agent-browser --version

# 检查 browser-use CLI (测试命令)
browser-use open https://example.com --help

# 检查 Python 包
python3 -c "import browser_use; print('browser-use OK')"
python3 -c "import playwright; print('playwright OK')"

# 检查 MCP 工具
npx @playwright/mcp --version
```

## 🚀 使用示例

### 示例 1: 自主开发循环

AI 可以执行完整的工作流：

```
1. 用户: "帮我实现用户登录功能"
2. AI: 创建登录组件
3. AI: 启动开发服务器
4. AI: 打开浏览器测试
   agent-browser open http://localhost:3000/login
   agent-browser fill @e1 "test@test.com"
   agent-browser fill @e2 "password"
   agent-browser click @e3
   agent-browser screenshot result.png
5. AI: 分析截图，验证功能
6. AI: 如需要，修复问题
7. AI: 生成测试用例
8. AI: 提交代码
   git add .
   git commit -m "feat: implement user login"
```

### 示例 2: 代码审查

```
用户: "审查这个 PR"
AI: 使用 code-review skill 分析代码
AI: 检查安全问题、性能问题、代码质量
AI: 输出详细的审查报告
```

### 示例 3: 生成测试

```
用户: "为 auth.py 生成测试"
AI: 使用 test-generator skill
AI: 分析 auth.py 的函数
AI: 生成 pytest 测试用例
AI: 运行测试验证
```

## 📊 能力矩阵

| 能力 | agent-browser | browser-use | MCP 工具 | Skills |
|------|---------------|-------------|----------|--------|
| 打开网页 | ✅ | ✅ | ✅ | - |
| 点击元素 | ✅ | ✅ | ✅ | - |
| 填写表单 | ✅ | ✅ | ✅ | - |
| 截图 | ✅ | ✅ | ✅ | - |
| 执行 JS | ✅ | ✅ | ✅ | - |
| 网络拦截 | ✅ | ❌ | ❌ | - |
| 批量命令 | ✅ | ❌ | ❌ | - |
| 自然语言 | ❌ | ✅ | ❌ | - |
| 代码审查 | - | - | - | ✅ |
| 生成测试 | - | - | - | ✅ |
| Git 操作 | - | - | - | ✅ |
| 文档搜索 | - | - | ✅ | - |

## 🎉 总结

OpenCode 现在拥有完整的自主开发能力：

- **5 个 Skill** 覆盖代码审查、测试生成、Git 操作、浏览器自动化
- **5 个 MCP 工具** 提供浏览器控制、文档搜索、GitHub 集成
- **全局工具** 安装完成，立即可用
- **项目配置** 完整，AI 可以理解项目结构

AI 现在可以自主进行：开发 → 测试 → 验证 → 迭代 的完整循环！
