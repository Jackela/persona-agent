#!/bin/bash
# OpenCode 完全自主开发环境配置脚本
# 为 persona-agent 项目配置完整的 AI 开发环境

set -e

echo "🚀 Setting up OpenCode autonomous development environment for persona-agent..."

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="/mnt/d/Code/persona-agent"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  OpenCode 完全自主开发环境配置${NC}"
echo -e "${BLUE}  项目: persona-agent${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 检查 Node.js
echo -e "${YELLOW}▶ Checking Node.js installation...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js 18+ first.${NC}"
    echo "   Visit: https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}✗ Node.js version 18+ required. Current: $(node --version)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node --version) found${NC}"

# 检查 Python
echo -e "${YELLOW}▶ Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.11+ first.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# 检查 npm
echo -e "${YELLOW}▶ Checking npm installation...${NC}"
if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm $(npm --version) found${NC}"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  安装全局工具${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 安装 agent-browser
echo -e "${YELLOW}▶ Installing agent-browser (global)...${NC}"
if command -v agent-browser &> /dev/null; then
    echo -e "${GREEN}✓ agent-browser already installed ($(agent-browser --version 2>/dev/null || echo 'unknown'))${NC}"
else
    npm install -g agent-browser
    echo -e "${GREEN}✓ agent-browser installed${NC}"
fi

# 安装 browser-use CLI
echo -e "${YELLOW}▶ Installing browser-use CLI (global)...${NC}"
if command -v browser-use &> /dev/null; then
    echo -e "${GREEN}✓ browser-use CLI already installed${NC}"
else
    npm install -g browser-use
    echo -e "${GREEN}✓ browser-use CLI installed${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  配置项目环境${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cd "$PROJECT_DIR"

# 创建虚拟环境
echo -e "${YELLOW}▶ Setting up Python virtual environment...${NC}"
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
else
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# 激活虚拟环境并安装依赖
echo -e "${YELLOW}▶ Installing Python dependencies...${NC}"
source .venv/bin/activate
pip install --upgrade pip

# 安装项目依赖
if [ -f "pyproject.toml" ]; then
    pip install -e ".[dev]"
    echo -e "${GREEN}✓ Project dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ pyproject.toml not found, skipping project install${NC}"
fi

# 安装 browser-use Python 包
echo -e "${YELLOW}▶ Installing browser-use Python package...${NC}"
pip install browser-use playwright

# 安装 Playwright 浏览器
echo -e "${YELLOW}▶ Installing Playwright browsers...${NC}"
playwright install chromium

echo -e "${GREEN}✓ Playwright browsers installed${NC}"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  验证安装${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 验证安装
echo -e "${YELLOW}▶ Verifying installations...${NC}"
echo ""

echo -n "agent-browser: "
if command -v agent-browser &> /dev/null; then
    echo -e "${GREEN}✓ OK ($(agent-browser --version 2>/dev/null || echo 'installed'))${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
fi

echo -n "browser-use CLI: "
if command -v browser-use &> /dev/null; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
fi

echo -n "browser-use Python: "
if python3 -c "import browser_use" 2>/dev/null; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
fi

echo -n "playwright: "
if command -v playwright &> /dev/null; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  配置完成！${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cat << 'EOF'
✨ 安装完成！你的 OpenCode 自主开发环境已就绪。

📁 项目配置:
   - AGENTS.md          → 项目特定的 AI 开发指南
   - .opencode/         → OpenCode 配置文件
   - .opencode/skills/  → Skill 文件

🛠️  已安装工具:
   - agent-browser      → Rust 浏览器自动化 CLI
   - browser-use CLI    → 命令行浏览器工具
   - browser-use Python → Python 浏览器自动化库
   - Playwright         → 浏览器控制引擎

🚀 快速开始:

   # 激活虚拟环境
   source .venv/bin/activate

   # 使用 agent-browser 测试网站
   agent-browser open https://example.com
   agent-browser snapshot -i
   agent-browser screenshot

   # 使用 browser-use 测试
   browser-use open https://example.com
   browser-use state
   browser-use screenshot

   # Python API 示例
   python3 -c "
   from browser_use import Agent, Browser, ChatBrowserUse
   import asyncio
   
   async def test():
       browser = Browser()
       agent = Agent(
           task='Open example.com and take a screenshot',
           llm=ChatBrowserUse(),
           browser=browser,
       )
       await agent.run()
   
   asyncio.run(test())
   "

📚 更多文档:
   - .opencode/skills/agent-browser.md   → agent-browser 完整文档
   - .opencode/skills/browser-use.md     → browser-use 完整文档

🎯 AI 现在可以自主:
   ✓ 打开和浏览网站
   ✓ 填写表单和点击按钮
   ✓ 截取屏幕截图
   ✓ 提取网页数据
   ✓ 测试 Web 应用程序
   ✓ 自动化浏览器工作流

⚠️ 注意事项:
   - 首次运行可能需要下载 Chrome/Chromium
   - 部分功能需要 API key (OpenAI, Anthropic 等)
   - 确保虚拟环境已激活后再使用 Python API

EOF

echo ""
echo -e "${GREEN}🎉 Setup complete! Happy coding!${NC}"
