#!/bin/bash
# 验证 OpenCode 全局安装 - 运行此脚本检查安装是否成功

echo "🔍 验证 OpenCode 开发环境安装..."
echo ""

FAILED=0

# 检查 Node.js 工具
echo "1. 检查 Node.js 工具:"
if command -v agent-browser &> /dev/null; then
    echo "   ✅ agent-browser: $(agent-browser --version 2>/dev/null | head -1)"
else
    echo "   ❌ agent-browser: 未安装"
    FAILED=1
fi

if npm list -g @playwright/mcp &> /dev/null; then
    echo "   ✅ @playwright/mcp: 已安装"
else
    echo "   ❌ @playwright/mcp: 未安装"
    FAILED=1
fi

if command -v browser-use &> /dev/null; then
    # 测试是否能正常运行（忽略 injected env 日志）
    if browser-use --version 2>&1 | grep -q "[0-9]\+\.[0-9]\+\.[0-9]\+"; then
        echo "   ✅ browser-use CLI: 工作正常"
    else
        echo "   ⚠️  browser-use CLI: 安装但可能有问题"
    fi
else
    echo "   ❌ browser-use CLI: 未安装"
    FAILED=1
fi

echo ""
echo "2. 检查 Python 工具:"
if python3 -c "import browser_use" 2>/dev/null; then
    echo "   ✅ browser-use Python: $(python3 -c 'import browser_use; print(browser_use.__version__)' 2>/dev/null || echo '已安装')"
else
    echo "   ❌ browser-use Python: 未安装"
    FAILED=1
fi

if python3 -c "import playwright" 2>/dev/null; then
    echo "   ✅ playwright Python: 已安装"
else
    echo "   ❌ playwright Python: 未安装"
    FAILED=1
fi

# 检查 Playwright 浏览器
echo ""
echo "3. 检查 Playwright 浏览器:"
if [ -d "$HOME/.cache/ms-playwright/chromium-"* ] 2>/dev/null; then
    echo "   ✅ Chromium: 已安装"
else
    echo "   ⚠️  Chromium: 可能需要运行 'playwright install chromium'"
fi

echo ""
echo "4. 检查 MCP 工具:"
if command -v uvx &> /dev/null || pip list 2>/dev/null | grep -q mcp-server-fetch; then
    echo "   ✅ Fetch MCP: 可用"
else
    echo "   ⚠️  Fetch MCP: 需要 'pip install mcp-server-fetch' 或 'pip install uv'"
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo "🎉 所有检查通过！环境已就绪。"
else
    echo "⚠️  部分工具未安装，请查看上面的 ❌ 标记。"
    echo "   运行安装命令修复后，再次运行此脚本。"
fi
