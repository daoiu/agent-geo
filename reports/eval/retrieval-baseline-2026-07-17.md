# 检索评测基线 2026-07-17

| 指标 | 值 |
|---|---|
| 样本数 | 4 |
| Recall@5 | 1.0 |
| MRR@5 | 0.875 |
| faithfulness | 0.0 |
| answer_relevancy | 0.777 |
| context_precision | 0.25 |
| LLM 指标可用 | True |

> 环境标注:embedding 维度不匹配(384 vs 512),HybridSearch 实际 fallback 到 keyword-only;金标集仅 4 条(1 个 KB / 4 chunks),Recall@5 受 top_k 完全覆盖影响严重;context_precision=0.25 是当前最可信的精确率信号。
