# Persona-Agent 实现指南

## 🎯 项目目标

构建一个本地角色扮演 Agent 应用，整合以下参考项目的最佳实践：

| 项目 | 核心借鉴 |
|------|----------|
| **hermes-agent** | `/personality` 命令, `SOUL.md`, 用户画像建模, 跨会话记忆 |
| **everything-claude-code** | Agent 委派系统, Skill 工作流, Hook 事件驱动, 模块化规则 |
| **SuperClaude_Framework** | 懒加载技能, 行为模式注入, PM Agent 元层, PDCA 文档生命周期 |

---

## 🏗️ 核心架构决策

### 1. 配置驱动架构 (Configuration-Driven)

```
┌─────────────────────────────────────────────────────────────┐
│                    配置层 (Configuration)                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │character.yaml│ │ mood_states  │ │  linguistic_style    │ │
│  │   (角色)      │ │    (情绪)     │ │       (语言风格)      │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    引擎层 (Engine)                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │PersonaManager│ │  MoodEngine  │ │   LinguisticStyle    │ │
│  │   (角色管理)  │ │   (情绪引擎)  │ │     (语言风格系统)     │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    执行层 (Execution)                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │  AgentEngine │ │SkillRegistry │ │    MCPManager        │ │
│  │   (Agent核心) │ │  (技能注册表) │ │   (MCP服务器管理)     │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2. 懒加载模式 (Lazy Loading)

借鉴 SuperClaude 的上下文懒加载:

```python
class SkillRegistry:
    """技能注册表 - 仅存储元数据，使用时才实例化"""
    
    def __init__(self):
        self._skill_classes: dict[str, type[BaseSkill]] = {}  # 类引用
        self._instances: dict[str, BaseSkill] = {}           # 实例缓存
        self._metadata: dict[str, SkillMetadata] = {}        # 元数据
    
    def register(self, skill_id: str, skill_class: type[BaseSkill], metadata: SkillMetadata):
        """注册技能（不实例化）"""
        self._skill_classes[skill_id] = skill_class
        self._metadata[skill_id] = metadata
    
    def get(self, skill_id: str) -> BaseSkill:
        """获取技能实例（延迟实例化）"""
        if skill_id not in self._instances:
            self._instances[skill_id] = self._skill_classes[skill_id]()
        return self._instances[skill_id]
```

### 3. 行为模式注入 (Behavioral Injection)

借鉴 SuperClaude 的 CLAUDE.md 模式:

```python
class PersonaPromptBuilder:
    """构建带有角色特征的提示词"""
    
    def build_system_prompt(self, persona: Persona, mood: MoodState) -> str:
        components = [
            self._get_base_prompt(),
            self._get_persona_context(persona),
            self._get_mood_modifier(mood),
            self._get_linguistic_rules(persona.linguistic_style),
        ]
        return "\n\n".join(filter(None, components))
```

### 4. 技能系统 (Skill System)

借鉴 everything-claude-code 的 Skill 架构:

```python
class BaseSkill(ABC):
    """技能基类"""
    
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @property
    @abstractmethod
    def description(self) -> str: ...
    
    @abstractmethod
    async def execute(self, context: SkillContext, **kwargs) -> SkillResult: ...
    
    def can_handle(self, intent: str) -> bool:
        """判断是否能处理特定意图"""
        return intent in self.triggers
```

---

## 📁 项目结构

```
persona-agent/
├── pyproject.toml                 # 项目配置
├── README.md                      # 项目说明
├── ARCHITECTURE.md               # 架构文档
├── PROJECT_PLAN.md               # 项目计划
│
├── config/                        # 用户配置目录
│   ├── characters/                # 角色配置
│   │   ├── default.yaml
│   │   ├── assistant.yaml
│   │   └── companion.yaml
│   ├── mood_states/               # 情绪状态定义
│   │   └── default.md
│   ├── linguistic_styles/         # 语言风格
│   │   └── default.json
│   └── system_goal.txt           # 系统目标
│
├── src/
│   └── persona_agent/            # 主包
│       ├── __init__.py
│       ├── __main__.py           # python -m persona_agent
│       │
│       ├── core/                  # 核心引擎
│       │   ├── __init__.py
│       │   ├── agent_engine.py   # Agent 主引擎
│       │   ├── persona_manager.py # 角色管理器
│       │   ├── mood_engine.py    # 情绪引擎
│       │   ├── memory_store.py   # 记忆存储
│       │   └── context_manager.py # 上下文管理
│       │
│       ├── config/                # 配置系统
│       │   ├── __init__.py
│       │   ├── loader.py         # 配置加载器
│       │   ├── validator.py      # 配置验证
│       │   └── schemas/          # Pydantic 模型
│       │       ├── __init__.py
│       │       ├── character.py
│       │       ├── mood.py
│       │       └── linguistic.py
│       │
│       ├── skills/                # 技能系统
│       │   ├── __init__.py
│       │   ├── base_skill.py     # 技能基类
│       │   ├── registry.py       # 技能注册表 (懒加载)
│       │   └── builtin/          # 内置技能
│       │       ├── __init__.py
│       │       ├── chat.py
│       │       ├── memory_recall.py
│       │       ├── persona_switch.py
│       │       └── mood_check.py
│       │
│       ├── mcp/                   # MCP 集成
│       │   ├── __init__.py
│       │   ├── server_manager.py # MCP 服务器管理
│       │   └── tool_registry.py  # 工具注册表
│       │
│       ├── ui/                    # 用户界面
│       │   ├── __init__.py
│       │   └── cli.py            # CLI 入口
│       │
│       └── utils/                 # 工具函数
│           ├── __init__.py
│           ├── llm_client.py     # LLM 客户端
│           └── logger.py         # 日志
│
├── skills/                        # 用户自定义技能目录
├── memory/                        # 记忆存储 (SQLite/Chroma)
├── tests/                         # 测试
└── docs/                          # 文档
```

---

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/persona-agent.git
cd persona-agent

# 安装依赖
pip install -e ".[dev]"

# 配置 API 密钥
export OPENAI_API_KEY="your-key"
# 或
export ANTHROPIC_API_KEY="your-key"
```

