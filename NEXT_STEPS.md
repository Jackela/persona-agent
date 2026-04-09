# 下一步工作计划：Persona-Agent 架构重构

## 📊 研究洞察总结

基于对 **CharacterAI**、**CrewAI**、**RoleRAG** 等前沿项目的深入研究：

### 🎯 关键发现

| 发现 | 影响 | 我们的现状 |
|------|------|-----------|
| **CharacterAI 使用训练而非纯提示** | 高质量角色需要微调 | 仅使用提示工程 |
| **RoleRAG 解决一致性幻觉** | 需要知识图谱+边界感知检索 | 简单向量检索 |
| **三层记忆架构是标准** | 工作/情景/语义记忆 | 仅线性历史 |
| **Temperature 0.3-0.7** | 平衡创造性和一致性 | 未优化 |
| **情绪状态机** | 情感强度+持续时间 | 简单关键词触发 |

---

## 🚀 重构路线图（已更新）

### Phase 1: 核心架构重构（优先级最高）

#### 任务 1: 三层 Prompt 系统 + RoleRAG 集成
**重要性**: ⭐⭐⭐⭐⭐  
**预计时间**: 5-7 天  
**参考**: RoleRAG 论文 + CrewAI

**具体实现**:
```python
class LayeredPromptEngine:
    """三层 Prompt + RoleRAG 检索"""
    
    Layer 1: Core Identity (静态)
      - 角色核心身份（不变）
      - 价值观、基本性格
    
    Layer 2: Dynamic Context (动态)
      - Emotional State (效价+唤醒度)
      - Relationship State (亲密度+信任)
      - Cognitive State (注意力+目标)
    
    Layer 3: Knowledge & Task
      - RoleRAG 检索相关知识
      - 当前任务指令
      - 响应约束
```

**验收标准**:
- [ ] 角色一致性评分 > 0.85
- [ ] 知识幻觉减少 50%
- [ ] Prompt 长度减少 30%（更精准）

---

#### 任务 2: 认知-情感双路径架构
**重要性**: ⭐⭐⭐⭐⭐  
**预计时间**: 4-5 天  
**参考**: EmotionFlow (MIT, 2024)

**具体实现**:
```python
class CognitiveEmotionalEngine:
    """双路径处理架构"""
    
    async def process(self, user_input: str) -> Response:
        # 路径1: 认知处理（理解、推理、规划）
        cognitive = await self.cognitive_pathway(
            user_input,
            context=self.working_memory
        )
        
        # 路径2: 情感处理（情绪识别、影响评估）
        emotional = await self.emotional_pathway(
            user_input,
            relevance=cognitive.relevance_score
        )
        
        # 融合层: 情感调节认知
        fused = self.fusion_layer.merge(cognitive, emotional)
        
        return await self.response_generator(fused)
```

**核心创新**:
- 情感强度建模 (0.0-1.0)
- 情感效价 (Valence) + 唤醒度 (Arousal)
- 情感-认知相互影响
- 多情绪混合支持（不是单一标签）

**验收标准**:
- [ ] 情绪转换自然度 > 4.0/5.0
- [ ] 长对话中情感一致性 > 80%

---

#### 任务 3: 层次化记忆系统（三层）
**重要性**: ⭐⭐⭐⭐⭐  
**预计时间**: 5-6 天  
**参考**: MemoryBank (Google, 2024)

