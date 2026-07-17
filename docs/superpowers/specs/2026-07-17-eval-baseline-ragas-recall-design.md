# 设计:评测基准 — RAGAS 式三指标 + Recall@5 基线

> 日期:2026-07-17
> 范围:本 spec 只覆盖「④ 评测闭环」子系统。①混合检索管道 / ②Agent 编排与反思 / ③性能+多模态 各自另立 spec。
> 原则:所有量化数字必须可追溯、可复现,不夸大(对齐 `docs/RESUME_AI_Agent_Target.md` 的诚实基线)。

## 背景与目标

现有 `backend/evals/` 是 **Agent 行为评测**(30 条:工具选择 / 拒答 / 抗诱导,`judge.py` 关键词 + 工具 + LLM-as-Judge 打分),**不含检索相关性评测,也没有 RAGAS 与 Recall@k**。

本子系统新建两条自动化评测线,并先跑出当前系统的「改进前」基线:

- **检索层**:Recall@5 / MRR@5 — 量化 `HybridSearch` 的召回质量。
- **回答层**:RAGAS 式三指标 — 量化最终答案质量。

**关键作用**:这两条基线是后续 ① 混合检索优化(Cross-Encoder 重排 / 查询改写 / 语义缓存)的量化对照。简历中「Recall@5 从 0.61 提升至 0.83」的两个数字,分别是本基线首跑(改进前)与 ① 完成后复跑(改进后)的**真实测量结果**。

## 决策记录(来自澄清)

- **RAGAS 实现**:先自研 RAGAS 式打分器,接口按官方 `ragas` 语义命名,预留后续无缝替换官方包的空间。不引入 `ragas` 重依赖。
- **金标集构建**:LLM 半合成(从现有 KB chunk 生成 question + 参考答案,源 chunk 标为相关)+ 人工抽查修正。
- **规模**:~50 条 query,跨多个真实 KB 采样。
- **三指标**:`faithfulness` / `answer_relevancy` / `context_precision`。
- **顺序**:本子系统(④)先做,之后 ① → ② → ③。

## 架构与模块边界

新增目录 `backend/evals/retrieval/`,与现有 agent 行为评测并存、互不干扰。

| 模块 | 职责 | 依赖 |
|---|---|---|
| `golden_set.jsonl` | 金标数据集(提交入库)。每条:`{id, kb_id, query, relevant_chunk_ids[], reference_answer}` | 无 |
| `dataset_builder.py` | 离线脚本:从现有 KB 采样 chunk → LLM 生成 question + 参考答案 → 源 chunk 标为相关 → 写 jsonl 供人工抽查 | `llm_client` |
| `retrieval_metrics.py` | **纯函数**:`recall_at_k` / `mrr_at_k` / `precision_at_k` | 无 |
| `ragas_scorer.py` | 自研三指标 `faithfulness` / `answer_relevancy` / `context_precision`,接口按 ragas 语义命名 | `llm_client` + bge embedding |
| `retrieval_runner.py` | 编排:载入金标 → 跑 `HybridSearch` → 算 Recall/MRR → 生成答案 → RAGAS 打分 → 聚合 → 报告 | 上面全部 |
| 报告输出 | `reports/eval/retrieval-baseline-<date>.{md,json}`,按 KB 分桶 + 总均值 | 无 |

**边界原则**:metrics 纯函数、零依赖;scorer 只碰 LLM + embedding;runner 只做编排;builder 是离线一次性脚本,不进热路径。每个模块都能独立单测。

## 三指标定义(自研,对齐 RAGAS 语义)

- **faithfulness**:答案中每个陈述能否由检索到的 context 支撑(LLM 逐句判定;支撑句数 / 总句数)。反幻觉。
- **answer_relevancy**:答案与问题的语义相关度(LLM 由答案反推可能的问题,再与原问题做 embedding 余弦均值)。
- **context_precision**:检索到的 context 中,相关片段是否排在靠前位置(结合金标 `relevant_chunk_ids`,按命中位置加权)。

## 数据流

```
一次性:
  dataset_builder → golden_set.jsonl(人工抽查后提交)

每次评测:
  golden_set
    → 逐 query 跑 HybridSearch.search(top_k=5)
    → top-5 chunk_ids vs relevant_chunk_ids  → Recall@5 / MRR@5
    → (检索 context + LLM 生成答案)          → RAGAS 三指标
    → 聚合(按 KB 分桶 + 总均值)
    → baseline 报告(数字入库,作为 ① 的对照基线)
```

## 规模与基线

- **金标集**:~50 条 query,跨多个真实 KB 采样,保证覆盖面与统计意义。
- **首次运行 = 建立基线**:跑当前 `hybrid_search`(向量 + jieba 关键词 + RRF,无重排 / 改写 / 缓存),记录 Recall@5、MRR@5、三指标基线值。此即简历「改进前」数字的真实出处;① 完成后复跑得「改进后」数字。

## 错误处理(沿用现有「静默降级」风格)

- 无 LLM key → `dataset_builder` 与 RAGAS 跳过;**Recall@5 / MRR@5 仍可纯函数计算**;报告标注「LLM 指标不可用」。
- embedding 走本地 HF 缓存(bge-small-zh-v1.5 已在用),沙箱离线可跑。
- Chroma 失败 → 复用 `HybridSearch` 既有降级(退化为关键词);评测照常记录降级态,不中断。
- 编程错误(如金标文件格式错)严格抛出,不被吞 —— 对齐现有 transient / 编程错误分离原则。

## 测试

- `retrieval_metrics`:纯函数边界用例 —— 空命中 / 全命中 / 部分命中 / 重复 id / k 超过结果数。
- `ragas_scorer`:mock `llm_client`,验证三指标计算逻辑与无 key 降级。
- `retrieval_runner`:tiny fixture 金标集(2-3 条)+ mock `HybridSearch`,验证聚合统计与报告结构。
- `dataset_builder`:mock LLM,验证采样 → 生成 → jsonl 写出的字段完整性。

## 交付物

1. `backend/evals/retrieval/` 全套模块 + 单测。
2. `golden_set.jsonl`(~50 条,人工抽查后提交)。
3. 首个基线报告 `reports/eval/retrieval-baseline-2026-07-17.{md,json}`。
4. README / RESUME 目标文档中「评测闭环」段落更新为真实可追溯描述。

## 非目标(明确排除,留给后续 spec)

- Cross-Encoder 重排 / 查询改写 / 语义缓存(① 混合检索管道)。
- Plan-Execute / ReflectionAgent(② 编排与反思)。
- Redis / OCR / VLM(③ 性能 + 多模态)。
- 官方 `ragas` 包接入(仅预留接口,不在本期实现)。
