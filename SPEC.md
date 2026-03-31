# Persona-Agent 技术规格书 (SPEC)

## 1. 项目概述

### 1.1 目标
构建一个本地角色扮演 AI Agent 应用，支持：
- 动态人格切换
- 情绪状态管理
- 语言风格定制
- 可扩展技能系统
- MCP 工具集成

### 1.2 技术栈
- **语言**: Python 3.11+
- **配置**: YAML, JSON, Markdown
- **数据验证**: Pydantic v2
- **CLI**: Typer + Rich
- **LLM**: OpenAI, Anthropic, 本地模型
- **存储**: SQLite (记忆), Chroma (向量检索)
- **MCP**: Model Context Protocol

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    CLI      │  │    TUI      │  │    Chat Session         │  │
│  │   (Typer)   │  │   (Rich)    │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         核心引擎层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │AgentEngine  │  │PersonaManager│  │    MoodEngine          │  │
│  │             │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │MemoryStore  │  │ContextManager│  │   LinguisticStyle      │  │
│  │             │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         扩展系统层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ SkillRegistry│  │MCPManager   │  │   ToolRegistry         │  │
│  │  (Lazy Load) │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         基础设施层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ ConfigLoader │  │LLMClient    │  │   Storage (SQLite)     │  │
│  │             │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 |
|------|------|
| AgentEngine | 主控制循环，协调各组件 |
| PersonaManager | 角色加载、切换、管理 |
| MoodEngine | 情绪状态跟踪和转换 |
| LinguisticStyle | 语言风格应用和转换 |
| MemoryStore | 对话历史存储和检索 |
| ContextManager | 上下文窗口管理 |
| SkillRegistry | 技能注册和懒加载 |
| MCPManager | MCP 服务器连接管理 |

---

## 3. 配置系统

### 3.1 配置文件格式

#### Character Profile (YAML)

```yaml
name: str                    # 角色名称 (required)
version: str                 # 版本号 (required)

traits:                      # 性格特征
  personality:               # 大五人格模型
    openness: float          # 开放性 (0-1)
    conscientiousness: float # 尽责性 (0-1)
    extraversion: float      # 外向性 (0-1)
    agreeableness: float     # 宜人性 (0-1)
    neuroticism: float       # 神经质 (0-1)
  communication_style:
    tone: str                # friendly/professional/playful/serious
    verbosity: str           # low/medium/high
    empathy: str             # low/medium/high

backstory: str               # 背景故事 (支持多行)

goals:                       # 目标
  primary: str               # 主要目标
  secondary: List[str]       # 次要目标

knowledge_domains: List[str] # 知识领域
limitations: List[str]        # 限制说明

mood_config: str             # 情绪配置文件路径
linguistic_style: str        # 语言风格配置文件路径
```

#### Mood States (Markdown + YAML Frontmatter)

```markdown
---
transitions:
  NEUTRAL:
    - to: HAPPY
      triggers: ["compliment", "success"]
      probability: 0.7
---

### {MOOD_NAME} ({DISPLAY_NAME})
- **描述**: {description}
- **触发器**: {triggers}
- **提示词修饰**: {prompt_modifier}
- **行为特征**:
  - {behavior_1}
  - {behavior_2}
```

#### Linguistic Style (JSON)

```json
{
  "name": str,
  "version": str,
  "vocabulary": {
    "level": "low|medium|high",
    "preferences": {
      "use_technical_terms": bool,
      "explain_jargon": bool,
      "preferred_words": [str],
      "avoided_words": [str]
    }
  },
  "sentence_structure": {
    "average_length": "short|medium|long",
    "complexity": "simple|moderate|complex",
    "patterns": [str]
  },
  "formality": {
    "level": "casual|semi_formal|formal",
    "greeting_style": str,
    "pronoun_usage": str
  },
  "expressions": {
    "emojis": {
      "enabled": bool,
      "frequency": "rare|occasional|frequent",
      "allowed": [str]
    },
    "catchphrases": [str]
  },
  "response_patterns": {
    "greeting": str,
    "acknowledgment": str,
    "clarification": str,
    "help_offer": str
  }
}
```

### 3.2 配置加载优先级

1. 环境变量 (PERSONA_AGENT_*)
2. 项目本地配置 (./.persona-agent/)
3. 用户全局配置 (~/.config/persona-agent/)
4. 默认配置 (包内)

