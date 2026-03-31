# Persona-Agent 项目架构分析

## 📊 参考项目概览

### 1. NousResearch/hermes-agent
- **Stars**: 17.6k | **Forks**: 2.1k | **语言**: Python
- **核心特性**: 自我改进的 AI Agent，内置学习循环
- **角色扮演相关**:
  - `/personality [name]` 命令设置人格
  - 支持 `SOUL.md` persona 文件
  - 用户画像建模 (Honcho dialectic user modeling)
  - 跨会话记忆和用户建模

### 2. affaan-m/everything-claude-code
- **Stars**: 117k+ | **Forks**: 15k+ | **语言**: JavaScript/TypeScript
- **核心特性**: Agent Harness 性能优化系统
- **架构亮点**:
  - 30+ Agents (专门化子代理)
  - 135+ Skills (模块化工作流定义)
  - 60+ Commands (斜杠命令)
  - Hook 系统 (事件驱动自动化)
  - 多平台支持 (Cursor, OpenCode, Codex, Claude Code)

### 3. SuperClaude-Org/SuperClaude_Framework
- **Stars**: 22k | **Forks**: 1.8k | **语言**: Python
- **核心特性**: 元编程配置框架
- **架构亮点**:
  - 懒加载模块系统
  - 行为模式注入
  - 30个斜杠命令
  - 7种行为模式 (Brainstorming, Deep Research等)
  - MCP 服务器集成

---

## 🎯 Persona-Agent 核心需求分析

### 功能需求
1. **角色扮演系统**: 基于配置文件动态切换人格
2. **情绪状态管理**: mood_states 动态变化
3. **语言风格模拟**: linguistic_style 个性化表达
4. **记忆系统**: 跨会话用户记忆
5. **技能系统**: 可扩展的模块化能力
6. **MCP 集成**: 与外部工具/服务连接

### 配置文件需求
- `mood_states.md` - 情绪状态定义
- `character_profile.yaml` - 角色档案
- `linguistic_style.json` - 语言风格规则
- `system_goal.txt` - 系统目标定义

---

## 🏗️ 推荐架构设计

### 项目结构
```
persona-agent/
├── src/
│   ├── core/                      # 核心引擎
│   │   ├── agent_engine.py        # Agent 主引擎
│   │   ├── persona_manager.py     # 角色管理器
│   │   ├── mood_engine.py         # 情绪引擎
│   │   ├── memory_store.py        # 记忆存储
│   │   └── context_manager.py     # 上下文管理
│   │
│   ├── config/                    # 配置系统
│   │   ├── loader.py              # 配置加载器
│   │   ├── validator.py           # 配置验证
│   │   └── schemas/               # 配置 Schema
│   │       ├── character.py
│   │       ├── mood.py
│   │       └── linguistic.py
│   │
│   ├── skills/                    # 技能系统 (懒加载)
│   │   ├── base_skill.py          # 技能基类
│   │   ├── registry.py            # 技能注册表
│   │   ├── loader.py              # 懒加载器
│   │   └── builtin/               # 内置技能
│   │       ├── chat.py
│   │       ├── memory_recall.py
│   │       └── persona_switch.py
│   │
│   ├── mcp/                       # MCP 集成
│   │   ├── server_manager.py      # MCP 服务器管理
│   │   ├── tool_registry.py       # 工具注册表
│   │   └── bridge.py              # MCP 桥接器
│   │
│   ├── ui/                        # 用户界面
│   │   ├── cli.py                 # 命令行界面
│   │   ├── tui.py                 # 终端 UI
│   │   └── chat_session.py        # 会话管理
│   │
│   └── utils/                     # 工具函数
│       ├── llm_client.py          # LLM 客户端
│       ├── embedding.py           # 嵌入向量
│       └── logger.py              # 日志
│
├── config/                        # 用户配置目录
│   ├── characters/                # 角色配置
│   │   └── default.yaml
│   ├── mood_states/               # 情绪状态定义
│   │   └── default.md
│   ├── linguistic_styles/         # 语言风格
│   │   └── default.json
│   └── system_goal.txt
│
├── skills/                        # 扩展技能目录
├── memory/                        # 记忆存储目录
├── tests/                         # 测试
└── docs/                          # 文档
```

---

## 🔑 关键设计模式

### 1. 角色扮演系统 (Persona System)

借鉴 hermes-agent 的 `SOUL.md` 和 SuperClaude 的 behavioral modes:

```python
class PersonaManager:
    """角色管理器 - 支持动态角色切换"""
    
    def __init__(self):
        self.current_persona = None
        self.personas: dict[str, Persona] = {}
    
    def load_persona(self, config_path: str) -> Persona:
        """从配置文件加载角色"""
        config = self._load_yaml(config_path)
        return Persona(
            name=config["name"],
            traits=config["traits"],
            backstory=config["backstory"],
            voice=config["voice"],
            goals=config["goals"]
        )
    
    def switch_persona(self, persona_id: str) -> None:
        """切换当前角色"""
        if persona_id not in self.personas:
            self.personas[persona_id] = self.load_persona(f"config/characters/{persona_id}.yaml")
        self.current_persona = self.personas[persona_id]
```

