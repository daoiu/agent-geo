# 简历项目描述 — GEO 优化 Agent(v5 · 工程师写法对齐版)

> 面向 **AI Agent / AI 应用开发岗**。按 `D:\Agent\学习文档\helson\怎么判断你的简历是否合格？ (1)(1).pdf` 的「工程师写法 + 6 件事 + 15 题自检」标准重写。
>
> **相对 v4 的差异**:v4 仍偏「技术名词清单」(八股写法),v5 全部改成「**针对 X 业务问题,基于 X 技术机制,设计 X 工程方案,实现 X 可验证效果**」;项目骨架按 6 件事(任务边界 / 工具契约 / 上下文策略 / 状态管理 / 权限确认 / 评测集)重组;附 15 题自检答案作为面试弹药库。

---

## 0 · v4 vs v5 写法对比(2 个例子)

| 维度 | v4 八股写法(被秒拒) | v5 工程师写法(被追问也答得上) |
|---|---|---|
| RAG | 「搭建 RAG 全链路:bge-small-zh-v1.5 + ChromaDB + jieba 双路召回,RRF(k=60)融合」 | 「针对品牌知识库频繁更新、模型凭印象回答会编造、且失败会污染下游内容的问题,基于稠密向量 + BM25-like 关键词 + RRF 融合设计混合检索,实现召回可追溯(带 kb_name / doc_filename)、失败自动降级纯关键词、无依据问题可拒答」 |
| Tool Use | 「5 个 agent 工具,Pydantic 强校验,tool_call 配对保证」 | 「针对 LLM 工具调用缺乏参数校验会污染下游、跨 provider 切换时 dangling tool_call_id 会让 strict provider 直接 400 的问题,基于 Pydantic 参数强校验 + tool_call 配对保证(kept_ids = resolved_ids ∩ declared_ids)设计 5 工具调度,实现关键动作可执行、可校验、可控制,strict provider 0 失败」 |

---

## 1 · 简历正文(1 页纸 · 按 6 件事框架)

### 1.1 抬头

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[姓名]                                       目标岗位:AI Agent / AI 应用开发
电话:[手机]   邮箱:[邮箱]   GitHub:[github.com/xxx]
期望城市:[城市 / 接受远程]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 1.2 个人简介(2 句 · 按 REFRAME 写「为什么存在」)

```text
[1~3 / N] 年 Python 后端,近 [N] 年聚焦 LLM Agent 工程化。独立主导 GEO 优化 Agent
全链路(诊断→RAG→内容生成→审核发布→监测),累计 9 个迭代阶段、6 个核心模块
~2 200 行、测试 1 100+ 行,所有模块都能讲清「为什么存在 / 失败怎么兜底 /
效果怎么验证」,可基于既有业务 5 分钟 docker-compose 复现完整链路。
```

### 1.3 技能清单(分组 + 关键词对齐 JD)

```text
• 语言与运行时:Python 3.11+、SQL、Shell、asyncio、类型注解
• Web 与 API:FastAPI 0.115、Uvicorn、Pydantic v2、StreamingResponse / SSE
• Agent 与编排:自写 ReAct 状态机(对标 LangGraph,不引框架)、
  OpenAI Function Calling、Pydantic 工具参数强校验、断点续跑 checkpoint
• 模型与网关:OpenAI 兼容 SDK 1.60(DeepSeek / DeepSeek-R1 / Kimi / MiniMax)、
  流式 chat.completions、推理模型 think 块治理
• 检索与 RAG:bge-small-zh-v1.5(512 维)、ChromaDB、jieba、RRF 融合、
  混合检索 + 降级、增量同步
• 记忆与上下文:ChromaDB 向量记忆层(scope 隔离、字数门控、距离阈值语义去重)、
  上下文预算(滑动窗口 + 旧工具结果截断)
• 数据与缓存:SQLAlchemy 2 async、aiosqlite、APScheduler、structlog
• 前端:React 18 + TypeScript + Vite + Tailwind + Radix UI +
  TanStack Query + Playwright(axe-core 无障碍)
• 工程化:Docker、docker-compose、pytest + vitest + Playwright E2E
```