---

## 4. 核心引擎

### 4.1 AgentEngine

```python
class AgentEngine:
    """Agent 主引擎"""
    
    def __init__(self):
        self.persona_manager: PersonaManager
        self.mood_engine: MoodEngine
        self.memory_store: MemoryStore
        self.context_manager: ContextManager
        self.skill_registry: SkillRegistry
        self.mcp_manager: MCPManager
    
    async def chat(self, user_input: str) -> str:
        """处理用户输入并返回回复"""
        # 1. 更新情绪状态
        mood = self.mood_engine.update(user_input)
        
        # 2. 检索相关记忆
        memories = await self.memory_store.retrieve_relevant(user_input)
        
        # 3. 构建系统提示
        system_prompt = self._build_system_prompt(mood, memories)
        
        # 4. 调用 LLM
        response = await self._call_llm(system_prompt, user_input)
        
        # 5. 应用语言风格
        styled_response = self._apply_linguistic_style(response)
        
        # 6. 存储对话
        await self.memory_store.store(user_input, styled_response)
        
        return styled_response
```

### 4.2 PersonaManager

```python
class PersonaManager:
    """角色管理器"""
    
    def load_persona(self, config_path: Path) -> Persona:
        """从配置文件加载角色"""
        
    def switch_persona(self, persona_id: str) -> None:
        """切换当前角色"""
        
    def get_current_persona(self) -> Persona:
        """获取当前角色"""
        
    def list_personas(self) -> List[PersonaInfo]:
        """列出可用角色"""
```

### 4.3 MoodEngine

```python
class MoodEngine:
    """情绪引擎"""
    
    def __init__(self, config_path: Path):
        self.current_mood: MoodState
        self.mood_history: List[MoodTransition]
        self.transitions: Dict[MoodState, List[MoodTransitionRule]]
    
    def update(self, trigger: str, context: Dict) -> MoodState:
        """基于触发器更新情绪状态"""
        
    def get_prompt_modifier(self) -> str:
        """获取当前情绪对提示词的修饰"""
```

### 4.4 MemoryStore

```python
class MemoryStore:
    """记忆存储"""
    
    def __init__(self, db_path: Path):
        self.db: aiosqlite.Connection
    
    async def store(self, user_msg: str, assistant_msg: str) -> None:
        """存储对话"""
        
    async def retrieve_relevant(
        self, 
        query: str, 
        limit: int = 5
    ) -> List[Memory]:
        """检索相关记忆"""
        
    async def get_conversation_history(
        self, 
        session_id: str,
        limit: int = 20
    ) -> List[Message]:
        """获取会话历史"""
```

---

## 5. 技能系统

### 5.1 技能基类

```python
class BaseSkill(ABC):
    """技能基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称"""
        
    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述"""
        
    @property
    def triggers(self) -> List[str]:
        """触发词列表"""
        return []
    
    @property
    def required_tools(self) -> List[str]:
        """需要的工具列表"""
        return []
    
    @abstractmethod
    async def can_execute(self, context: SkillContext) -> bool:
        """判断是否可以执行"""
        
    @abstractmethod
    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        """执行技能"""
```

### 5.2 技能注册表 (懒加载)

```python
class SkillRegistry:
    """技能注册表 - 懒加载模式"""
    
    def __init__(self):
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}
        self._instances: Dict[str, BaseSkill] = {}
        self._metadata: Dict[str, SkillMetadata] = {}
    
    def register(
        self, 
        skill_id: str, 
        skill_class: Type[BaseSkill],
        metadata: SkillMetadata
    ) -> None:
        """注册技能（不实例化）"""
        self._skill_classes[skill_id] = skill_class
        self._metadata[skill_id] = metadata
    
    def get(self, skill_id: str) -> BaseSkill:
        """获取技能实例（延迟实例化）"""
        if skill_id not in self._instances:
            if skill_id not in self._skill_classes:
                raise SkillNotFoundError(skill_id)
            self._instances[skill_id] = self._skill_classes[skill_id]()
        return self._instances[skill_id]
    
    def discover_skills(self, skills_dir: Path) -> None:
        """发现并注册目录中的技能"""
```

### 5.3 内置技能

