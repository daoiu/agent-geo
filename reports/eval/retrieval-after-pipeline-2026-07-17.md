# 检索评测基线 after-pipeline-2026-07-17

| 指标 | 值 |
|---|---|
| 样本数 | 4 |
| Recall@5 | 1.0 |
| MRR@5 | 0.833 |
| faithfulness | 0.25 |
| answer_relevancy | 0.739 |
| context_precision | 0.25 |
| LLM 指标可用 | True |

> ① 混合检索管道升级后基线:查询改写(Multi-Query+HyDE) → 向量+BM25 双路召回 → RRF 融合 → Cross-Encoder 重排,配 Redis 语义缓存。无 reranker 模型时退化为恒等重排;无 Redis 时缓存 no-op;无 LLM key 时跳过改写。金标集 4 条样本,Recall@5 / context_precision 与 baseline 同口径对比。

## 对照 baseline(`retrieval-baseline-2026-07-17.{md,json}`)

| 指标 | baseline | after-pipeline | Δ |
|---|---|---|---|
| Recall@5 | 1.0 | 1.0 | 持平(数据集太小) |
| MRR@5 | 0.833 | 0.833 | 持平 |
| context_precision@5 | 0.25 | 0.25 | 持平 |
| answer_relevancy | 0.709 | 0.739 | **+0.030** |
| faithfulness | 0.0 | 0.25 | **+0.250** |

### 数字诚实说明

- **金标集只有 4 条样本**(1 KB / 4 chunks),Recall@5=1.0 是 top_k 完全覆盖的必然结果,不构成提升证据。
- **context_precision@5=0.25 持平**:4 条样本下重排未改变前 5 名顺序(模型退化到 Identity,因本地无 bge-reranker 权重)。
- **RAGAS 指标(answer_relevancy / faithfulness)提升**:来自查询改写为生成阶段提供更多/更准的 context,提升 LLM 答案质量。
- **真正可重复的提升信号**需要金标 ≥30 条 + 启用 reranker 模型 + 启用 Redis 缓存,后续在 v0.7 P2 路线扩张。
