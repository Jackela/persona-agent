# Persona-Agent 项目计划

## 项目概述
构建一个本地角色扮演 Agent 应用，支持动态人格切换、情绪状态管理、语言风格模拟，具备可扩展的技能系统和 MCP 集成能力。

---

## 📋 任务清单

### Phase 1: 项目初始化与核心框架
- [ ] 1.1 创建项目结构和基础配置
  - 创建 `src/` 目录结构
  - 设置 `pyproject.toml` / `setup.py`
  - 配置开发环境 (pytest, black, ruff)
  - 创建基础 `.gitignore`

- [ ] 1.2 实现配置系统基础
  - 创建 `config/schemas/` 目录
  - 实现 Pydantic 模型 (Character, Mood, LinguisticStyle)
  - 实现 YAML/JSON 配置加载器
  - 添加配置验证和错误处理

- [ ] 1.3 实现 LLM 客户端抽象
  - 创建 `utils/llm_client.py`
  - 支持 OpenAI API 格式
  - 支持多模型切换
  - 实现流式响应

- [ ] 1.4 实现基础 CLI 界面
  - 使用 Typer 创建命令行入口
  - 实现 `persona-agent chat` 命令
  - 添加基础日志输出

### Phase 2: 角色扮演核心系统
- [ ] 2.1 实现角色管理器
  - 创建 `core/persona_manager.py`
  - 实现角色加载/切换逻辑
  - 创建默认角色模板
  - 实现角色缓存机制

- [ ] 2.2 实现情绪引擎
  - 创建 `core/mood_engine.py`
  - 解析 mood_states.md 格式
  - 实现情绪状态转换逻辑
  - 情绪对提示词的影响

- [ ] 2.3 实现语言风格系统
  - 创建 `core/linguistic_style.py`
  - 解析 linguistic_style.json
  - 实现文本风格转换器
  - 风格-情绪联动

- [ ] 2.4 集成角色系统到对话流程
  - 修改对话循环，注入角色上下文
  - 根据情绪动态调整系统提示
  - 应用语言风格到回复

### Phase 3: 记忆与上下文管理
- [ ] 3.1 实现记忆存储
  - 创建 `core/memory_store.py`
  - 使用 SQLite 存储对话历史
  - 实现记忆摘要生成
  - 添加记忆检索接口

- [ ] 3.2 实现上下文管理器
  - 创建 `core/context_manager.py`
  - 管理对话上下文窗口
  - 实现上下文压缩策略
  - 长期记忆 vs 短期记忆

- [ ] 3.3 实现用户画像
  - 用户偏好学习
  - 跨会话记忆保持
  - 用户特定配置

### Phase 4: 技能系统 (懒加载)
- [ ] 4.1 实现技能基础框架
  - 创建 `skills/base_skill.py`
  - 定义 Skill 抽象基类
  - 实现技能元数据模型

- [ ] 4.2 实现技能注册表 (懒加载)
  - 创建 `skills/registry.py`
  - 实现延迟实例化机制
  - 技能发现和自动注册
  - 技能依赖管理

- [ ] 4.3 实现内置技能
  - `chat` - 基础对话
  - `memory_recall` - 记忆检索
  - `persona_switch` - 角色切换
  - `mood_check` - 情绪查询

- [ ] 4.4 实现技能加载器
  - 从 `skills/` 目录加载自定义技能
  - 热重载支持
  - 技能版本管理

### Phase 5: MCP 集成
- [ ] 5.1 实现 MCP 服务器管理器
  - 创建 `mcp/server_manager.py`
  - MCP 连接配置
  - 服务器生命周期管理

- [ ] 5.2 实现工具注册表
  - 创建 `mcp/tool_registry.py`
  - 工具发现和注册
  - 工具调用封装

- [ ] 5.3 集成 MCP 工具到对话
  - 工具可用性提示
  - 工具调用执行
  - 结果处理与展示

### Phase 6: 高级功能与优化
- [ ] 6.1 实现 TUI 界面
  - 使用 Rich 美化输出
  - 实现实时打字效果
  - 对话历史浏览

- [ ] 6.2 实现会话管理
  - 会话保存/加载
  - 会话列表
  - 会话导出

- [ ] 6.3 配置热重载
  - 文件监听
  - 配置变更自动应用
  - 角色切换无需重启

- [ ] 6.4 性能优化
  - 配置缓存
  - 记忆索引优化
  - 异步处理

### Phase 7: 测试与文档
- [ ] 7.1 单元测试
  - 配置系统测试
  - 角色管理器测试
  - 情绪引擎测试

- [ ] 7.2 集成测试
  - 端到端对话测试
  - MCP 集成测试

- [ ] 7.3 文档编写
  - API 文档
  - 配置指南
  - 技能开发指南
  - 使用教程

---

## 🎯 优先级调整

### 必须完成 (P0)
- 1.1, 1.2, 1.3, 1.4 - 项目基础
- 2.1, 2.2, 2.3, 2.4 - 角色扮演核心

### 高优先级 (P1)
- 3.1, 3.2 - 记忆系统
- 4.1, 4.2, 4.3 - 技能系统基础
- 7.1 - 核心测试

### 中优先级 (P2)
- 3.3 - 用户画像
- 4.4 - 自定义技能
- 5.1, 5.2, 5.3 - MCP 集成
- 6.1 - TUI

### 低优先级 (P3)
- 6.2, 6.3, 6.4 - 高级功能
- 7.2, 7.3 - 完整测试和文档

---

## 📁 文件创建计划

### 配置文件
```
config/
├── characters/
│   └── default.yaml
├── mood_states/
│   └── default.md
├── linguistic_styles/
│   └── default.json
└── system_goal.txt
```

### 源代码文件
```
src/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── agent_engine.py
│   ├── persona_manager.py
│   ├── mood_engine.py
│   ├── memory_store.py
│   └── context_manager.py
├── config/
│   ├── __init__.py
│   ├── loader.py
│   ├── validator.py
│   └── schemas/
│       ├── __init__.py
│       ├── character.py
│       ├── mood.py
│       └── linguistic.py
├── skills/
│   ├── __init__.py
│   ├── base_skill.py
│   ├── registry.py
│   └── builtin/
│       ├── __init__.py
│       ├── chat.py
│       ├── memory_recall.py
│       └── persona_switch.py
├── mcp/
│   ├── __init__.py
│   ├── server_manager.py
│   └── tool_registry.py
├── ui/
│   ├── __init__.py
│   └── cli.py
└── utils/
    ├── __init__.py
    ├── llm_client.py
    └── logger.py
```

### 测试文件
```
tests/
├── __init__.py
├── conftest.py
├── test_config.py
├── test_persona_manager.py
├── test_mood_engine.py
└── test_skills.py
```

---

## 🔄 依赖关系

```
config/schemas  →  config/loader  →  core/*
                      ↓
               utils/llm_client  →  core/agent_engine
                      ↓
                    ui/cli
```

技能系统和 MCP 是相对独立的模块，可以在核心稳定后添加。