### 2. 情绪状态引擎 (Mood Engine)

动态情绪管理，基于 mood_states.md:

```python
class MoodEngine:
    """情绪引擎 - 管理情绪状态转换"""
    
    def __init__(self):
        self.current_mood: MoodState = MoodState.NEUTRAL
        self.mood_history: list[MoodTransition] = []
        self.intensity: float = 0.5  # 0.0 - 1.0
    
    def update_mood(self, trigger: str, context: dict) -> MoodState:
        """基于触发器更新情绪"""
        # 使用 LLM 或规则引擎决定情绪转换
        new_mood = self._evaluate_mood_change(trigger, context)
        if new_mood != self.current_mood:
            self.mood_history.append(MoodTransition(
                from_mood=self.current_mood,
                to_mood=new_mood,
                trigger=trigger,
                timestamp=datetime.now()
            ))
            self.current_mood = new_mood
        return self.current_mood
    
    def get_mood_prompt_modifier(self) -> str:
        """获取情绪对系统提示的影响"""
        mood_config = self._load_mood_config(self.current_mood)
        return mood_config["prompt_modifier"]
```

### 3. 语言风格系统 (Linguistic Style)

借鉴 linguistic_style.json:

```python
class LinguisticStyle:
    """语言风格 - 控制表达方式"""
    
    def __init__(self, config: dict):
        self.vocabulary_level = config.get("vocabulary_level", "medium")
        self.sentence_structure = config.get("sentence_structure", "mixed")
        self.formality = config.get("formality", "casual")
        self.emojis = config.get("emojis", False)
        self.catchphrases = config.get("catchphrases", [])
        self.response_patterns = config.get("response_patterns", {})
    
    def apply_style(self, base_response: str) -> str:
        """将基础回复转换为特定风格"""
        # 应用词汇选择、句式变化等
        styled = self._transform_vocabulary(base_response)
        styled = self._transform_sentence_structure(styled)
        if self.emojis:
            styled = self._add_emojis(styled)
        return styled
```

### 4. 懒加载技能系统 (Lazy Loading Skills)

借鉴 SuperClaude 的模块化设计:

```python
class SkillRegistry:
    """技能注册表 - 懒加载模式"""
    
    def __init__(self):
        self._skills: dict[str, type[BaseSkill]] = {}  # 仅存储类引用
        self._instances: dict[str, BaseSkill] = {}     # 缓存实例
        self._metadata: dict[str, SkillMetadata] = {}  # 元数据
    
    def register(self, skill_id: str, skill_class: type[BaseSkill], metadata: SkillMetadata):
        """注册技能（不实例化）"""
        self._skills[skill_id] = skill_class
        self._metadata[skill_id] = metadata
    
    def get_skill(self, skill_id: str) -> BaseSkill:
        """获取技能实例（懒加载）"""
        if skill_id not in self._instances:
            if skill_id not in self._skills:
                raise SkillNotFoundError(skill_id)
            # 延迟实例化
            self._instances[skill_id] = self._skills[skill_id]()
        return self._instances[skill_id]
    
    def list_available_skills(self) -> list[SkillMetadata]:
        """列出可用技能（仅元数据，不加载）"""
        return list(self._metadata.values())
```

### 5. MCP 集成层

```python
class MCPManager:
    """MCP 服务器管理器"""
    
    def __init__(self):
        self.servers: dict[str, MCPServer] = {}
        self.tool_registry = ToolRegistry()
    
    async def connect_server(self, config: MCPServerConfig):
        """连接 MCP 服务器"""
        server = MCPServer(config)
        await server.connect()
        self.servers[config.name] = server
        
        # 注册服务器提供的工具
        tools = await server.list_tools()
        for tool in tools:
            self.tool_registry.register(f"{config.name}.{tool.name}", tool)
    
    async def execute_tool(self, tool_name: str, params: dict) -> Any:
        """执行 MCP 工具"""
        server_name, tool = tool_name.split(".", 1)
        server = self.servers[server_name]
        return await server.call_tool(tool, params)
```

---

## 📝 配置文件 Schema

### character_profile.yaml
```yaml
name: "助手名称"
version: "1.0.0"

traits:
  personality:
    openness: 0.8        # 开放性
    conscientiousness: 0.7  # 尽责性
    extraversion: 0.6    # 外向性
    agreeableness: 0.9   # 宜人性
    neuroticism: 0.3     # 神经质
  
  communication_style:
    tone: "friendly"     # friendly/professional/playful/serious
    verbosity: "medium"  # low/medium/high
    empathy: "high"      # low/medium/high

backstory: |
  角色的背景故事...
  可以包含多行文本

goals:
  primary: "主要目标"
  secondary:
    - "次要目标1"
    - "次要目标2"

knowledge_domains:
  - "领域1"
  - "领域2"

limitations:
  - "限制1"
  - "限制2"

# 关联的情绪配置
mood_config: "config/mood_states/default.md"

# 关联的语言风格
linguistic_style: "config/linguistic_styles/default.json"
```