### 1.4 项目经历(按 6 件事骨架)

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GEO 优化 Agent(v0.1 → Phase 3)        [起始年月] – [结束年月]
个人项目 / 后端主导 + 前端 + 工程化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### ① 任务边界(替谁 / 做什么 / 不做什么)

```text
替非技术市场人员做 GEO(生成式引擎优化)诊断 + 内容生成辅助 + 发布辅助 +
提及率监测;不做内容伪造 / AI 投毒 / 黑帽 SEO 等白帽以外的操作(README
§9 合规说明)。Agent 入口仅自然语言对话,5 工具覆盖诊断 / 检索 / 列库 /
单篇生成 / 批量任务;写工具默认后台异步(避免流式卡顿),HITL 保留为 opt-in。
```

**Multi-Agent 拆分(v0.6+ Multi-Agent 改造)**:
- 保留单 ReAct 主 agent 不动,5 工具中 2 个(`generate_article` / `create_generation_task`)改走 specialist handoff;
- 拆 2 个 specialist:**ContentWriterSpecialist**(无 ReAct 状态,纯生成)+ **MonitorSpecialist**(无对话入口,纯查询判定);
- Handoff 协议 5 条纪律:幂等键(查 handoff_log)/ 超时(asyncio.wait_for)/ 状态隔离(独立 session)/ 失败回退(降级旧路径)/ 成本归因(落 log);
- 不拆 diagnose / search / list 三个工具(需要主 agent 路由);
- 不引 LangGraph / LangChain / CrewAI / AutoGen(延续 v0.4 决策)。

#### ② 工具契约(参数 / 失败 / 回退)

```text
5 工具(diagnose_brand / search_knowledge / list_knowledge_bases /
generate_article / create_generation_task),每个工具入参用 Pydantic 模型
做强校验(类型 / 必填 / 范围);跨 provider 切换时按
kept_ids = resolved_ids ∩ declared_ids 策略丢弃 dangling tool_call、
跳过孤儿 tool 结果,strict provider 0 失败。

失败回退链:
- HybridSearch:任一链路失败 → 自动降级纯关键词召回(跨库路径 per-KB
  向量失败 skip 后整体降级);
- ContentWriter:transient 异常(超时 / 429 / 5xx)→ 吞掉返回空标题 +
  空正文,调用方按"流结束但 content 为空"判定失败;
- Agent 主循环:工具抛未捕获异常 → 转 JSON 错误载荷写入 tool 消息,
  继续 ReAct,避免单点失败拖死整轮 turn;
- 写工具:默认 v0.6 P1.6 后台异步(落 v0.2 Task 表 + 触发 worker +
  立即返回 task_id,与批量任务复用),与多篇生成走同一套路径。
```

#### ③ 上下文策略(什么进 / 什么先摘要 / 怎么防爆)

```text
Phase 3 上下文预算(默认关闭可调):
- 滑动窗口 context_window_messages=40 → 送进 LLM 的最近历史条数上限;
- 旧工具结果截断 tool_result_max_chars=2000 + tool_result_keep_recent=3
  → 最近 3 个 tool 结果保全量,其余超长截断 + 标"…(truncated)";
- build_messages 先裁窗口再算 kept_ids,先扫配对再裁内容,避免边界副作用。

system prompt 分层:常量部分(角色 + 工具契约 + 反编造)放前;
v0.6 P1.6 L2 记忆索引段(仅 scope 内记忆名 + 描述)拼到末尾,
命中率高的小集合索引段常量化利于 OpenAI prompt cache,
索引变更不重建整段 system。

记忆 prepend:仅在第一条 user 消息前注入 <relevant_memories>...</>
块,后续 assistant / tool / system 不重复注入;空集合 → 不注入。
```