| 技能 | 功能 |
|------|------|
| chat | 基础对话 |
| memory_recall | 记忆检索 |
| persona_switch | 角色切换 |
| mood_check | 情绪查询 |
| tool_call | 工具调用 |

---

## 6. MCP 集成

### 6.1 MCPManager

```python
class MCPManager:
    """MCP 服务器管理器"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.tool_registry: ToolRegistry
    
    async def connect_server(self, config: MCPServerConfig) -> None:
        """连接 MCP 服务器"""
        
    async def disconnect_server(self, server_name: str) -> None:
        """断开 MCP 服务器"""
        
    async def execute_tool(
        self, 
        tool_name: str, 
        params: Dict[str, Any]
    ) -> ToolResult:
        """执行 MCP 工具"""
        
    def list_available_tools(self) -> List[ToolInfo]:
        """列出可用工具"""
```

### 6.2 MCP 配置

```json
{
  "mcpServers": {
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp@0.1.2"],
      "env": {
        "TAVILY_API_KEY": "${TAVILY_API_KEY}"
      }
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

---

## 7. 用户界面

### 7.1 CLI 命令

```bash
# 对话
persona-agent chat [OPTIONS]
  --persona TEXT          选择角色
  --interactive           交互式角色切换
  --session TEXT          会话ID

# 配置管理
persona-agent config [COMMAND]
  list                    列出角色
  create --name TEXT      创建角色
  edit --character TEXT   编辑角色
  validate                验证配置

# 记忆管理
persona-agent memory [COMMAND]
  search TEXT             搜索记忆
  export --output PATH    导出记忆
  clear                   清空记忆

# 技能管理
persona-agent skill [COMMAND]
  list                    列出技能
  enable --skill TEXT     启用技能
  disable --skill TEXT    禁用技能

# MCP 管理
persona-agent mcp [COMMAND]
  list                    列出服务器
  add --config PATH       添加服务器
  remove --name TEXT      移除服务器

# 系统
persona-agent doctor      诊断问题
persona-agent version     显示版本
```

### 7.2 TUI 界面

- 实时对话显示
- 打字机效果
- 角色/情绪状态指示
- 会话历史浏览
- 快捷键支持

---

## 8. 数据模型

### 8.1 核心模型

```python
class Persona(BaseModel):
    """角色模型"""
    id: str
    name: str
    version: str
    traits: PersonalityTraits
    backstory: str
    goals: Goals
    knowledge_domains: List[str]
    limitations: List[str]
    mood_config: Path
    linguistic_style: Path

class MoodState(BaseModel):
    """情绪状态模型"""
    name: str
    display_name: str
    description: str
    triggers: List[str]
    prompt_modifier: str
    behaviors: List[str]

class Memory(BaseModel):
    """记忆模型"""
    id: str
    session_id: str
    timestamp: datetime
    user_message: str
    assistant_message: str
    embedding: Optional[List[float]]

class SkillMetadata(BaseModel):
    """技能元数据"""
    id: str
    name: str
    description: str
    version: str
    author: str
    tags: List[str]
    dependencies: List[str]
```

---

## 9. 错误处理

### 9.1 错误类型

```python
class PersonaAgentError(Exception):
    """基础错误"""
    pass

class ConfigError(PersonaAgentError):
    """配置错误"""
    pass

class PersonaNotFoundError(PersonaAgentError):
    """角色未找到"""
    pass

class SkillNotFoundError(PersonaAgentError):
    """技能未找到"""
    pass

class MCPConnectionError(PersonaAgentError):
    """MCP 连接错误"""
    pass

class LLMError(PersonaAgentError):
    """LLM 调用错误"""
    pass
```

---

## 10. 性能要求

### 10.1 响应时间

| 操作 | 目标响应时间 |
|------|-------------|
| 角色切换 | < 100ms |
| 配置加载 | < 200ms |
| 记忆检索 | < 500ms |
| LLM 首次响应 | < 2s |

### 10.2 资源使用

- 内存: < 512MB (基础运行)
- 存储: < 100MB (不含记忆数据)
- CPU: 支持异步并发

---

## 11. 安全考虑

- API 密钥存储在环境变量或密钥管理服务
- MCP 工具执行前确认
- 记忆数据本地存储，不上传
- 配置文件验证和沙箱

---

## 12. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2024-XX-XX | 初始版本 |