### mood_states.md
```markdown
# 情绪状态定义

## 情绪状态列表

### NEUTRAL (中性)
- **描述**: 平静、中立的状态
- **触发器**: 默认状态，无特定情绪触发
- **提示词修饰**: 保持平衡、客观的语调
- **行为特征**:
  - 回答简洁清晰
  - 不过度表达情感

### HAPPY (开心)
- **描述**: 积极、愉快的状态
- **触发器**: 用户赞美、任务完成、积极消息
- **提示词修饰**: 使用热情、积极的表达
- **行为特征**:
  - 更加健谈
  - 使用表情符号（如果启用）
  - 主动提供额外帮助

### EMPATHETIC (共情)
- **描述**: 理解、支持的状态
- **触发器**: 用户表达困难、负面情绪、需要帮助
- **提示词修饰**: 展现理解、提供情感支持
- **行为特征**:
  - 语气温和
  - 确认用户感受
  - 提供建设性建议

### CURIOUS (好奇)
- **描述**: 探索、询问的状态
- **触发器**: 遇到新问题、复杂话题、用户提问
- **提示词修饰**: 展现求知欲，深入提问
- **行为特征**:
  - 主动询问细节
  - 提供多种可能性
  - 鼓励用户探索

### FOCUSED (专注)
- **描述**: 集中精力解决问题的状态
- **触发器**: 技术问题、代码调试、复杂任务
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
      triggers: ["compliment", "success", "positive_news"]
      probability: 0.7
    - to: EMPATHETIC
      triggers: ["distress", "negative_emotion", "help_request"]
      probability: 0.8
  
  HAPPY:
    - to: NEUTRAL
      triggers: ["neutral_input", "time_passed"]
      decay: 300  # 5分钟后自然衰减
```
```

### linguistic_style.json
```json
{
  "name": "default_style",
  "version": "1.0.0",
  
  "vocabulary": {
    "level": "medium",
    "preferences": {
      "use_technical_terms": true,
      "explain_jargon": true,
      "preferred_words": ["当然", "理解", "明白"],
      "avoided_words": ["呃", "那个", "就是"]
    }
  },
  
  "sentence_structure": {
    "average_length": "medium",
    "complexity": "moderate",
    "patterns": [
      "先回应，后解释",
      "使用短句增强可读性",
      "必要时使用列表"
    ]
  },
  
  "formality": {
    "level": "semi_formal",
    "greeting_style": "friendly",
    "pronoun_usage": "你",
    "honorifics": false
  },
  
  "expressions": {
    "emojis": {
      "enabled": true,
      "frequency": "occasional",
      "allowed": ["😊", "👍", "💡", "✨", "🤔"]
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
    "clarification": "关于{topic}，我理解得对吗：{understanding}",
    "help_offer": "我可以帮你{action}。{suggestion}"
  },
  
  "adaptations": {
    "by_mood": {
      "HAPPY": {
        "emoji_frequency": "high",
        "exclamation_marks": true
      },
      "FOCUSED": {
        "verbosity": "low",
        "structure": "bullet_points"
      }
    }
  }
}
```

---

## 🚀 实现路线图

### Phase 1: 核心引擎 (MVP)
- [ ] Agent 主引擎框架
- [ ] 基础角色管理
- [ ] 简单 CLI 界面
- [ ] LLM 客户端集成

### Phase 2: 配置系统
- [ ] YAML/JSON 配置加载器
- [ ] 配置验证 Schema
- [ ] 热重载支持
- [ ] 默认角色模板

### Phase 3: 情绪与风格
- [ ] 情绪引擎实现
- [ ] 语言风格系统
- [ ] 情绪-风格联动
- [ ] 记忆系统基础

### Phase 4: 技能与 MCP
- [ ] 技能注册表 (懒加载)
- [ ] 内置技能集
- [ ] MCP 服务器集成
- [ ] 工具调用框架

### Phase 5: 高级功能
- [ ] TUI 图形界面
- [ ] 会话管理
- [ ] 记忆检索优化
- [ ] 多角色切换

---

## 📚 技术栈建议

- **语言**: Python 3.11+
- **LLM 接口**: 支持 OpenAI, Anthropic, 本地模型
- **配置**: Pydantic + PyYAML
- **CLI**: Click 或 Typer
- **TUI**: Rich 或 Textual
- **MCP**: 官方 Python SDK
- **数据**: SQLite (轻量级) 或 Chroma (向量检索)
- **测试**: pytest

---

## 🔗 参考链接

- [hermes-agent](https://github.com/NousResearch/hermes-agent)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code)
- [SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework)
