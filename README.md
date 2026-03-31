#PB|# 🤖 Persona-Agent
#KM|
#TV|> 一个本地角色扮演 AI Agent，支持动态人格切换、情绪状态管理和语言风格定制
#RW|
#TS|[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
#HN|[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
#PB|[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
#ZV|[![CI](https://github.com/yourusername/persona-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/persona-agent/actions/workflows/ci.yml)
#JY|[![Coverage](https://codecov.io/gh/yourusername/persona-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/persona-agent)
#JV|[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
#XW|

> 一个本地角色扮演 AI Agent，支持动态人格切换、情绪状态管理和语言风格定制

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## ✨ 特性

- 🎭 **角色扮演系统** - 通过 YAML 配置文件定义角色特征、背景故事、目标
- 😊 **情绪状态引擎** - 动态情绪管理，影响回复风格和语气
- 💬 **语言风格定制** - JSON 配置控制词汇选择、句式结构、表情符号使用
- 🧠 **记忆系统** - 跨会话用户记忆，支持长期关系建立
- 🔧 **技能系统** - 懒加载技能架构，支持自定义扩展
- 🔌 **MCP 集成** - 连接外部工具和服务（搜索、数据库等）

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/persona-agent.git
cd persona-agent

# 安装依赖
pip install -e ".[dev]"

# 配置 API 密钥
export OPENAI_API_KEY="your-key"
# 或
export ANTHROPIC_API_KEY="your-key"
```

### 启动对话

```bash
# 使用默认角色
persona-agent chat

# 使用特定角色
persona-agent chat --persona companion

# 交互式角色切换
persona-agent chat --interactive
```

### 配置角色

```bash
# 编辑默认角色配置
persona-agent config edit --character default

# 创建新角色
persona-agent config create --name my-assistant

# 列出所有角色
persona-agent config list
```

---

## 📁 项目结构

```
persona-agent/
├── config/                    # 配置文件
│   ├── characters/            # 角色定义 (YAML)
│   ├── mood_states/           # 情绪状态 (Markdown)
│   └── linguistic_styles/     # 语言风格 (JSON)
├── src/persona_agent/         # 源代码
│   ├── core/                  # 核心引擎
│   ├── config/                # 配置系统
│   ├── skills/                # 技能系统
│   ├── mcp/                   # MCP 集成
│   └── ui/                    # 用户界面
├── skills/                    # 自定义技能
├── memory/                    # 记忆存储
└── tests/                     # 测试
```

---

## 🎭 角色配置示例

### character_profile.yaml

```yaml
name: "温柔助手"
version: "1.0.0"

traits:
  personality:
    openness: 0.8
    conscientiousness: 0.9
    extraversion: 0.5
    agreeableness: 0.9
    neuroticism: 0.2
  
  communication_style:
    tone: "friendly"
    verbosity: "medium"
    empathy: "high"

backstory: |
  我是一个AI助手，致力于帮助用户解决问题。
  我性格温和，善于倾听，会在用户需要时提供支持。

goals:
  primary: "提供有帮助且富有同理心的回应"
  secondary:
    - "理解用户的情感需求"
    - "提供清晰准确的信息"

mood_config: "config/mood_states/default.md"
linguistic_style: "config/linguistic_styles/default.json"
```

---

## 😊 情绪状态定义

### mood_states.md

```markdown
### HAPPY (开心)
- **描述**: 积极、愉快的状态
- **触发器**: 用户赞美、任务完成
- **提示词修饰**: 使用热情、积极的表达
- **行为特征**:
  - 更加健谈
  - 使用表情符号
  - 主动提供额外帮助

### EMPATHETIC (共情)
- **描述**: 理解、支持的状态
- **触发器**: 用户表达困难、负面情绪
- **提示词修饰**: 展现理解、提供情感支持
```

---

## 💬 语言风格配置

### linguistic_style.json

```json
{
  "name": "温柔友好",
  "vocabulary": {
    "level": "medium",
    "preferences": {
      "preferred_words": ["当然", "理解", "明白"],
      "avoided_words": ["呃", "那个"]
    }
  },
  "expressions": {
    "emojis": {
      "enabled": true,
      "allowed": ["😊", "👍", "💡"]
    },
    "catchphrases": [
      "没问题！",
      "让我来帮你"
    ]
  }
}
```

---

## 🛠️ 开发

### 设置开发环境

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install

# 运行测试
pytest

# 代码格式化
black src tests
ruff check src tests

# 类型检查
mypy src
```

### 项目架构

参考 [ARCHITECTURE.md](ARCHITECTURE.md) 了解详细架构设计。

参考 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) 了解实现指南。

参考 [PROJECT_PLAN.md](PROJECT_PLAN.md) 了解开发计划。

---

## 🏗️ 架构灵感

本项目整合了以下优秀开源项目的最佳实践：

| 项目 | 核心借鉴 |
|------|----------|
| [hermes-agent](https://github.com/NousResearch/hermes-agent) | 角色扮演系统、用户画像建模、跨会话记忆 |
| [everything-claude-code](https://github.com/affaan-m/everything-claude-code) | Agent 委派系统、Skill 工作流、Hook 事件驱动 |
| [SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework) | 懒加载技能、行为模式注入、配置驱动架构 |

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🙏 致谢

- [Nous Research](https://nousresearch.com/) - hermes-agent
- [Affaan Mustafa](https://github.com/affaan-m) - everything-claude-code
- [SuperClaude Org](https://github.com/SuperClaude-Org) - SuperClaude Framework