#### ④ 状态管理(什么跨会话 / 什么用完即焚 / 怎么冲突)

```text
会话级(用完即焚):AgentMessageORM(role / content / tool_calls /
tool_call_id / pending_confirmation),turn_complete 后 fire-and-forget
触发 _do_extract_after_turn 蒸馏。

跨会话级(分层,Phase 2 向量化):
- L0 episodic(AgentMessageORM):原始对话流,SQLite 持久化;
- L1 semantic(KB chunks):bge 向量化后入 ChromaDB 每 KB 一个
  collection(cosine);
- L2 preferences(AgentMemoryORM):跨会话用户偏好 / 反馈 / 项目事实 /
  参考资料,4 类型受白名单约束;向量层 MemoryVectorIndex(单 collection
  agent_memories + scope 隔离,scope = device_id 跨 session 共享,
  缺失降级 anon:<session_id>)。

冲突处理:
- 写入去重:字数门控 memory_extract_min_chars=8 + cosine 距离阈值
  memory_dedup_max_distance=0.15(语义近邻直接跳过);
- 整理去重:consolidate 阈值触发(行数 ≥ memory_consolidate_threshold=50),
  同步 delete_scope + 回填向量(失败静默,下次 select 补);
- 旧记忆与新任务冲突 → 写入去重 + 距离阈值 + consolidate 周期性整理,
  不引入 PII 脱敏 / 可删除设计(诚实标注,推迟到 v1.0)。
```

#### ⑤ 权限确认(高风险动作怎么兜底)

```text
写工具(generate_article / create_generation_task):默认后台异步,与
v0.2 批量任务复用同一套审核 → WordPress 发布 → 提及率监测的
"用户在前端审核"兜底,Agent 端不直接落库到最终发布通道。

Human-in-the-loop(opt-in):写类工具抛 HumanConfirmationRequired →
ReAct 暂停 → yield human_confirmation_required SSE 事件 → 前端弹窗 →
用户点确认 → POST /sessions/{sid}/messages/{msg_id}/confirm →
调 _execute_generate_article_confirmed → 生成预览(标题 + 前 300 字符)→
落 tool 消息 → run_agent_turn_from_checkpoint 从 pending_confirmation
checkpoint 续跑剩余推理步。

网络面:SSRF 守卫拒绝内部 IP(URL 黑名单 + GEO_ENV=development 切换
dev/prod 模式);WordPress 发布用 Application Password 而非长期 token;
SMTP 密码用 cryptography 加密存 SQLite,启动解密。

模型适配:DeepSeek-R1 / MiniMax 等带 <think>... 推理块输出的模型,采用
双层防御——
- 静态:_strip_think_blocks 正则一次性剥离;
- 流式:三态状态机 before_think → in_think → after_think + 7 字符
  回看缓冲,正确处理 think 块跨 chunk 切断;
- system_prompts 同时显式禁止模型在正文写出 think 块(双层防御,
  不依赖单一剥离)。
```

#### ⑥ 评测集(一次改动到底变好还是变差)

```text
测试覆盖:
- test_content_writer_agent.py 392 行:含 think 块静态剥离 +
  流式跨 chunk 切断 102 行新增;
- test_tool_executor.py 729 行:覆盖后台异步与 HITL 双路径;
- pytest + vitest + Playwright E2E 覆盖 agent 循环 / 工具执行 /
  混合检索 / think 块剥离关键路径。

离线指标(Phase 1 观测重构):
- _emit_metrics 在三出口(turn_complete / max_iterations_reached /
  human_confirmation)打 agent_turn_metrics 结构化日志;
- 聚合 prompt_tokens / completion_tokens / total_tokens +
  usage_seen 标志,避免 LLM 不返回 usage 时污染统计;
- 配套 agg_metrics.py token baseline 脚本,真实流量下复算 P50 /
  P95 / 单轮 token 消耗。

手动验证:README + MANUAL_VERIFICATION_V0.1~V0.5 7 场景手测清单,
覆盖启动 / 诊断 / 知识库 / Agent chat / 工具 / 观测 / 降级。

诚实备注:个人项目,9 个迭代阶段 / 188 个 commit 全部在本地开发,
无线上流量与生产指标;无可引用的用户规模 / 性能 / SLA 数据。
可在面试现场演示:git clone + cp .env.example .env + 填 DeepSeek key
+ docker-compose up,5 分钟内跑通 /agent 入口。
```

