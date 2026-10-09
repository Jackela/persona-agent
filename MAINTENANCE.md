# 维护与验证

README 和其他 Markdown 是可编辑母稿。修改前检查目标分支与相关实现，维护后记录源码修订、实际命令、退出码和剩余问题。本次基线为 main 的 `06a34392ec582db96c9f7697a3ed2b43b1d1eb3d`；dev 有独有工作，本修复不合并或删除它。

## 离线验证入口

```bash
pip install -e ".[dev]"
PYTHONPATH=src python scripts/check_integration.py
```

该入口使用真实服务、临时 SQLite 和临时技能演进目录，LLM 边界使用测试替身，不调用收费模型或 Ollama。它验证聊天、记忆、规划、技能与服务的组合行为；不证明外部模型、MCP 宿主或部署环境可用。pytest 失败、收集失败和无测试都会返回非零，CI 的独立步骤保留该退出码。

默认入口运行整个 `tests/integration`。可传入明确的测试文件作故障复现，例如 `python scripts/check_integration.py path/to/test_regression.py`。

## 当前证据范围

基线已有 105 项集成测试通过，但旧 CI 用 `|| true` 吞掉失败。修复后仍运行这 105 项，并以故意失败的独立临时测试验证旧命令返回 0、新入口返回 1。结构化记录见 `maintenance-evidence.json`。

本修复不将历史报告改写成全系统验收。CI 仍有历史类型检查、文档和安全审计的非阻断项，未在本次改成阻断；它们的绿灯不得被描述为对应检查全部通过。生产密钥、真实模型、Chromadb 功能、容器和现场交互未在本次本地验证。

既有分支保护使用单中括号比较 `release*`，导致预期允许的 release 分支也被拒绝。现使用 Bash 的模式匹配保留 release/*、dev、future 白名单，并检查普通 fix 分支仍返回非零。