**具体实现**:
```python
class HierarchicalMemory:
    """三层记忆架构"""
    
    # Layer 1: Working Memory (工作记忆)
    # - 最近 3-5 轮对话
    # - 始终保持在 Context 中
    working_memory: Deque[Message]
    
    # Layer 2: Episodic Memory (情景记忆)
    # - 向量化存储 (ChromaDB)
    # - 语义检索相关事件
    episodic_store: VectorStore
    
    # Layer 3: Semantic Memory (语义记忆)
    # - 知识图谱 (人物关系、事实)
    # - 图数据库或关系型
    semantic_graph: GraphStore
    
    async def retrieve(self, query: str, context: Context) -> MemoryContext:
        # 1. 工作记忆总是包含
        working = self.working_memory.get_recent(n=5)
        
        # 2. 情景记忆：语义检索
        episodic = await self.episodic_store.similarity_search(
            query,
            filter={"user_id": context.user_id, "importance": ">0.7"},
            top_k=3
        )
        
        # 3. 语义记忆：实体检索
        entities = self.extract_entities(query)
        semantic = await self.semantic_graph.query_entities(entities)
        
        # 4. 重要性排序和融合
        return self.merge_and_rank(working, episodic, semantic)
```

**关键特性**:
- **时间衰减**: 旧记忆重要性逐渐降低
- **重要性评分**: 用户强调的内容权重更高
- **记忆总结**: 长对话自动总结为情景记忆
- **冲突检测**: 检测记忆冲突并解决

**验收标准**:
- [ ] 相关记忆检索准确率 > 80%
- [ ] 记忆检索响应时间 < 100ms
- [ ] 长对话（50轮）上下文保持 > 70%

---

### Phase 2: 高级功能（重要）

#### 任务 4: 角色一致性验证器
**重要性**: ⭐⭐⭐⭐  
**预计时间**: 3-4 天  
**参考**: Constitutional AI (Anthropic)

```python
class ConsistencyValidator:
    """四层一致性检查"""
    
    def validate(self, response: str) -> ValidationResult:
        checks = {
            "values_alignment": self.check_core_values(response),
            "personality_coherence": self.check_personality_traits(response),
            "historical_consistency": self.check_against_past_responses(response),
            "emotional_appropriateness": self.check_emotion_fit(response),
            "knowledge_boundaries": self.check_knowledge_limits(response)
        }
        
        if not all(checks.values()):
            return self.regenerate_with_constraints(checks)
```

---

#### 任务 5: 自适应用户建模
**重要性**: ⭐⭐⭐⭐  
**预计时间**: 4-5 天  
**参考**: Honcho (plastic-labs)

```python
class UserModel:
    """学习用户偏好和行为"""
    
    preferences: Dict[str, Preference]  # 话题偏好、风格偏好
    emotional_triggers: Dict[str, float]  # 情绪触发点
    trust_level: float  # 关系亲密度 0-1
    interaction_patterns: PatternHistory  # 行为模式
    
    def adapt(self, interaction: Interaction) -> Adaptation:
        # 实时学习用户反馈
        sentiment = self.analyze_sentiment(interaction.response)
        engagement = self.measure_engagement(interaction)
        
        # 调整角色参数
        if sentiment.negative:
            return self.soften_tone()
        if engagement.low:
            return self.increase_proactivity()
```

---

#### 任务 6: Prompt 版本控制与 A/B 测试
**重要性**: ⭐⭐⭐  
**预计时间**: 2-3 天

```python
class PromptVersionManager:
    """管理 Prompt 版本和效果追踪"""
    
    def deploy(self, new_prompt: Prompt) -> Deployment:
        # 灰度发布
        return self.canary_deploy(new_prompt, traffic_split=0.1)
    
    def evaluate(self, version_id: str) -> Metrics:
        # 评估角色一致性、用户满意度
        return {
            "consistency_score": self.measure_consistency(),
            "user_satisfaction": self.get_user_ratings(),
            "engagement_rate": self.calculate_engagement()
        }
```

---

### Phase 3: 优化与扩展

#### 任务 7: 多模态支持（可选）
**重要性**: ⭐⭐  
**预计时间**: 5-7 天
- 表情/动作描述生成
- 语音语调提示

#### 任务 8: 多智能体协作（未来）
**重要性**: ⭐⭐  
**预计时间**: 7-10 天
- 多个角色群聊场景
- 角色间关系动态

---

## 📋 详细实施计划