#### 项目成果(数据化 · 末尾)

```text
• 9 个迭代阶段、6 个核心模块合计 ~2 200 行(react_loop 576 +
  tool_executor 411 + memory 391 + content_writer_agent 233 +
  system_prompts 110 + hybrid_search 180 + memory_vector 63 +
  embedding 42)。
• 测试 1 100+ 行(392 + 729)覆盖关键路径,可在真实流量前快速回归。
• 5 工具 / 4 模型适配(DeepSeek / DeepSeek-R1 / Kimi / MiniMax)
  / 单库 + 跨库双路径检索 / strict provider 0 失败。
• 188 个 commit,README + MANUAL_VERIFICATION_V0.1~V0.5 + 设计 /
  实施 / 验证三套文档完整,可作为团队新人 onboarding 材料。
```

---

## 2 · 15 题自检答案(面试弹药库 · 不写进简历)

> 把简历上 GEO 优化 Agent 拿出来,逐题答 1 分钟。答不上 = 八股写法,
> 会被面试当场拆穿。答得上 = 工程师写法,简历一条就够。

### 2.1 RAG 信息从哪里来(3 题)

**Q1 你的 Agent 缺的是内部文档、实时数据、专业规则,还是历史用户记录?为什么这些信息不能直接靠模型回答?**

- 缺的是**内部文档**(品牌方上传的 PDF/Word/MD/TXT,作为 GEO 内容生成
  的真实信息源)+ **专业规则**(GEO 方法论:权威性 / 相关性 / 结构化
  / 时效性 / 可验证性的 5 维评分卡)。
- 不能直接靠模型回答:模型对客户私有文档 0 知识,只能凭通用语料"生成
  一个看似合理"的内容 → 出现编造、错误产品名、错误数据,反而损害
  GEO(白帽 GEO 的反义是黑帽投毒)。

**Q2 检索失败会出现哪几种情况:查不到 / 查错 / 来源冲突 / 内容过期 / 证据不足?每一种怎么处理?**

- **查不到**(召回为空):HybridSearch 失败 → 自动降级纯关键词(jieba
  分词 + SQL LIKE);仍查不到 → 返回 total_found=0 + 让 LLM 显式
  拒答"无依据问题可拒答"(system_prompts 强制)。
- **查错**(召回内容与问题不匹配):RRF 融合时向量 + 关键词任一可信
  即保留,_rrf_score 标得分便于上层调试;chunk 截断 500 字避免 LLM
  上下文爆炸,降低错配放大效应。
- **来源冲突**(同一问题命中多 KB / 多文档相互矛盾):跨库路径
  search_across_kbs 用 RRF 单点融合,冲突项都返回带 kb_name +
  doc_filename,LLM 自行权衡;未做事实级冲突检测(诚实标注,推迟到
  v0.5.1-3)。
- **内容过期**:v0.5 启动 lazy 向量化 + 上传 / 删除钩入 ChromaDB 实现
  增量同步;删除是直接清;过期未做 TTL(诚实标注)。
- **证据不足**:chunk 截断 500 字 + system_prompts "不得编造"约束
  + LLM 拒答路径。

**Q3 你怎么证明 RAG 有用:是提升答案准确率 / 减少幻觉 / 提高引用正确率 / 降低人工查询成本?**

