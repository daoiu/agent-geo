# 记忆系统 & 上下文工程优化 — 路线图

| 字段 | 值 |
|---|---|
| 类型 | 多子项目路线图（decomposition roadmap） |
| 日期 | 2026-07-13 |
| 状态 | 已批，逐 Phase 展开设计 |
| 前置 | v0.6 P1.6（L2 跨会话偏好）已上线 |
| 定位 | 单人本地 demo 工具，非 SaaS 多租户 |

## 1. 目标

把 6 项优化收敛为 3 个可独立实施的子项目，按依赖关系排序。全程不破坏
L0（消息持久化）/ L1（KB）/ L2（偏好）三层现有契约，不引入设计文档已否决的项
（重要度打分、三因子排序、注入过滤、记忆图谱、反思、时间衰减、MemGPT 分页）。

## 2. 现状发现（6 项）

**记忆系统（L2）**

1. **每个 user turn 多付 2 次 LLM 往返** —— `load_relevant_memories`（内含
   `select_relevant`）每轮调一次 LLM 选记忆，`extract` 每轮又调一次；短对话、
   无新信息时也照跑。`react_loop.py:256` + `:362`。
2. **L1/L2 技术栈割裂** —— v0.5 已建向量栈（`embedding.py` / `vector_index.py` /
   `hybrid_search.py`，向量+关键词+RRF），但 v0.6 的 L2 选记忆用一次性 LLM 调用
   （`memory.py:135`）。
3. **去重只靠精确 name 匹配** —— `extract` 里 `get_by_name` 完全一致才跳过
   （`memory.py:278`），语义重复要等攒到 50 条触发 `consolidate` 兜底。

**上下文工程（L0 / context 组装）**

4. **工具结果全量回灌历史** —— `search_knowledge` / `diagnose_brand` 的完整 JSON
   被原样存进 tool 消息（`react_loop.py:345`），下一轮全量重放，多轮线性膨胀。
5. **L0 无窗口 / 无摘要** —— 每轮 `list_messages` 全量加载整个 session
   （`react_loop.py:357`），长会话 token 线性增长。
6. **两个 ReAct 循环近乎重复** —— `run_agent_turn` 与
   `run_agent_turn_from_checkpoint` 的 context 组装逻辑几乎一样（~200 行 ×2），
   任何 context 策略调整都要双改。

## 3. 6 项映射到 3 个 Phase

```
Phase 1 ─ 循环收敛 + 埋点        [使能项，先做]
   #6 单一 ReAct 循环
   埋点：token / LLM 调用次数
        │ 使能（后续只改一处）
        │ 基线（量化后续收益）
        ▼
Phase 2 ─ 记忆层 v2             [记忆系统]
   #2 向量化选记忆（复用 EmbeddingService + rrf_fusion）
   #3 语义去重（搭 #2 白送）
   #1 select 换向量 + extract 加门控
        │
        ▼
Phase 3 ─ 上下文预算            [上下文工程，风险最高，最后做]
   #4 工具结果瘦身
   #5 L0 窗口 + 滚动摘要
```

依赖检查：
- Phase 1 使能 Phase 3（#4/#5 只改一处），并提供量化 Phase 2/3 收益的基线
- Phase 2 的 #2 使 #3 几乎白送，并收掉 #1 的 select 半

## 4. Phase 1 — 循环收敛 + 埋点

| 项 | 内容 |
|---|---|
| 动机 | 两个循环重复（~200 行 ×2），L2 接入时被迫双改；后续 #4/#5 还要反复动循环 |
| 改动 | 抽出单一 ReAct 驱动（context 组装 + 工具循环 + 落库 + SSE yield），两入口只保留起点差异（新 turn vs 从 checkpoint 恢复）；每轮记录 token/调用次数 |
| 触及 | `react_loop.py`（主）、可能新增 `agent/loop_core.py` |
| 不触及 | 工具语义、SSE 事件协议、DB schema、L2 逻辑 |
| 成本 / 风险 | 中 / 中 —— 风险集中在 `build_messages` 的 dangling tool_call 配对逻辑（`react_loop.py:69-83`），靠现有 442 测试兜底 |
| 退出标准 | 两入口行为等价（现有测试全绿）；日志能打出每轮 token 与调用次数 |

## 5. Phase 2 — 记忆层 v2

| 项 | 内容 |
|---|---|
| 动机 | 每 turn 多付 2 次 LLM；已有向量栈却用 LLM 选记忆；去重只靠精确 name |
| 改动 | ① 记忆写入时 `EmbeddingService.embed` 存向量；② `select_relevant` 改向量相似度召回（可选 RRF 融关键词），删掉那次 LLM 调用；③ `extract` 前用向量近邻判语义重复；④ `extract` 加门控：turn 过短 / 无新用户信息则跳过 |
| 触及 | `memory.py`、`memory_repo.py`、可能给 memory 建独立 Chroma collection |
| 不触及 | L2 表结构尽量不变（向量可另存）；注入位置（system 索引 + user relevant）不变 |
| 成本 / 风险 | 中 / 低-中 —— 冷启动（存量记忆回填向量）、沙箱无外网靠本地 HF 缓存 |
| 退出标准 | select 零 LLM 调用；语义重复在 extract 阶段被合并；短 turn 不触发 extract；跨 session 偏好复现不回归 |

## 6. Phase 3 — 上下文预算

| 项 | 内容 |
|---|---|
| 动机 | 工具结果全量回灌（`react_loop.py:345`）多轮膨胀；L0 每轮全量重放 |
| 改动 | ① 工具结果分级：最近一轮保全量，更早历史做摘要/裁剪/只留引用；② L0 滑动窗口 + 超阈值滚动摘要（旧消息蒸馏成一条 summary 常驻） |
| 触及 | 收敛后的单循环（Phase 1 成果）、可能新增 `context_budget.py` |
| 不触及 | 消息持久化（DB 存全量，只裁"送进 LLM 的那份"） |
| 成本 / 风险 | 高 / 中-高 —— 摘要损失保真度、工具结果裁剪不当会让 LLM 下一轮缺料，需用 Phase 1 埋点验证 |
| 退出标准 | 长会话 token 增长由线性转亚线性；裁剪/摘要后功能端到端不回归；有前后 token 对比数据 |

## 7. 关键原则

- 每个 Phase 独立走 spec → plan → 实施，可单独上线、单独回滚
- Phase 1 的埋点是后两个 Phase 的验收标尺 —— 没有基线不谈"优化了多少"
- DB 永远存全量历史；所有裁剪/摘要只作用于"送进 LLM 的那一份"，可逆

## 8. 各 Phase 的独立 spec（待产出）

- [ ] `2026-XX-XX-phase1-loop-consolidation-design.md`
- [ ] `2026-XX-XX-phase2-memory-v2-design.md`
- [ ] `2026-XX-XX-phase3-context-budget-design.md`