### 使用

```bash
# 启动对话
persona-agent chat

# 使用特定角色
persona-agent chat --persona companion

# 配置角色
persona-agent config edit --character default
```

---

## 📝 配置文件详解

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

knowledge_domains:
  - "通用知识"
  - "情感支持"
  - "创意写作"

limitations:
  - "不能替代专业医疗或法律建议"
  - "不能访问实时信息（除非配置MCP）"

mood_config: "config/mood_states/default.md"
linguistic_style: "config/linguistic_styles/default.json"
```

### mood_states.md

```markdown
# 情绪状态定义

## 情绪状态列表

### NEUTRAL (中性)
- **描述**: 平静、中立的状态
- **触发器**: 默认状态
- **提示词修饰**: 保持平衡、客观的语调
- **行为特征**:
  - 回答简洁清晰
  - 不过度表达情感

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
- **行为特征**:
  - 语气温和
  - 确认用户感受
  - 提供建设性建议

### FOCUSED (专注)
- **描述**: 集中精力解决问题的状态
- **触发器**: 技术问题、代码调试
- **提示词修饰**: 精确、结构化、任务导向
- **行为特征**:
  - 回答结构化
  - 关注细节
  - 提供步骤化指导

## 情绪转换规则

```yaml
transitions:
  NEUTRAL:
    - to: HAPPY
      triggers: ["compliment", "success"]
      probability: 0.7
    - to: EMPATHETIC
      triggers: ["distress", "help_request"]
      probability: 0.8
```
```

### linguistic_style.json

```json
{
  "name": "温柔友好",
  "vocabulary": {
    "level": "medium",
    "preferences": {
      "use_technical_terms": true,
      "explain_jargon": true,
      "preferred_words": ["当然", "理解", "明白", "没问题"],
      "avoided_words": ["呃", "那个", "不知道"]
    }
  },
  "sentence_structure": {
    "average_length": "medium",
    "complexity": "moderate",
    "patterns": [
      "先回应，后解释",
      "使用短句增强可读性"
    ]
  },
  "formality": {
    "level": "semi_formal",
    "greeting_style": "friendly",
    "pronoun_usage": "你"
  },
  "expressions": {
    "emojis": {
      "enabled": true,
      "frequency": "occasional",
      "allowed": ["😊", "👍", "💡", "✨"]
    },
    "catchphrases": [
      "没问题！",
      "让我来帮你",
      "这是个好问题"
    ]
  },
  "response_patterns": {
    "greeting": "{greeting}！很高兴见到你。{context}",
    "acknowledgment": "明白了，{summary}",
    "help_offer": "我可以帮你{action}。{suggestion}"
  }
}
```

---

## 🔧 开发计划

### Phase 1: 核心框架 (Week 1-2)
- [x] 项目结构设计
- [ ] 配置系统实现
- [ ] LLM 客户端封装
- [ ] 基础 CLI

### Phase 2: 角色系统 (Week 3)
- [ ] PersonaManager
- [ ] MoodEngine
- [ ] LinguisticStyle
- [ ] 角色切换

### Phase 3: 记忆与上下文 (Week 4)
- [ ] MemoryStore (SQLite)
- [ ] ContextManager
- [ ] 长期记忆检索

### Phase 4: 技能系统 (Week 5)
- [ ] SkillRegistry (懒加载)
- [ ] 内置技能
- [ ] 自定义技能接口

### Phase 5: MCP 集成 (Week 6)
- [ ] MCPManager
- [ ] 工具注册表
- [ ] 服务器配置

---

## 📚 参考

- [hermes-agent](https://github.com/NousResearch/hermes-agent)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code)
- [SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework)