- 仓库无生产流量,**未做线上 A/B 评测**(诚实标注)。
- 可在面试现场跑:
  - 自建 200 条品牌 GEO 问题集(v0.2 tasks 真实用户问题采样);
  - 对照组:无 RAG 的 LLM 直答 vs RAG + chunk 注入;
  - 指标:答案中关键实体名(品牌 / 产品)命中率 + 引用 kb_name /
    doc_filename 的正确率 + 拒答率(无依据问题应拒答);
  - 跑在 README 的 MANUAL_VERIFICATION 流程上,可现场演示。

### 2.2 MEM 状态怎么保存(3 题)

**Q4 哪些信息只是当前任务状态、哪些是短期上下文、哪些才值得跨会话保存?判断标准是什么?**

- **当前任务状态**(用完即焚):AgentMessageORM 的 tool_call_id +
  pending_confirmation 字段,turn_complete 后 fire-and-forget 触发
  蒸馏,蒸馏完成后即"过期"。
- **短期上下文**(本次会话内):AgentMessageORM role=tool / user /
  assistant 的最近 40 条(Phase 3 滑动窗口)。
- **长期偏好 / 跨会话**(值得保存):4 类型受白名单约束——
  - user:用户偏好(语言 / 输出风格 / 写作风格)
  - feedback:用户反馈("以后别用 X 风格")
  - project:项目事实("客户的品牌主色是 X")
  - reference:参考资料(URL / 文档名)
- 判断标准:`memory_extract_min_chars=8` 字数门控(避免噪声) +
  cosine 距离阈值 `memory_dedup_max_distance=0.15`(避免重复)。

**Q5 长期记忆写入前是否需要用户确认?后续如何更新 / 删除 / 过期 / 处理冲突?**

- **写入确认**:目前未做 UI 确认(诚实标注);但 extract 流程有字数门控
  + 距离阈值 + LLM 蒸馏(LLM 自己判断是否值得记)。
- **更新**:同名(name)直接 skip(避免覆盖)。
- **删除**:未做 UI 删除(诚实标注);consolidate 周期性整理是事实上的
  批量删除。
- **过期**:未做 TTL(诚实标注);靠 consolidate 触发阈值(行数 ≥ 50)
  来压缩总量。
