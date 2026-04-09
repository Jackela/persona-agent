# OpenCode 完全自主开发环境配置指南

## 📋 概述

本文档指导你配置完整的 OpenCode 自主开发环境，让 AI 能够自主进行浏览器自动化、Web 测试、代码迭代等工作。

## 🎯 核心能力

配置完成后，AI 将能够自主：

- 🌐 **浏览器自动化** - 打开网站、填写表单、点击按钮
- 📸 **屏幕截图** - 验证 UI、记录测试结果
- 🧪 **Web 测试** - 自动化前后端分离项目的 E2E 测试
- 🔍 **数据提取** - 从网页抓取信息
- 🔄 **迭代开发** - 修改代码 → 测试 → 验证 → 继续修改

## 📦 已配置工具

### 1. agent-browser (Vercel)
- **类型**: Rust CLI 工具
- **特点**: 极速响应（~50ms）、refs 机制、snapshot 断言
- **适用**: 确定性测试、CI/CD 集成、精确控制

### 2. browser-use
- **类型**: Python 库 + CLI
- **特点**: 自然语言任务、AI Agent 抽象、Cloud 反检测
- **适用**: 探索性测试、复杂工作流、快速原型

### 3. MCP 工具
- **Playwright MCP** - 浏览器自动化 MCP 服务器
- **Context7** - 技术文档搜索
- **GitHub MCP** - 代码仓库管理
- **Firecrawl** - 网页抓取 (可选)

## 🚀 快速开始

### 1. 运行安装脚本

```bash
# 确保在项目根目录
cd /mnt/d/Code/persona-agent

# 运行配置脚本
chmod +x setup-opencode-env.sh
./setup-opencode-env.sh
```

### 2. 验证安装

```bash
# 检查 agent-browser
agent-browser --version

# 检查 browser-use CLI
browser-use --version

# 检查 browser-use Python
source .venv/bin/activate
python3 -c "import browser_use; print('OK')"
```

### 3. 快速测试

```bash
# 使用 agent-browser 测试
agent-browser open https://example.com
agent-browser snapshot -i
agent-browser screenshot test.png

# 使用 browser-use 测试
browser-use open https://example.com
browser-use state
browser-use screenshot test2.png
```

## 📁 项目结构

```
persona-agent/
├── AGENTS.md                          # AI 开发指南
├── .opencode/
│   ├── config.json                    # OpenCode 配置
│   └── skills/
│       ├── agent-browser.md          # agent-browser skill
│       └── browser-use.md            # browser-use skill
├── setup-opencode-env.sh             # 安装脚本
└── .venv/                            # Python 虚拟环境
```

## 🎮 使用场景示例

### 场景 1: 测试登录页面

```bash
# agent-browser 方式 - 精确控制
agent-browser batch \
  "open http://localhost:3000/login" \
  "fill @e1 'test@example.com'" \
  "fill @e2 'password123'" \
  "click @e3" \
  "wait --text 'Dashboard'" \
  "screenshot login-success.png"

# browser-use 方式 - 自然语言
browser-use open http://localhost:3000/login
browser-use state
# 根据 state 输出决定点击哪个元素...
```

### 场景 2: Python 自动化测试

```python
# test_login.py
import asyncio
from browser_use import Agent, Browser, ChatBrowserUse

async def test_login():
    browser = Browser()
    agent = Agent(
        task="Test the login flow on http://localhost:3000",
        llm=ChatBrowserUse(),
        browser=browser,
    )
    result = await agent.run()
    return result

if __name__ == "__main__":
    result = asyncio.run(test_login())
    print(f"Test result: {result}")
```

### 场景 3: AI 自主开发工作流

AI 现在可以这样工作：

1. **编写代码** → 修改前端组件
2. **启动服务** → `npm run dev`
3. **测试验证** → 
   ```bash
   agent-browser open http://localhost:3000
   agent-browser screenshot before.png
   # ... 执行操作 ...
   agent-browser screenshot after.png
   agent-browser diff screenshot --baseline before.png
   ```