### Week 1: 基础架构
- **Day 1-2**: 设计三层 Prompt 接口
- **Day 3-4**: 实现 RoleRAG 知识检索
- **Day 5-7**: 集成测试和优化

### Week 2: 认知-情感引擎
- **Day 1-2**: 实现情感状态机（效价+唤醒度）
- **Day 3-4**: 实现双路径处理
- **Day 5**: 融合层和响应生成

### Week 3: 记忆系统重构
- **Day 1-2**: 工作记忆 + 情景记忆（向量）
- **Day 3-4**: 语义记忆（图数据库）
- **Day 5**: 记忆检索和融合逻辑

### Week 4: 一致性验证
- **Day 1-2**: 一致性检查器
- **Day 3-4**: 用户建模系统
- **Day 5**: 集成测试

---

## 🎯 技术选型建议

### 记忆存储
```
工作记忆: 内存 (deque)
情景记忆: ChromaDB (向量检索)
语义记忆: Neo4j 或 NetworkX (图数据库)
```

### 检索增强
```
Embedding: text-embedding-3-small 或本地模型
相似度: 余弦相似度 + 时间衰减权重
重排序: Cross-encoder 微调
```

### LLM 参数
```python
{
    "temperature": 0.4,      # 平衡创造性和一致性
    "top_p": 0.9,           # 允许合理变化
    "frequency_penalty": 0.2, # 减少口头禅重复
    "presence_penalty": 0.1   # 轻微话题多样性
}
```

---

## 📊 成功指标（KPIs）

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|----------|
| **角色一致性** | ~60% | >85% | 人工评估 100 轮对话 |
| **情绪自然度** | ~3.2/5 | >4.0/5 | 用户评分 |
| **记忆准确率** | ~50% | >80% | 相关记忆在 Top-3 比例 |
| **长对话保持** | ~40% | >70% | 20轮后角色不崩坏比例 |
| **知识幻觉** | ~30% | <10% | 角色知识边界内回答比例 |
| **响应延迟** | ~2s | <1s | P95 响应时间 |

---

## 🚨 风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| **重构范围过大** | 延期 | 分阶段交付，每个阶段可独立运行 |
| **性能下降** | 体验差 | 提前做性能基准测试，缓存策略 |
| **一致性难以量化** | 无法评估 | 建立评估数据集和自动化测试 |
| **用户不适应新行为** | 流失 | A/B 测试，逐步灰度发布 |

---

## 💡 立即开始的建议

我建议按以下顺序实施：

### ✅ 今天就做
1. **创建 `refactor/layered-prompt` 分支**
2. **设计 `PromptEngine` 接口**
3. **编写 ADR (Architecture Decision Record)**

### ✅ 本周完成
1. **实现三层 Prompt 基础框架**
2. **添加 RoleRAG 知识检索**
3. **编写单元测试**

### ✅ 验证标准
```python
# 重构后应该可以这样使用
engine = LayeredPromptEngine(
    character=pixel_character,
    knowledge_graph=pixel_kg,
    memory=hierarchical_memory
)

context = engine.build_context(
    user_input="我今天很难过",
    conversation_history=recent_messages
)

# context 自动包含：
# - 核心身份（静态）
# - 当前情绪状态（动态）
# - 相关记忆（检索）
# - 知识边界（约束）
```

---

## 🎓 学习资源

1. **RoleRAG 论文**: https://arxiv.org/abs/2505.18541
2. **CrewAI 源码**: https://github.com/CrewAIInc/crewAI
3. **MemoryBank 论文**: Google Research 2024
4. **Character-LLM**: https://arxiv.org/abs/2310.10158

---

**准备好开始 Phase 1 了吗？** 🚀

我建议从 **任务1: 三层 Prompt + RoleRAG** 开始，因为它是：
1. 影响最大的（所有对话质量提升）
2. 风险可控（向后兼容）
3. 可以快速验证效果

需要我为第一个任务创建详细的技术设计文档吗？