- **冲突**:consolidate 让 LLM 合并 / 删除 / 排序("Merge duplicates /
  Remove outdated/contradicted / Keep the total under 30 memories")。

**Q6 如果模型记错 / 用户恶意写入 / 旧记忆与新任务冲突,系统怎么拦截和回滚?**

- **模型记错**:LLM 蒸馏有距离阈值去重 + 后续 extract 仍会持续触发
  consolidate;诚实标注,无显式回滚接口。
- **用户恶意写入**:未做 PII 脱敏 / 可删除设计(README §9 推迟 v1.0)。
- **旧记忆与新任务冲突**:scope 隔离(每个 device_id 独立 vector scope)
  防止跨用户污染;consolidate 周期性整理 + LLM 冲突仲裁。

### 2.3 TOOL 工具什么时候介入(3 题)

**Q7 哪些动作必须调用工具,而不能让模型用自然语言"生成一个看似合理的结果"?**

- 品牌诊断(爬虫 + 真实搜索结果)→ 不能让模型编造提及率;
- 知识库检索(用户私有文档)→ 不能让模型凭印象回答;
- 任务创建 + 调度(后台 worker)→ 不能让模型口述"已创建";
- WordPress 发布(网络副作用)→ 不能让模型模拟"已发布";
- 任何会**产生外部副作用**或**依赖私有数据**的动作,都必须调工具。

**Q8 工具调用前,参数完整性 / 权限边界 / 业务规则 / 副作用分别怎么校验?**

- **参数完整性**:Pydantic 模型校验(类型 / 必填 / 范围),工具分发前
  走 `validate_tool_args(tool_name, args)`,失败抛 ValidationError。
- **权限边界**:未做完整租户隔离(README v1.0 推迟项);SSRF 守卫拒绝
  内部 IP(URL 黑名单 + dev/prod 模式)。
- **业务规则**:
  - diagnose_brand 入参 brand_name / industry / official_url 必填;
  - search_knowledge 跨库路径(无 kb_id)与单库路径(有 kb_id)分离;
  - generate_article 必须传 kb_id(基于 KB 召回);
  - create_generation_task 必须传 kb_id + article_count + style +
    target_length。
- **副作用**:写工具默认后台异步(避免流式卡顿);HITL 路径 opt-in
  弹窗确认 → pending_confirmation 落库 → run_agent_turn_from_checkpoint
  续跑。

**Q9 工具失败后,什么时候重试 / 什么时候降级为只读回答 / 什么时候必须转人工?**

- **重试**:未做自动重试(诚实标注);HybridSearch 失败直接降级而非
  重试(避免放大)。
- **降级为只读**:HybridSearch 失败 → 纯关键词召回(不重试);ContentWriter
  transient 失败 → 吞掉返回空,调用方按"流结束但 content 为空"判定
  失败。
- **转人工**:HITL 路径 opt-in(写工具抛 HumanConfirmationRequired →
  前端弹窗 → 用户确认);系统不做自动转人工,留给用户主动触发。
- **整体策略**:fail-fast(不无限重试) + 优雅降级(能力逐步降级而非
  整体崩溃) + 显式失败(返回明确错误码,让上层决策)。

### 2.4 EVAL 效果如何验证(3 题)

**Q10 这个 Agent 的成功标准是什么:任务完成 / 答案可信 / 节省时间 / 降低人工介入 / 减少错误操作?**

- 仓库无生产流量,**未做线上 A/B 评测**(诚实标注)。
- 设计上支持的成功标准:
  - **任务完成率**:max_iterations_reached 占比(越低越好) +
    turn_complete 占比(越高越好);
  - **答案可信度**:hit rate on brand / product 关键实体名 +
    引用 kb_name / doc_filename 的正确率;
  - **降低人工介入**:HITL 触发率 human_confirmation 占比(应逐步
    下降);
  - **减少错误操作**:tool error 占比(应逐步下降);
  - **节省时间**:单 turn token 消耗(P50 / P95) + 端到端 P95 延迟。
- 全部通过 `_emit_metrics` 三出口埋点 + `agg_metrics.py` 聚合。

**Q11 评测集来自真实用户问题还是自己编的样例?是否覆盖正常 / 边界 / 失败 / 恶意输入?**

- 仓库未提供官方评测集(诚实标注);可在面试现场构建:
  - **真实用户问题**:从 v0.2 tasks 表采样(N 条品牌 GEO 真实问题);
  - **正常**:典型诊断 / 检索 / 生成流程;
  - **边界**:超长上下文(>40 条历史)→ 触发 Phase 3 截断;空 KB →
    触发 total_found=0 拒答;非 ASCII 输入(emoji / 特殊符号);
  - **失败**:ChromaDB 不可用 → HybridSearch 降级;LLM 超时 →
    ContentWriter 返回空;tool_call 错配 → kept_ids 配对保证;
  - **恶意**:SSRF 内部 IP → URL 黑名单拦截;超长用户输入 →
    max_upload_size_mb=50 限制。
- 测试覆盖:pytest 392 + 729 行 + Playwright E2E + axe-core 无障碍。

**Q12 一次失败能否定位到具体环节:意图识别 / 检索 / 上下文管理 / 工具调用 / 模型推理 / 权限规则 / 产品流程本身?**

- **能**:`agent_turn_metrics` 三出口埋点 + structlog 字段:
  - iterations(推理步数)
  - llm_calls(LLM 调用次数)
  - tool_calls(工具调用次数)
  - prompt_tokens / completion_tokens / total_tokens
  - outcome(turn_complete / max_iterations_reached / human_confirmation)
- **不能**:未做细粒度 per-tool 埋点(诚实标注,推迟到 v0.5.1-3)。
- **改进方向**:tool_call 失败时记录 exc 类型 + 参数 + 错误载荷;
  retrieval 失败时记录 query + recall@k + 关键词 / 向量分布。

### 2.5 MULTI 是否真的该拆(3 题)

**Q13 为什么不能用单 Agent + workflow 解决?拆成多 Agent 后具体降低了什么复杂度?**

- GEO2 是"主 Agent + 2 specialist"三层架构(不是无差别多 Agent):
  - **主 Agent (ReAct Loop)**:5 工具中 3 个保留(diagnose_brand / search_knowledge / list_knowledge_bases),负责路由决策 + 反思;2 个工具(generate_article / create_generation_task)改走 specialist handoff。
  - **ContentWriterSpecialist**:无 ReAct 状态,只看 (system + brand + topic + chunks),纯生成。
  - **MonitorSpecialist**:无对话入口,只看 (brand + questions + providers),纯查询判定。
- **为什么只拆 2 个**:对照 LangGraph / AutoGen / CrewAI / MetaGPT 4 个项目"什么时候该拆"8 条标准中,GEO2 仅满足 ① 部分(职责错位)+ ⑥ 全部(工具/权限差异大),其他 6 条不满足。拆 2 个 specialist 是"标准 ⑥ 的直接体现",引入更重机制(写-评-改/Manager 委派/并行)是负优化。
- **降低什么复杂度**:
  - 上下文隔离:ContentWriter 不污染主 agent ReAct 状态,文章生成可独立调试;
  - 评测独立:ContentWriter / Monitor 可独立 LLM-as-judge(评测体系 4.5 → 5.0);
  - 失败兜底:HITL 路径在主 agent 写工具确认,specialist 失败自动降级到旧路径;
  - 成本归因:handoff_log 表按 specialist 聚合 token / 失败率 / 超时率。

**Q14 每个 Agent 的职责 / 工具权限 / 上下文可见范围 / 输出契约是什么?谁负责最终结果?**

| 维度 | 主 Agent (ReAct) | ContentWriterSpecialist | MonitorSpecialist |
|---|---|---|---|
| 职责 | 路由 + 工具编排 + 反思 | 写文章(单/批) | 定期 LLM 查询 + 提及率判定 |
| 工具 | diagnose_brand / search_knowledge / list_knowledge_bases + handoff 2 个 specialist | 无工具调用(纯生成) | 无工具调用(纯查询) |
| 上下文 | 会话历史 + KB 召回 + L2 记忆 | system_prompt + brand + topic + chunks | brand + industry + questions + providers |
| 输出 | SSE 事件流(7 类) | HandoffResult(文章正文 + token) | HandoffResult(snapshot + 提及率 + 阈值告警) |
| 权限 | 全工具 + 写类 HITL | 仅 specialist 内部权限 | 仅 specialist 内部权限 |

- **最终结果负责**:主 Agent(类似 orchestrator);specialist 失败 → 主 Agent 决定重试 / 降级 / 转人工。

**Q15 handoff 失败 / 重复调用 / 状态丢失 / 成本和延迟上升时,系统如何停止 / 回退和记录问题?**

- **本项目 handoff 协议 5 条工程纪律**(完整答案):
  1. **幂等键**:`handoff_id` (UUID4),specialist 收到重复 → 直接返回上次 `HandoffResult`(查 `handoff_log` 表,24h 窗口内);
  2. **超时**:`asyncio.wait_for(timeout=...)`,默认 300s(ContentWriter) / 60s(Monitor),超时 → 落 `status=timeout` + 主 Agent 降级;
  3. **状态隔离**:specialist 不持有主 Agent ReAct 状态,只接 `payload` dict,使用独立 DB session + LLM client;
  4. **失败回退**:specialist 抛 `SpecialistHandoffError` → 主 Agent catch → 降级到旧路径(`_execute_generate_article_legacy` / `monitor_service.execute_monitor_run`);
  5. **成本归因**:每次 handoff 落 `handoff_log` 表(specialist / handoff_id / task_id / session_id / started_at / duration_ms / token_usage / status),用于成本 dashboard / token baseline / 失败率监控。
- **整体策略**:fail-fast(不无限重试)+ 优雅降级(能力逐步降级而非整体崩溃)+ 显式失败(返回明确错误码,让上层决策)。
- **成本控制**:`handoff_log` 表按 specialist 聚合,`handoff_log_retention_days=90` 定期清理;`handoff_timeout_*` 配置可调。
- **日志关联**:`handoff_id` 串联主 Agent session / specialist 调用 / 失败 / token 4 段链路,便于审计与回溯。

---

## 3 · 6 件事自检(按 PDF §04 · 改写清单)

| 6 件事 | 在 v5 哪个位置 |
|---|---|
| ① 任务边界(替谁 / 做什么 / 不做什么) | 1.4 项目经历 · ① 任务边界 |
| ② 工具契约(参数 / 失败 / 回退) | 1.4 项目经历 · ② 工具契约 |
| ③ 上下文策略(什么进 / 什么先摘要 / 怎么防爆) | 1.4 项目经历 · ③ 上下文策略 |
| ④ 状态管理(什么跨会话 / 什么用完即焚 / 怎么冲突) | 1.4 项目经历 · ④ 状态管理 |
| ⑤ 权限确认(高风险动作怎么兜底) | 1.4 项目经历 · ⑤ 权限确认 |
| ⑥ 评测集(一次改动到底变好还是变差) | 1.4 项目经历 · ⑥ 评测集 |

---

## 4 · 投递前 5 问自检(按 PDF REFRAME 倒推)

1. **我能讲清这个项目「为什么存在」吗?** → v5 抬头 1.2 简介 2 句
   已写明"为什么 GEO / 为什么 LLM Agent / 为什么工程师写法"。
2. **我能讲清每个模块「失败怎么兜底」吗?** → v5 1.4 · ②工具契约 +
   ⑤权限确认 + 15 题 Q9(失败处理决策树)已覆盖。
3. **我能讲清「效果怎么验证」吗?** → v5 1.4 · ⑥评测集 + 15 题
   Q10/Q11/Q12(评测集来源 + 成功标准 + 失败定位)已覆盖。
4. **我能讲清「为什么不用 LangGraph / LangChain」吗?** → v5
   1.3 技能清单已写"自写 ReAct 状态机(对标 LangGraph,不引框架)";
   面试可答:框架引入会绑死 ReAct 推理循环的细节,自写能精准控
   配对保证 / 三出口埋点 / Phase 1 共享循环体等工程点。
5. **我能讲清「为什么不做 multi-agent / MCP / 跨 session 学习」吗?**
   → v5 1.4 · ①任务边界 + 15 题 Q13/Q14/Q15 已诚实标注;面试
   可答:任务边界清晰,5 工具就够,multi-agent 收益不明显所以
   没拆;诚实说明比假装做了更可信。

---

## 5 · 保守边界(诚实标注 · 不写进简历正文)

按 skill 守则,以下仓库现状**不写进简历**,但面试被问及时如实回答:

- 未做模型训练 / 微调 / LoRA(仅集成第三方 OpenAI 兼容 API)。
- 未做 MCP server 暴露、跨 session 学习、多用户 / 权限(README v1.0 推迟)。
- LLM 响应非真正流式:agent 主路径 SSE 仅承载事件(`assistant_message`
  一次性);`ContentWriter.stream_article` 自身支持真流式,但 agent turn
  内仍是事件级流式。
- 无 Cross-Encoder 重排 / HyDE / query rewriting(v0.5.1-3 推迟)。
- 无 PII 脱敏 / 可删除设计 / 多租户鉴权 / OTel Trace ID 贯通 / 客户端
  断开取消处理 / 成本仪表盘。
- 无生产流量与线上指标(诚实备注已写在 1.4 · ⑥ 评测集)。