4. **分析结果** → 根据截图对比决定是否继续修改
5. **循环迭代** → 重复直到满足要求

## 🔧 工具对比

| 特性 | agent-browser | browser-use |
|------|---------------|-------------|
| **响应速度** | ⚡⚡⚡⚡⚡ (~50ms) | ⚡⚡⚡ (~200ms) |
| **学习曲线** | 中等（需学 commands） | 低（自然语言） |
| **可控性** | ⭐⭐⭐⭐⭐ 精确 | ⭐⭐⭐ 黑盒 |
| **CI/CD** | ⭐⭐⭐⭐⭐ 完美 | ⭐⭐⭐ 需配置 |
| **自然语言** | ⭐⭐ 命令式 | ⭐⭐⭐⭐⭐ 声明式 |
| **最佳场景** | 回归测试、CI | 探索、复杂任务 |

### 选择建议

- **前端精确测试** → agent-browser
- **快速探索验证** → browser-use
- **CI/CD 集成** → agent-browser
- **复杂多步任务** → browser-use

## 📝 Skill 文件说明

### agent-browser skill
位于 `.opencode/skills/agent-browser.md`

包含：
- 安装说明
- 核心工作流
- 所有命令参考
- 认证处理
- 最佳实践

### browser-use skill
位于 `.opencode/skills/browser-use.md`

包含：
- 安装说明
- CLI 命令
- Python API 示例
- 常见工作流
- 故障排除

## 🔐 环境变量

创建 `.env` 文件（已添加到 `.gitignore`）：

```bash
# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Browser Use Cloud (可选)
BROWSER_USE_API_KEY=...

# MCP 工具 (可选)
FIRECRAWL_API_KEY=...
CONTEXT7_API_KEY=...

# agent-browser 加密 (可选)
AGENT_BROWSER_ENCRYPTION_KEY=...
```

## 🐛 故障排除

### agent-browser 问题

```bash
# 浏览器无法启动
agent-browser close
agent-browser --headed open <url>

# 元素找不到
agent-browser scroll down
agent-browser state

# 诊断
agent-browser doctor
```

### browser-use 问题

```bash
# 检查安装
browser-use doctor

# 浏览器问题
playwright install chromium

# 权限问题
chmod +x .venv/bin/*
```

## 🚀 高级配置

### 全局 MCP 配置

编辑 `~/.config/opencode/opencode.json`：

```json
{
  "mcp": {
    "playwright": {
      "type": "local",
      "command": ["npx", "-y", "@playwright/mcp"],
      "enabled": true
    },
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

### 自定义 Skill

创建 `.opencode/skills/my-skill.md`：

```markdown
---
name: my-skill
description: My custom skill
---

## When to use
When the user asks about X...

## Tools
- Bash(my-command)

## Examples
```bash
my-command arg1 arg2
```
```

## 📚 参考资料

- [agent-browser 文档](https://agent-browser.dev)
- [browser-use 文档](https://docs.browser-use.com)
- [OpenCode 文档](https://opencode.ai/docs)
- [MCP 协议](https://modelcontextprotocol.io)

## ✅ 验证清单

配置完成后，确认以下检查项：

- [ ] `agent-browser --version` 显示版本
- [ ] `browser-use --version` 显示版本
- [ ] `source .venv/bin/activate` 成功
- [ ] `python3 -c "import browser_use"` 无错误
- [ ] `agent-browser open https://example.com` 成功
- [ ] `browser-use open https://example.com` 成功
- [ ] `.opencode/skills/` 包含两个 skill 文件
- [ ] `AGENTS.md` 存在且内容正确

## 🎉 完成！

现在 AI 可以自主进行：
1. 浏览器自动化测试
2. Web 应用验证
3. 截图对比
4. 数据提取
5. 持续迭代开发

开始你的自主开发之旅吧！
